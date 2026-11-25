"""Repository layer for Stage 12B Appointment SMS Reminders.

Provides:
1. `ReminderRepositoryProtocol` — formal contract for reminder persistence & queue claiming.
2. `InMemoryReminderRepository` — thread-safe in-memory implementation mirroring PostgreSQL
   deduplication, atomic `SKIP LOCKED` claiming, stale-lease recovery, and tenant scoping.
3. `SupabaseRestReminderRepository` — backend-only `service_role` Supabase PostgREST adapter
   calling `public.claim_due_appointment_reminders` RPC and enforcing strict tenant filters.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
from uuid import UUID
import httpx
from app.core.config import Settings
from app.modules.notifications.schemas import (
    AppointmentSmsReminder,
    BusinessNotificationSettings,
    LeaseUpdateResult,
    LiveAppointmentSnapshot,
    ReconciliationCandidateAppointment,
    ReminderRecipientType,
    ReminderStatus,
)


def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


class ReminderRepositoryProtocol(Protocol):
    """Formal persistence interface for Stage 12B reminder engine."""

    async def get_notification_settings(
        self, organization_id: UUID, business_id: UUID
    ) -> Optional[BusinessNotificationSettings]: ...

    async def upsert_notification_settings(
        self, settings: BusinessNotificationSettings
    ) -> BusinessNotificationSettings: ...

    async def get_max_appointment_version(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> int: ...

    async def upsert_reminders(
        self, reminders: List[AppointmentSmsReminder]
    ) -> List[AppointmentSmsReminder]: ...

    async def list_reminders_for_appointment(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> List[AppointmentSmsReminder]: ...

    async def cancel_pending_for_appointment(
        self,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        *,
        reason: str,
    ) -> int: ...

    async def claim_due_reminders(
        self,
        *,
        batch_size: int = 25,
        worker_id: str = "sms-worker",
        lease_timeout_seconds: int = 300,
        now: Optional[datetime] = None,
    ) -> List[AppointmentSmsReminder]: ...

    async def update_reminder(
        self,
        reminder: AppointmentSmsReminder,
        *,
        expected_worker_id: str,
        expected_locked_at: datetime,
    ) -> LeaseUpdateResult: ...

    async def get_live_appointment_snapshot(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> Optional[LiveAppointmentSnapshot]: ...

    async def list_upcoming_confirmed_appointments(
        self,
        *,
        min_start_at: datetime,
        limit: int = 100,
    ) -> List[ReconciliationCandidateAppointment]: ...

    # Stage 12C.2: Delivery Receipt (DLR) persistence & deduplication
    async def find_reminders_by_provider_message_id(
        self, provider_name: str, provider_message_id: str
    ) -> List[AppointmentSmsReminder]: ...

    async def record_delivery_event_if_new(self, event: Any) -> bool: ...

    async def get_latest_applied_delivery_event_at(
        self, reminder_id: UUID
    ) -> Optional[datetime]: ...

    async def apply_delivery_receipt_update(
        self,
        *,
        reminder_id: UUID,
        organization_id: UUID,
        business_id: UUID,
        new_status: ReminderStatus,
        provider_status: str,
        delivered_at: Optional[datetime],
        last_error: Optional[str],
    ) -> bool: ...

    async def list_unresolved_sent_reminders(
        self,
        provider_name: str,
        *,
        since: datetime,
        limit: int = 25,
    ) -> List[AppointmentSmsReminder]: ...


class InMemoryReminderRepository:
    """Thread-safe in-memory reminder store for unit tests and local dev."""

    def __init__(
        self,
        *,
        live_snapshot_resolver: Optional[
            Callable[[UUID, UUID, UUID], Optional[LiveAppointmentSnapshot]]
        ] = None,
        upcoming_appointments_resolver: Optional[
            Callable[[datetime, int], List[ReconciliationCandidateAppointment]]
        ] = None,
    ) -> None:
        self._lock = asyncio.Lock()
        self._settings: Dict[Tuple[UUID, UUID], BusinessNotificationSettings] = {}
        self._reminders: Dict[UUID, AppointmentSmsReminder] = {}
        self._dedup_keys: Dict[Tuple[UUID, ReminderRecipientType, int], UUID] = {}
        self._delivery_events: Dict[Tuple[str, str], Any] = {}
        self._live_snapshot_resolver = live_snapshot_resolver
        self._upcoming_appointments_resolver = upcoming_appointments_resolver

    def set_live_snapshot_resolver(
        self,
        resolver: Optional[Callable[[UUID, UUID, UUID], Optional[LiveAppointmentSnapshot]]],
    ) -> None:
        self._live_snapshot_resolver = resolver

    def set_upcoming_appointments_resolver(
        self,
        resolver: Optional[Callable[[datetime, int], List[ReconciliationCandidateAppointment]]],
    ) -> None:
        self._upcoming_appointments_resolver = resolver

    def clear(self) -> None:
        self._settings.clear()
        self._reminders.clear()
        self._dedup_keys.clear()
        self._delivery_events.clear()

    async def get_notification_settings(
        self, organization_id: UUID, business_id: UUID
    ) -> Optional[BusinessNotificationSettings]:
        return self._settings.get((organization_id, business_id))

    async def upsert_notification_settings(
        self, settings: BusinessNotificationSettings
    ) -> BusinessNotificationSettings:
        async with self._lock:
            now = datetime.now(timezone.utc)
            saved = settings.model_copy(update={"updated_at": now})
            self._settings[(settings.organization_id, settings.business_id)] = saved
            return saved

    async def get_max_appointment_version(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> int:
        versions = [
            r.appointment_version
            for r in self._reminders.values()
            if r.organization_id == organization_id
            and r.business_id == business_id
            and r.appointment_id == appointment_id
        ]
        return max(versions) if versions else 0

    async def upsert_reminders(
        self, reminders: List[AppointmentSmsReminder]
    ) -> List[AppointmentSmsReminder]:
        async with self._lock:
            inserted: List[AppointmentSmsReminder] = []
            for rem in reminders:
                dedup_key = (rem.appointment_id, rem.recipient_type, rem.appointment_version)
                if dedup_key in self._dedup_keys:
                    continue
                self._dedup_keys[dedup_key] = rem.id
                self._reminders[rem.id] = rem
                inserted.append(rem)
            return inserted

    async def list_reminders_for_appointment(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> List[AppointmentSmsReminder]:
        return sorted(
            [
                r
                for r in self._reminders.values()
                if r.organization_id == organization_id
                and r.business_id == business_id
                and r.appointment_id == appointment_id
            ],
            key=lambda r: (r.appointment_version, r.recipient_type.value, r.created_at),
        )

    async def cancel_pending_for_appointment(
        self,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        *,
        reason: str,
    ) -> int:
        async with self._lock:
            now = datetime.now(timezone.utc)
            cancelled_count = 0
            for rid, rem in list(self._reminders.items()):
                if (
                    rem.organization_id == organization_id
                    and rem.business_id == business_id
                    and rem.appointment_id == appointment_id
                    and rem.status == ReminderStatus.PENDING
                ):
                    self._reminders[rid] = rem.model_copy(
                        update={
                            "status": ReminderStatus.CANCELLED,
                            "last_error": reason,
                            "locked_at": None,
                            "locked_by": None,
                            "updated_at": now,
                        }
                    )
                    cancelled_count += 1
            return cancelled_count

    async def claim_due_reminders(
        self,
        *,
        batch_size: int = 25,
        worker_id: str = "sms-worker",
        lease_timeout_seconds: int = 300,
        now: Optional[datetime] = None,
    ) -> List[AppointmentSmsReminder]:
        async with self._lock:
            ref_now = now or datetime.now(timezone.utc)
            bounded_batch = max(1, min(int(batch_size), 100))
            stale_cutoff = ref_now - timedelta(seconds=max(30, min(int(lease_timeout_seconds), 3600)))

            # Step 1: Recover stale processing leases (mirrors SQL RPC)
            for rid, rem in list(self._reminders.items()):
                if (
                    rem.status == ReminderStatus.PROCESSING
                    and rem.locked_at is not None
                    and rem.locked_at < stale_cutoff
                ):
                    if rem.appointment_start_at <= ref_now:
                        self._reminders[rid] = rem.model_copy(
                            update={
                                "status": ReminderStatus.FAILED,
                                "locked_at": None,
                                "locked_by": None,
                                "last_error": "stale_lease_after_appointment_start",
                                "updated_at": ref_now,
                            }
                        )
                    elif rem.retry_count < rem.max_retries:
                        self._reminders[rid] = rem.model_copy(
                            update={
                                "status": ReminderStatus.PENDING,
                                "retry_count": rem.retry_count + 1,
                                "next_retry_at": ref_now,
                                "locked_at": None,
                                "locked_by": None,
                                "last_error": "stale_lease_recovered",
                                "updated_at": ref_now,
                            }
                        )
                    else:
                        self._reminders[rid] = rem.model_copy(
                            update={
                                "status": ReminderStatus.FAILED,
                                "locked_at": None,
                                "locked_by": None,
                                "last_error": "max_retries_exceeded_after_stale_lease",
                                "updated_at": ref_now,
                            }
                        )

            # Step 2: Claim due pending reminders atomically
            due = [
                r
                for r in self._reminders.values()
                if r.status == ReminderStatus.PENDING
                and (r.next_retry_at or r.scheduled_for) <= ref_now
            ]
            due.sort(key=lambda r: (r.next_retry_at or r.scheduled_for, r.created_at))

            claimed: List[AppointmentSmsReminder] = []
            for rem in due[:bounded_batch]:
                updated = rem.model_copy(
                    update={
                        "status": ReminderStatus.PROCESSING,
                        "locked_at": ref_now,
                        "locked_by": worker_id[:120],
                        "updated_at": ref_now,
                    }
                )
                self._reminders[rem.id] = updated
                claimed.append(updated)
            return claimed

    async def update_reminder(
        self,
        reminder: AppointmentSmsReminder,
        *,
        expected_worker_id: str,
        expected_locked_at: datetime,
    ) -> LeaseUpdateResult:
        """Lease-fenced update: succeeds ONLY if row is still processing under the exact lease."""
        async with self._lock:
            current = self._reminders.get(reminder.id)
            if current is None:
                return LeaseUpdateResult(updated=False, lease_lost=True, reminder=None)
            if (
                current.organization_id != reminder.organization_id
                or current.business_id != reminder.business_id
                or current.status != ReminderStatus.PROCESSING
                or current.locked_by != expected_worker_id
                or current.locked_at is None
                or current.locked_at.astimezone(timezone.utc)
                != expected_locked_at.astimezone(timezone.utc)
            ):
                return LeaseUpdateResult(updated=False, lease_lost=True, reminder=None)

            updated = reminder.model_copy(update={"updated_at": datetime.now(timezone.utc)})
            self._reminders[reminder.id] = updated
            return LeaseUpdateResult(updated=True, lease_lost=False, reminder=updated)

    async def get_live_appointment_snapshot(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> Optional[LiveAppointmentSnapshot]:
        if self._live_snapshot_resolver is None:
            return None
        return self._live_snapshot_resolver(organization_id, business_id, appointment_id)

    async def list_upcoming_confirmed_appointments(
        self,
        *,
        min_start_at: datetime,
        limit: int = 100,
    ) -> List[ReconciliationCandidateAppointment]:
        if self._upcoming_appointments_resolver is None:
            return []
        return self._upcoming_appointments_resolver(min_start_at, limit)

    async def find_reminders_by_provider_message_id(
        self, provider_name: str, provider_message_id: str
    ) -> List[AppointmentSmsReminder]:
        prov = provider_name.strip().lower()
        msg_id = provider_message_id.strip()
        return [
            r
            for r in self._reminders.values()
            if (r.provider_name or "").strip().lower() == prov
            and (r.provider_message_id or "").strip() == msg_id
        ]

    async def record_delivery_event_if_new(self, event: Any) -> bool:
        async with self._lock:
            key = (event.provider_name.strip().lower(), event.event_fingerprint)
            if key in self._delivery_events:
                return False
            self._delivery_events[key] = event
            return True

    async def get_latest_applied_delivery_event_at(
        self, reminder_id: UUID
    ) -> Optional[datetime]:
        timestamps = [
            ev.provider_event_at.astimezone(timezone.utc)
            for ev in self._delivery_events.values()
            if ev.reminder_id == reminder_id
            and ev.applied is True
            and ev.provider_event_at is not None
        ]
        return max(timestamps) if timestamps else None

    async def apply_delivery_receipt_update(
        self,
        *,
        reminder_id: UUID,
        organization_id: UUID,
        business_id: UUID,
        new_status: ReminderStatus,
        provider_status: str,
        delivered_at: Optional[datetime],
        last_error: Optional[str],
    ) -> bool:
        async with self._lock:
            current = self._reminders.get(reminder_id)
            if current is None:
                return False
            if (
                current.organization_id != organization_id
                or current.business_id != business_id
                or current.status == ReminderStatus.DELIVERED
            ):
                return False
            self._reminders[reminder_id] = current.model_copy(
                update={
                    "status": new_status,
                    "provider_status": provider_status,
                    "delivered_at": delivered_at if delivered_at is not None else current.delivered_at,
                    "last_error": last_error if last_error is not None else current.last_error,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            return True

    async def list_unresolved_sent_reminders(
        self,
        provider_name: str,
        *,
        since: datetime,
        limit: int = 25,
    ) -> List[AppointmentSmsReminder]:
        prov = provider_name.strip().lower()
        since_utc = since.astimezone(timezone.utc)
        rows = [
            r
            for r in self._reminders.values()
            if r.status == ReminderStatus.SENT
            and (r.provider_name or "").strip().lower() == prov
            and r.provider_message_id is not None
            and r.sent_at is not None
            and r.sent_at.astimezone(timezone.utc) >= since_utc
        ]
        rows.sort(key=lambda r: r.sent_at or r.created_at)
        return rows[:limit]


class SupabaseRestReminderRepository:
    """Backend-only `service_role` Supabase PostgREST repository for Stage 12B."""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError(
                "SupabaseRestReminderRepository requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        self._base_url = settings.supabase_url.strip().rstrip("/")
        self._service_role_key = settings.supabase_service_role_key.strip()

    def _headers(self, *, prefer: str = "return=representation") -> Dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    @staticmethod
    def _to_reminder(row: Dict[str, Any]) -> AppointmentSmsReminder:
        return AppointmentSmsReminder(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            business_id=UUID(row["business_id"]),
            appointment_id=UUID(row["appointment_id"]),
            appointment_version=int(row["appointment_version"]),
            appointment_start_at=_parse_dt(row["appointment_start_at"]),  # type: ignore[arg-type]
            staff_id=UUID(row["staff_id"]) if row.get("staff_id") else None,
            recipient_type=ReminderRecipientType(row["recipient_type"]),
            recipient_phone=row.get("recipient_phone"),
            recipient_name=row.get("recipient_name"),
            scheduled_for=_parse_dt(row["scheduled_for"]),  # type: ignore[arg-type]
            status=ReminderStatus(row["status"]),
            skip_reason=row.get("skip_reason"),
            template_key=row["template_key"],
            provider_name=row.get("provider_name"),
            provider_message_id=row.get("provider_message_id"),
            provider_status=row.get("provider_status"),
            retry_count=int(row.get("retry_count", 0)),
            max_retries=int(row.get("max_retries", 3)),
            next_retry_at=_parse_dt(row.get("next_retry_at")),
            locked_at=_parse_dt(row.get("locked_at")),
            locked_by=row.get("locked_by"),
            sent_at=_parse_dt(row.get("sent_at")),
            delivered_at=_parse_dt(row.get("delivered_at")),
            last_error=row.get("last_error"),
            created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
            updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
        )

    async def get_notification_settings(
        self, organization_id: UUID, business_id: UUID
    ) -> Optional[BusinessNotificationSettings]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/business_notification_settings",
                headers=self._headers(),
                params={
                    "select": "*",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                return None
            row = rows[0]
            return BusinessNotificationSettings(
                organization_id=UUID(row["organization_id"]),
                business_id=UUID(row["business_id"]),
                owner_sms_phone=row.get("owner_sms_phone"),
                sms_reminders_enabled=bool(row.get("sms_reminders_enabled", False)),
                created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
                updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
            )

    async def upsert_notification_settings(
        self, settings: BusinessNotificationSettings
    ) -> BusinessNotificationSettings:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/business_notification_settings",
                headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
                json={
                    "business_id": str(settings.business_id),
                    "organization_id": str(settings.organization_id),
                    "owner_sms_phone": settings.owner_sms_phone,
                    "sms_reminders_enabled": settings.sms_reminders_enabled,
                },
            )
            resp.raise_for_status()
            row = resp.json()[0]
            return BusinessNotificationSettings(
                organization_id=UUID(row["organization_id"]),
                business_id=UUID(row["business_id"]),
                owner_sms_phone=row.get("owner_sms_phone"),
                sms_reminders_enabled=bool(row.get("sms_reminders_enabled", False)),
                created_at=_parse_dt(row["created_at"]),  # type: ignore[arg-type]
                updated_at=_parse_dt(row["updated_at"]),  # type: ignore[arg-type]
            )

    async def get_max_appointment_version(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> int:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "select": "appointment_version",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "appointment_id": f"eq.{appointment_id}",
                    "order": "appointment_version.desc",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            return int(rows[0]["appointment_version"]) if rows else 0

    async def upsert_reminders(
        self, reminders: List[AppointmentSmsReminder]
    ) -> List[AppointmentSmsReminder]:
        if not reminders:
            return []
        payload = [
            {
                "id": str(r.id),
                "organization_id": str(r.organization_id),
                "business_id": str(r.business_id),
                "appointment_id": str(r.appointment_id),
                "appointment_version": r.appointment_version,
                "appointment_start_at": r.appointment_start_at.astimezone(timezone.utc).isoformat(),
                "staff_id": str(r.staff_id) if r.staff_id else None,
                "recipient_type": r.recipient_type.value,
                "recipient_phone": r.recipient_phone,
                "recipient_name": r.recipient_name,
                "scheduled_for": r.scheduled_for.astimezone(timezone.utc).isoformat(),
                "status": r.status.value,
                "skip_reason": r.skip_reason,
                "template_key": r.template_key,
                "retry_count": r.retry_count,
                "max_retries": r.max_retries,
                "last_error": r.last_error,
            }
            for r in reminders
        ]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(prefer="resolution=ignore-duplicates,return=representation"),
                params={"on_conflict": "appointment_id,recipient_type,appointment_version"},
                json=payload,
            )
            resp.raise_for_status()
            return [self._to_reminder(row) for row in resp.json()]

    async def list_reminders_for_appointment(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> List[AppointmentSmsReminder]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "select": "*",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "appointment_id": f"eq.{appointment_id}",
                    "order": "appointment_version.asc,recipient_type.asc",
                },
            )
            resp.raise_for_status()
            return [self._to_reminder(row) for row in resp.json()]

    async def cancel_pending_for_appointment(
        self,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        *,
        reason: str,
    ) -> int:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "appointment_id": f"eq.{appointment_id}",
                    "status": "eq.pending",
                },
                json={
                    "status": ReminderStatus.CANCELLED.value,
                    "last_error": reason,
                    "locked_at": None,
                    "locked_by": None,
                },
            )
            resp.raise_for_status()
            return len(resp.json())

    async def claim_due_reminders(
        self,
        *,
        batch_size: int = 25,
        worker_id: str = "sms-worker",
        lease_timeout_seconds: int = 300,
        now: Optional[datetime] = None,
    ) -> List[AppointmentSmsReminder]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/rpc/claim_due_appointment_reminders",
                headers=self._headers(),
                json={
                    "p_batch_size": batch_size,
                    "p_worker_id": worker_id,
                    "p_lease_timeout_seconds": lease_timeout_seconds,
                },
            )
            resp.raise_for_status()
            rows = resp.json() or []
            return [self._to_reminder(row) for row in rows]

    async def update_reminder(
        self,
        reminder: AppointmentSmsReminder,
        *,
        expected_worker_id: str,
        expected_locked_at: datetime,
    ) -> LeaseUpdateResult:
        """Lease-fenced PostgREST PATCH verifying id, tenant, status=processing, locked_by, and locked_at."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "id": f"eq.{reminder.id}",
                    "organization_id": f"eq.{reminder.organization_id}",
                    "business_id": f"eq.{reminder.business_id}",
                    "status": "eq.processing",
                    "locked_by": f"eq.{expected_worker_id}",
                    "locked_at": f"eq.{expected_locked_at.astimezone(timezone.utc).isoformat()}",
                },
                json={
                    "status": reminder.status.value,
                    "skip_reason": reminder.skip_reason,
                    "provider_name": reminder.provider_name,
                    "provider_message_id": reminder.provider_message_id,
                    "provider_status": reminder.provider_status,
                    "retry_count": reminder.retry_count,
                    "next_retry_at": (
                        reminder.next_retry_at.astimezone(timezone.utc).isoformat()
                        if reminder.next_retry_at
                        else None
                    ),
                    "locked_at": (
                        reminder.locked_at.astimezone(timezone.utc).isoformat()
                        if reminder.locked_at
                        else None
                    ),
                    "locked_by": reminder.locked_by,
                    "sent_at": (
                        reminder.sent_at.astimezone(timezone.utc).isoformat()
                        if reminder.sent_at
                        else None
                    ),
                    "delivered_at": (
                        reminder.delivered_at.astimezone(timezone.utc).isoformat()
                        if reminder.delivered_at
                        else None
                    ),
                    "last_error": reminder.last_error,
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                return LeaseUpdateResult(updated=False, lease_lost=True, reminder=None)
            return LeaseUpdateResult(
                updated=True,
                lease_lost=False,
                reminder=self._to_reminder(rows[0]),
            )

    async def get_live_appointment_snapshot(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> Optional[LiveAppointmentSnapshot]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(),
                params={
                    "select": (
                        "id,organization_id,business_id,booking_reference,status,start_at,timezone,"
                        "staff_id,customer_name,"
                        "salon_services(name),salon_staff(full_name),businesses(name)"
                    ),
                    "id": f"eq.{appointment_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                return None
            row = rows[0]
            svc = row.get("salon_services") or {}
            st = row.get("salon_staff") or {}
            biz = row.get("businesses") or {}
            return LiveAppointmentSnapshot(
                appointment_id=UUID(row["id"]),
                organization_id=UUID(row["organization_id"]),
                business_id=UUID(row["business_id"]),
                booking_reference=row["booking_reference"],
                status=row["status"],
                start_at=_parse_dt(row["start_at"]),  # type: ignore[arg-type]
                timezone=row["timezone"],
                staff_id=UUID(row["staff_id"]),
                staff_name=st.get("full_name") or "Stylist",
                service_name=svc.get("name") or "Service",
                customer_name=row["customer_name"],
                salon_name=biz.get("name") or "Salon",
            )

    async def list_upcoming_confirmed_appointments(
        self,
        *,
        min_start_at: datetime,
        limit: int = 100,
    ) -> List[ReconciliationCandidateAppointment]:
        bounded_limit = max(1, min(int(limit), 200))
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/salon_appointments",
                headers=self._headers(),
                params={
                    "select": (
                        "id,organization_id,business_id,start_at,timezone,status,"
                        "staff_id,customer_name,customer_phone,"
                        "salon_staff(full_name,phone)"
                    ),
                    "status": "in.(confirmed,rescheduled)",
                    "start_at": f"gt.{min_start_at.astimezone(timezone.utc).isoformat()}",
                    "order": "start_at.asc",
                    "limit": str(bounded_limit),
                },
            )
            resp.raise_for_status()
            results: List[ReconciliationCandidateAppointment] = []
            for row in resp.json() or []:
                st = row.get("salon_staff") or {}
                results.append(
                    ReconciliationCandidateAppointment(
                        appointment_id=UUID(row["id"]),
                        organization_id=UUID(row["organization_id"]),
                        business_id=UUID(row["business_id"]),
                        start_at=_parse_dt(row["start_at"]),  # type: ignore[arg-type]
                        timezone=row["timezone"],
                        status=row["status"],
                        staff_id=UUID(row["staff_id"]),
                        staff_name=st.get("full_name") or "Stylist",
                        staff_phone=st.get("phone"),
                        customer_name=row["customer_name"],
                        customer_phone=row["customer_phone"],
                    )
                )
            return results

    async def find_reminders_by_provider_message_id(
        self, provider_name: str, provider_message_id: str
    ) -> List[AppointmentSmsReminder]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "select": "*",
                    "provider_name": f"eq.{provider_name.strip().lower()}",
                    "provider_message_id": f"eq.{provider_message_id.strip()}",
                    "limit": "2",
                },
            )
            resp.raise_for_status()
            return [self._to_reminder(row) for row in resp.json() or []]

    async def record_delivery_event_if_new(self, event: Any) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/appointment_sms_delivery_events",
                headers=self._headers(prefer="resolution=ignore-duplicates,return=representation"),
                params={"on_conflict": "provider_name,event_fingerprint"},
                json={
                    "id": str(event.id),
                    "organization_id": str(event.organization_id),
                    "business_id": str(event.business_id),
                    "reminder_id": str(event.reminder_id),
                    "provider_name": event.provider_name,
                    "provider_message_id": event.provider_message_id,
                    "event_fingerprint": event.event_fingerprint,
                    "source": event.source,
                    "normalized_outcome": event.normalized_outcome.value,
                    "raw_status_code": event.raw_status_code,
                    "provider_event_at": (
                        event.provider_event_at.astimezone(timezone.utc).isoformat()
                        if event.provider_event_at
                        else None
                    ),
                    "applied": event.applied,
                    "ignored_reason": event.ignored_reason,
                },
            )
            resp.raise_for_status()
            return len(resp.json() or []) > 0

    async def get_latest_applied_delivery_event_at(
        self, reminder_id: UUID
    ) -> Optional[datetime]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/appointment_sms_delivery_events",
                headers=self._headers(),
                params={
                    "select": "provider_event_at",
                    "reminder_id": f"eq.{reminder_id}",
                    "applied": "eq.true",
                    "provider_event_at": "not.is.null",
                    "order": "provider_event_at.desc",
                    "limit": "1",
                },
            )
            resp.raise_for_status()
            rows = resp.json() or []
            return _parse_dt(rows[0]["provider_event_at"]) if rows else None

    async def apply_delivery_receipt_update(
        self,
        *,
        reminder_id: UUID,
        organization_id: UUID,
        business_id: UUID,
        new_status: ReminderStatus,
        provider_status: str,
        delivered_at: Optional[datetime],
        last_error: Optional[str],
    ) -> bool:
        body: Dict[str, Any] = {
            "status": new_status.value,
            "provider_status": provider_status,
        }
        if delivered_at is not None:
            body["delivered_at"] = delivered_at.astimezone(timezone.utc).isoformat()
        if last_error is not None:
            body["last_error"] = last_error

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "id": f"eq.{reminder_id}",
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "status": "neq.delivered",
                },
                json=body,
            )
            resp.raise_for_status()
            return len(resp.json() or []) > 0

    async def list_unresolved_sent_reminders(
        self,
        provider_name: str,
        *,
        since: datetime,
        limit: int = 25,
    ) -> List[AppointmentSmsReminder]:
        bounded_limit = max(1, min(int(limit), 50))
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/appointment_sms_reminders",
                headers=self._headers(),
                params={
                    "select": "*",
                    "provider_name": f"eq.{provider_name.strip().lower()}",
                    "status": "eq.sent",
                    "provider_message_id": "not.is.null",
                    "sent_at": f"gte.{since.astimezone(timezone.utc).isoformat()}",
                    "order": "sent_at.asc",
                    "limit": str(bounded_limit),
                },
            )
            resp.raise_for_status()
            return [self._to_reminder(row) for row in resp.json() or []]


_in_memory_reminder_repo = InMemoryReminderRepository()


def get_in_memory_reminder_repository() -> InMemoryReminderRepository:
    return _in_memory_reminder_repo
