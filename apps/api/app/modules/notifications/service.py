"""Stage 12B Appointment SMS Reminder Service.

Authoritative lifecycle synchronization + safe worker dispatch engine:
- Single authoritative sync layer called by `SalonWorkflowService` (no duplicate DB triggers).
- Explicit recipient resolution:
  * Customer: appointment `customer_phone` (normalized to E.164).
  * Owner: ONLY explicit `business_notification_settings.owner_sms_phone` (NEVER falls back
    to `business_profiles.phone` or public reception phone). Records `skipped` / `skipped_no_phone`
    if unconfigured.
  * Staff: assigned `salon_staff.phone` only when valid E.164; otherwise `skipped` / `skipped_no_phone`.
- Stage 12B enforces `NoopSmsProvider` exclusively and defaults `SMS_REMINDERS_ENABLED=false`.
- Privacy: NEVER logs phone numbers, secrets, or sensitive customer PII.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional
from uuid import UUID, uuid4
from app.core.config import Settings, get_settings
from app.modules.notifications.providers import (
    NoopSmsProvider,
    SmsProviderError,
    SmsProviderProtocol,
    build_sms_provider,
    classify_transport_error,
)
from app.modules.notifications.repository import (
    InMemoryReminderRepository,
    ReminderRepositoryProtocol,
    SupabaseRestReminderRepository,
    get_in_memory_reminder_repository,
)
from app.modules.notifications.schemas import (
    AppointmentSmsReminder,
    ReconciliationCandidateAppointment,
    ReminderRecipientType,
    ReminderStatus,
    SmsErrorCategory,
    SmsSendRequest,
    build_reminder_template_variables,
    normalize_e164_phone,
    render_reminder_message,
)
from app.modules.salons.schemas import (
    SalonAppointmentResponse,
    SalonAppointmentStatus,
    SalonStaffResponse,
)

logger = logging.getLogger("svario.notifications.reminders")

_RETRY_BACKOFF_SECONDS = (60, 180, 300)
_TEMPLATE_KEYS = {
    ReminderRecipientType.CUSTOMER: "customer_30m",
    ReminderRecipientType.OWNER: "owner_30m",
    ReminderRecipientType.STAFF: "staff_30m",
}


@dataclass(frozen=True)
class WorkerDispatchSummary:
    """Sanitized summary returned by one worker polling cycle (contains zero PII)."""

    claimed: int = 0
    sent_simulated: int = 0
    cancelled_stale: int = 0
    retried: int = 0
    failed: int = 0
    ambiguous_timeout: int = 0
    lease_lost: int = 0
    skipped_disabled: bool = False


@dataclass(frozen=True)
class ReconciliationSummary:
    """Sanitized summary returned by one recipient-level reconciliation pass."""

    appointments_checked: int = 0
    reminders_repaired: int = 0
    skipped_disabled: bool = False


class AppointmentReminderService:
    """Orchestrates appointment reminder scheduling, lifecycle sync, and worker dispatch."""

    def __init__(
        self,
        *,
        settings: Settings,
        repo: ReminderRepositoryProtocol,
        provider: Optional[SmsProviderProtocol] = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        # Stage 12B: default to NoopSmsProvider exclusively; real SMS delivery is not authorized.
        self._provider: SmsProviderProtocol = provider or NoopSmsProvider()

    @property
    def repository(self) -> ReminderRepositoryProtocol:
        return self._repo

    @property
    def provider(self) -> SmsProviderProtocol:
        return self._provider

    def _build_recipient_reminder_from_fields(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        appointment_start_at: datetime,
        staff_id: Optional[UUID],
        appointment_version: int,
        recipient_type: ReminderRecipientType,
        raw_phone: Optional[str],
        recipient_name: Optional[str],
        now: datetime,
    ) -> AppointmentSmsReminder:
        start_utc = appointment_start_at.astimezone(timezone.utc)
        lead_delta = timedelta(minutes=self._settings.sms_reminder_lead_minutes)
        scheduled_for = start_utc - lead_delta

        normalized_phone = normalize_e164_phone(
            raw_phone,
            default_country_code=self._settings.sms_default_country_code,
        )

        # Last-minute booking check: skip reminders when booked < 30 minutes before start
        if scheduled_for <= now:
            status = ReminderStatus.SKIPPED
            skip_reason = "skipped_last_minute_booking"
            stored_phone = normalized_phone
        elif normalized_phone is None:
            status = ReminderStatus.SKIPPED
            skip_reason = (
                "skipped_no_phone"
                if raw_phone is None or not raw_phone.strip()
                else "skipped_invalid_phone"
            )
            stored_phone = None
        else:
            status = ReminderStatus.PENDING
            skip_reason = None
            stored_phone = normalized_phone

        return AppointmentSmsReminder(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            appointment_id=appointment_id,
            appointment_version=appointment_version,
            appointment_start_at=start_utc,
            staff_id=staff_id,
            recipient_type=recipient_type,
            recipient_phone=stored_phone,
            recipient_name=recipient_name,
            scheduled_for=scheduled_for,
            status=status,
            skip_reason=skip_reason,
            template_key=_TEMPLATE_KEYS[recipient_type],
            retry_count=0,
            max_retries=3,
            created_at=now,
            updated_at=now,
        )

    def _build_recipient_reminder(
        self,
        *,
        appointment: SalonAppointmentResponse,
        appointment_version: int,
        recipient_type: ReminderRecipientType,
        raw_phone: Optional[str],
        recipient_name: Optional[str],
        now: datetime,
    ) -> AppointmentSmsReminder:
        return self._build_recipient_reminder_from_fields(
            organization_id=appointment.organization_id,
            business_id=appointment.business_id,
            appointment_id=appointment.id,
            appointment_start_at=appointment.start_at,
            staff_id=appointment.staff_id,
            appointment_version=appointment_version,
            recipient_type=recipient_type,
            raw_phone=raw_phone,
            recipient_name=recipient_name,
            now=now,
        )

    async def _schedule_version(
        self,
        *,
        appointment: SalonAppointmentResponse,
        staff: Optional[SalonStaffResponse],
        appointment_version: int,
        now: Optional[datetime] = None,
    ) -> List[AppointmentSmsReminder]:
        ref_now = now or datetime.now(timezone.utc)

        # Owner phone comes ONLY from explicit business_notification_settings.owner_sms_phone
        # NEVER falls back to business_profiles.phone or public reception phone.
        notif_settings = await self._repo.get_notification_settings(
            appointment.organization_id, appointment.business_id
        )
        owner_raw_phone = notif_settings.owner_sms_phone if notif_settings else None
        staff_raw_phone = staff.phone if staff is not None else None
        staff_name = staff.full_name if staff is not None else appointment.staff_name

        candidates = [
            self._build_recipient_reminder(
                appointment=appointment,
                appointment_version=appointment_version,
                recipient_type=ReminderRecipientType.CUSTOMER,
                raw_phone=appointment.customer_phone,
                recipient_name=appointment.customer_name,
                now=ref_now,
            ),
            self._build_recipient_reminder(
                appointment=appointment,
                appointment_version=appointment_version,
                recipient_type=ReminderRecipientType.OWNER,
                raw_phone=owner_raw_phone,
                recipient_name="Salon Owner",
                now=ref_now,
            ),
            self._build_recipient_reminder(
                appointment=appointment,
                appointment_version=appointment_version,
                recipient_type=ReminderRecipientType.STAFF,
                raw_phone=staff_raw_phone,
                recipient_name=staff_name,
                now=ref_now,
            ),
        ]

        inserted = await self._repo.upsert_reminders(candidates)
        logger.info(
            "sms_reminders_scheduled appointment_id=%s version=%s inserted=%s",
            appointment.id,
            appointment_version,
            len(inserted),
        )
        return inserted

    async def sync_for_created_appointment(
        self,
        *,
        appointment: SalonAppointmentResponse,
        staff: Optional[SalonStaffResponse],
        now: Optional[datetime] = None,
    ) -> List[AppointmentSmsReminder]:
        """Authoritative sync on appointment creation (idempotent on booking replay)."""
        if appointment.status not in {
            SalonAppointmentStatus.CONFIRMED,
            SalonAppointmentStatus.RESCHEDULED,
        }:
            return []

        existing_ver = await self._repo.get_max_appointment_version(
            appointment.organization_id, appointment.business_id, appointment.id
        )
        if existing_ver >= 1:
            # Idempotent replay of an already-scheduled appointment: do not duplicate
            return []

        return await self._schedule_version(
            appointment=appointment,
            staff=staff,
            appointment_version=1,
            now=now,
        )

    async def sync_for_rescheduled_appointment(
        self,
        *,
        appointment: SalonAppointmentResponse,
        staff: Optional[SalonStaffResponse],
        now: Optional[datetime] = None,
    ) -> List[AppointmentSmsReminder]:
        """Authoritative sync on appointment reschedule: cancel old pending, create next version."""
        await self._repo.cancel_pending_for_appointment(
            appointment.organization_id,
            appointment.business_id,
            appointment.id,
            reason="appointment_rescheduled",
        )
        prev_ver = await self._repo.get_max_appointment_version(
            appointment.organization_id, appointment.business_id, appointment.id
        )
        next_ver = prev_ver + 1
        return await self._schedule_version(
            appointment=appointment,
            staff=staff,
            appointment_version=next_ver,
            now=now,
        )

    async def cancel_for_appointment(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        reason: str = "appointment_cancelled",
    ) -> int:
        """Authoritative sync on cancellation, completion, or no_show."""
        cancelled = await self._repo.cancel_pending_for_appointment(
            organization_id,
            business_id,
            appointment_id,
            reason=reason,
        )
        logger.info(
            "sms_reminders_cancelled appointment_id=%s cancelled=%s reason=%s",
            appointment_id,
            cancelled,
            reason,
        )
        return cancelled

    async def reconcile_missing_reminders_once(
        self,
        *,
        now: Optional[datetime] = None,
        limit: int = 100,
    ) -> ReconciliationSummary:
        """Recipient-level reconciliation for upcoming confirmed/rescheduled appointments.

        Independently repairs missing customer, explicit-owner, or assigned-staff
        reminders without recreating intentionally skipped recipients, cancelled
        appointments, obsolete appointment versions, or last-minute/past bookings.
        """
        if not self._settings.sms_reminders_enabled:
            return ReconciliationSummary(skipped_disabled=True)

        ref_now = now or datetime.now(timezone.utc)
        min_start_at = ref_now + timedelta(minutes=self._settings.sms_reminder_lead_minutes)
        candidates: List[ReconciliationCandidateAppointment] = (
            await self._repo.list_upcoming_confirmed_appointments(
                min_start_at=min_start_at,
                limit=limit,
            )
        )

        repaired_total = 0
        for appt in candidates:
            if appt.status not in {
                SalonAppointmentStatus.CONFIRMED.value,
                SalonAppointmentStatus.RESCHEDULED.value,
            }:
                continue
            appt_start_utc = appt.start_at.astimezone(timezone.utc)
            if appt_start_utc <= min_start_at:
                continue

            existing_all = await self._repo.list_reminders_for_appointment(
                appt.organization_id, appt.business_id, appt.appointment_id
            )
            # Only consider reminders matching the CURRENT appointment_start_at
            # (obsolete/cancelled versions from earlier times are ignored, never recreated).
            current_version_rows = [
                r
                for r in existing_all
                if r.appointment_start_at.astimezone(timezone.utc) == appt_start_utc
            ]

            if current_version_rows:
                target_version = max(r.appointment_version for r in current_version_rows)
                latest_rows = [
                    r for r in current_version_rows if r.appointment_version == target_version
                ]
            else:
                max_prev = max((r.appointment_version for r in existing_all), default=0)
                target_version = max_prev + 1
                latest_rows = []

            # Any existing row (including `skipped` or `cancelled` for this exact version)
            # counts as already accounted for so intentionally skipped recipients are not recreated.
            present_types = {r.recipient_type for r in latest_rows}
            missing_types = [
                rt
                for rt in (
                    ReminderRecipientType.CUSTOMER,
                    ReminderRecipientType.OWNER,
                    ReminderRecipientType.STAFF,
                )
                if rt not in present_types
            ]
            if not missing_types:
                continue

            notif_settings = await self._repo.get_notification_settings(
                appt.organization_id, appt.business_id
            )
            owner_raw_phone = notif_settings.owner_sms_phone if notif_settings else None

            to_insert: List[AppointmentSmsReminder] = []
            for rt in missing_types:
                if rt == ReminderRecipientType.CUSTOMER:
                    raw_phone = appt.customer_phone
                    rec_name = appt.customer_name
                elif rt == ReminderRecipientType.OWNER:
                    raw_phone = owner_raw_phone
                    rec_name = "Salon Owner"
                else:
                    raw_phone = appt.staff_phone
                    rec_name = appt.staff_name

                to_insert.append(
                    self._build_recipient_reminder_from_fields(
                        organization_id=appt.organization_id,
                        business_id=appt.business_id,
                        appointment_id=appt.appointment_id,
                        appointment_start_at=appt_start_utc,
                        staff_id=appt.staff_id,
                        appointment_version=target_version,
                        recipient_type=rt,
                        raw_phone=raw_phone,
                        recipient_name=rec_name,
                        now=ref_now,
                    )
                )

            inserted = await self._repo.upsert_reminders(to_insert)
            repaired_total += len(inserted)

        if repaired_total > 0:
            logger.info(
                "sms_reminders_reconciled appointments_checked=%s reminders_repaired=%s",
                len(candidates),
                repaired_total,
            )
        return ReconciliationSummary(
            appointments_checked=len(candidates),
            reminders_repaired=repaired_total,
            skipped_disabled=False,
        )

    async def process_due_reminders_once(
        self,
        *,
        worker_id: str = "sms-worker",
        now: Optional[datetime] = None,
    ) -> WorkerDispatchSummary:
        """Run one atomic claim-and-dispatch cycle with strict lease fencing.

        - Respects `SMS_REMINDERS_ENABLED` (defaults to False).
        - Re-reads live appointment state right before dispatch to catch races.
        - Fences every processing state transition by `(id, org, biz, status=processing, locked_by, locked_at)`.
        - Never retries `AMBIGUOUS_TIMEOUT` automatically (prevents duplicate SMS).
        - Never sends after `appointment_start_at`.
        - Never logs phone numbers, message bodies, or secrets.
        """
        if not self._settings.sms_reminders_enabled:
            return WorkerDispatchSummary(skipped_disabled=True)

        ref_now = now or datetime.now(timezone.utc)
        claimed = await self._repo.claim_due_reminders(
            batch_size=self._settings.sms_worker_batch_size,
            worker_id=worker_id,
            lease_timeout_seconds=self._settings.sms_worker_lease_timeout_seconds,
            now=ref_now,
        )

        sent_sim = 0
        cancelled_stale = 0
        retried = 0
        failed = 0
        ambiguous_timeout = 0
        lease_lost = 0

        for rem in claimed:
            lease_worker_id = rem.locked_by or worker_id
            lease_locked_at = rem.locked_at or ref_now

            # 1. Hard cutoff: never send after appointment start
            if rem.appointment_start_at <= ref_now:
                upd = await self._repo.update_reminder(
                    rem.model_copy(
                        update={
                            "status": ReminderStatus.FAILED,
                            "locked_at": None,
                            "locked_by": None,
                            "last_error": "missed_appointment_start",
                        }
                    ),
                    expected_worker_id=lease_worker_id,
                    expected_locked_at=lease_locked_at,
                )
                if upd.lease_lost:
                    lease_lost += 1
                    logger.warning("sms_reminder_lease_lost reminder_id=%s appointment_id=%s", rem.id, rem.appointment_id)
                else:
                    failed += 1
                continue

            # 2. Re-read authoritative live appointment state immediately before dispatch
            live = await self._repo.get_live_appointment_snapshot(
                rem.organization_id, rem.business_id, rem.appointment_id
            )
            stale_reason: Optional[str] = None
            if live is None:
                stale_reason = "appointment_not_found"
            elif live.status not in {
                SalonAppointmentStatus.CONFIRMED.value,
                SalonAppointmentStatus.RESCHEDULED.value,
            }:
                stale_reason = f"appointment_status_{live.status}"
            elif live.start_at.astimezone(timezone.utc) != rem.appointment_start_at.astimezone(timezone.utc):
                stale_reason = "appointment_time_changed"
            elif (
                rem.recipient_type == ReminderRecipientType.STAFF
                and rem.staff_id is not None
                and live.staff_id != rem.staff_id
            ):
                stale_reason = "appointment_staff_reassigned"

            if stale_reason is not None:
                upd = await self._repo.update_reminder(
                    rem.model_copy(
                        update={
                            "status": ReminderStatus.CANCELLED,
                            "locked_at": None,
                            "locked_by": None,
                            "last_error": stale_reason,
                        }
                    ),
                    expected_worker_id=lease_worker_id,
                    expected_locked_at=lease_locked_at,
                )
                if upd.lease_lost:
                    lease_lost += 1
                    logger.warning("sms_reminder_lease_lost reminder_id=%s appointment_id=%s", rem.id, rem.appointment_id)
                else:
                    cancelled_stale += 1
                    logger.info(
                        "sms_reminder_cancelled_stale reminder_id=%s appointment_id=%s recipient=%s reason=%s",
                        rem.id,
                        rem.appointment_id,
                        rem.recipient_type.value,
                        stale_reason,
                    )
                continue

            if not rem.recipient_phone:
                upd = await self._repo.update_reminder(
                    rem.model_copy(
                        update={
                            "status": ReminderStatus.SKIPPED,
                            "skip_reason": "skipped_no_phone",
                            "locked_at": None,
                            "locked_by": None,
                        }
                    ),
                    expected_worker_id=lease_worker_id,
                    expected_locked_at=lease_locked_at,
                )
                if upd.lease_lost:
                    lease_lost += 1
                continue

            # 3. Render transactional copy & dispatch via provider (NoopSmsProvider in Stage 12B)
            assert live is not None
            body = render_reminder_message(
                recipient_type=rem.recipient_type,
                salon_name=live.salon_name,
                service_name=live.service_name,
                appointment_start_at=live.start_at,
                timezone_name=live.timezone,
                customer_name=live.customer_name,
                staff_name=live.staff_name,
                booking_reference=live.booking_reference,
                lead_minutes=self._settings.sms_reminder_lead_minutes,
            )
            template_vars = build_reminder_template_variables(
                recipient_type=rem.recipient_type,
                salon_name=live.salon_name,
                service_name=live.service_name,
                appointment_start_at=live.start_at,
                timezone_name=live.timezone,
                customer_name=live.customer_name,
                staff_name=live.staff_name,
                booking_reference=live.booking_reference,
            )
            send_req = SmsSendRequest(
                reminder_id=rem.id,
                recipient_type=rem.recipient_type,
                recipient_phone=rem.recipient_phone,
                template_key=rem.template_key,
                message_body=body,
                idempotency_key=f"{rem.appointment_id}:{rem.recipient_type.value}:v{rem.appointment_version}",
                template_variables=template_vars,
            )

            try:
                result = await self._provider.send_sms(send_req)
                # Provider acceptance marks `sent` (NEVER `delivered` without carrier DLR)
                upd = await self._repo.update_reminder(
                    rem.model_copy(
                        update={
                            "status": ReminderStatus.SENT,
                            "provider_name": result.provider_name,
                            "provider_message_id": result.provider_message_id,
                            "provider_status": result.provider_status,
                            "sent_at": ref_now,
                            "locked_at": None,
                            "locked_by": None,
                            "last_error": None,
                        }
                    ),
                    expected_worker_id=lease_worker_id,
                    expected_locked_at=lease_locked_at,
                )
                if upd.lease_lost:
                    lease_lost += 1
                    logger.warning(
                        "sms_reminder_lease_lost_post_send reminder_id=%s appointment_id=%s recipient=%s",
                        rem.id,
                        rem.appointment_id,
                        rem.recipient_type.value,
                    )
                else:
                    sent_sim += 1
                    logger.info(
                        "sms_reminder_dispatched reminder_id=%s appointment_id=%s recipient=%s provider=%s simulated=%s",
                        rem.id,
                        rem.appointment_id,
                        rem.recipient_type.value,
                        result.provider_name,
                        result.simulated,
                    )
            except SmsProviderError as exc:
                if exc.category == SmsErrorCategory.AMBIGUOUS_TIMEOUT:
                    # NEVER blindly retry ambiguous provider outcomes — prevents duplicate SMS
                    upd = await self._repo.update_reminder(
                        rem.model_copy(
                            update={
                                "status": ReminderStatus.FAILED,
                                "provider_status": "manual_review_ambiguous_timeout",
                                "locked_at": None,
                                "locked_by": None,
                                "last_error": exc.error_code or "provider_timeout_ambiguous",
                            }
                        ),
                        expected_worker_id=lease_worker_id,
                        expected_locked_at=lease_locked_at,
                    )
                    if upd.lease_lost:
                        lease_lost += 1
                    else:
                        ambiguous_timeout += 1
                        failed += 1
                        logger.warning(
                            "sms_reminder_ambiguous_timeout reminder_id=%s appointment_id=%s recipient=%s error_code=%s",
                            rem.id,
                            rem.appointment_id,
                            rem.recipient_type.value,
                            exc.error_code,
                        )
                    continue

                next_retry_count = rem.retry_count + 1
                if (
                    exc.category == SmsErrorCategory.TRANSIENT
                    and rem.retry_count < rem.max_retries
                ):
                    backoff_idx = min(rem.retry_count, len(_RETRY_BACKOFF_SECONDS) - 1)
                    next_at = ref_now + timedelta(seconds=_RETRY_BACKOFF_SECONDS[backoff_idx])
                    if next_at < rem.appointment_start_at:
                        upd = await self._repo.update_reminder(
                            rem.model_copy(
                                update={
                                    "status": ReminderStatus.PENDING,
                                    "retry_count": next_retry_count,
                                    "next_retry_at": next_at,
                                    "locked_at": None,
                                    "locked_by": None,
                                    "last_error": exc.error_code,
                                }
                            ),
                            expected_worker_id=lease_worker_id,
                            expected_locked_at=lease_locked_at,
                        )
                        if upd.lease_lost:
                            lease_lost += 1
                        else:
                            retried += 1
                        continue

                upd = await self._repo.update_reminder(
                    rem.model_copy(
                        update={
                            "status": ReminderStatus.FAILED,
                            "retry_count": next_retry_count,
                            "locked_at": None,
                            "locked_by": None,
                            "last_error": exc.error_code,
                        }
                    ),
                    expected_worker_id=lease_worker_id,
                    expected_locked_at=lease_locked_at,
                )
                if upd.lease_lost:
                    lease_lost += 1
                else:
                    failed += 1
                    logger.warning(
                        "sms_reminder_failed reminder_id=%s appointment_id=%s recipient=%s error_code=%s",
                        rem.id,
                        rem.appointment_id,
                        rem.recipient_type.value,
                        exc.error_code,
                    )
            except Exception as exc:
                # Conservatively classify unexpected transport/runtime errors
                category = classify_transport_error(exc)
                if category == SmsErrorCategory.TRANSIENT and rem.retry_count < rem.max_retries:
                    next_retry_count = rem.retry_count + 1
                    backoff_idx = min(rem.retry_count, len(_RETRY_BACKOFF_SECONDS) - 1)
                    next_at = ref_now + timedelta(seconds=_RETRY_BACKOFF_SECONDS[backoff_idx])
                    if next_at < rem.appointment_start_at:
                        upd = await self._repo.update_reminder(
                            rem.model_copy(
                                update={
                                    "status": ReminderStatus.PENDING,
                                    "retry_count": next_retry_count,
                                    "next_retry_at": next_at,
                                    "locked_at": None,
                                    "locked_by": None,
                                    "last_error": "pre_send_transport_error",
                                }
                            ),
                            expected_worker_id=lease_worker_id,
                            expected_locked_at=lease_locked_at,
                        )
                        if upd.lease_lost:
                            lease_lost += 1
                        else:
                            retried += 1
                        continue

                upd = await self._repo.update_reminder(
                    rem.model_copy(
                        update={
                            "status": ReminderStatus.FAILED,
                            "provider_status": "manual_review_ambiguous_timeout",
                            "locked_at": None,
                            "locked_by": None,
                            "last_error": "provider_timeout_ambiguous",
                        }
                    ),
                    expected_worker_id=lease_worker_id,
                    expected_locked_at=lease_locked_at,
                )
                if upd.lease_lost:
                    lease_lost += 1
                else:
                    ambiguous_timeout += 1
                    failed += 1

        return WorkerDispatchSummary(
            claimed=len(claimed),
            sent_simulated=sent_sim,
            cancelled_stale=cancelled_stale,
            retried=retried,
            failed=failed,
            ambiguous_timeout=ambiguous_timeout,
            lease_lost=lease_lost,
            skipped_disabled=False,
        )


def build_appointment_reminder_service(
    *,
    settings: Optional[Settings] = None,
    repo: Optional[ReminderRepositoryProtocol] = None,
    provider: Optional[SmsProviderProtocol] = None,
) -> Optional[AppointmentReminderService]:
    """Build an `AppointmentReminderService` using `NoopSmsProvider` (Stage 12B).

    Returns `None` in live-Supabase mode when `SUPABASE_SERVICE_ROLE_KEY` is missing
    so existing appointment operations never break.
    """
    resolved_settings = settings if isinstance(settings, Settings) else get_settings()
    if repo is not None:
        resolved_repo: ReminderRepositoryProtocol = repo
    elif resolved_settings.is_live_supabase_configured:
        if not resolved_settings.supabase_service_role_key:
            return None
        resolved_repo = SupabaseRestReminderRepository(settings=resolved_settings)
    else:
        resolved_repo = get_in_memory_reminder_repository()

    resolved_provider = provider if provider is not None else build_sms_provider(resolved_settings)
    return AppointmentReminderService(
        settings=resolved_settings,
        repo=resolved_repo,
        provider=resolved_provider,
    )
