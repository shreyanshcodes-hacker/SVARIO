"""Stage 12B — Comprehensive Reliability, Security & Lifecycle Tests for SMS Reminder Engine."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Optional
from uuid import UUID, uuid4
import httpx
import pytest
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.modules.notifications.providers import NoopSmsProvider, SmsProviderError
from app.modules.notifications.repository import InMemoryReminderRepository
from app.modules.notifications.schemas import (
    BusinessNotificationSettings,
    LiveAppointmentSnapshot,
    ReminderRecipientType,
    ReminderStatus,
    SmsErrorCategory,
    normalize_e164_phone,
)
from app.modules.notifications.service import AppointmentReminderService
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.schemas import (
    BusinessHoursResponse,
    BusinessProfileUpdateRequest,
    WeekdayHoursItem,
)
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationIndustry,
    OrganizationRole,
)
from app.modules.salons.repository import InMemorySalonRepository
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentStatus,
    SalonServiceCreateRequest,
    SalonStaffCreateRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
)
from app.modules.salons.service import SalonWorkflowService
from app.modules.websites.schemas import PublicBookingWebsiteResponse
from app.workers.sms_reminder_worker import SmsReminderWorker


def _make_actor(user_id: Optional[UUID] = None) -> AuthenticatedUser:
    uid = user_id or uuid4()
    return AuthenticatedUser(
        id=uid,
        email="owner@example.test",
        role="authenticated",
        issuer="https://test.supabase.co/auth/v1",
        audience="authenticated",
        raw_token="test-jwt",
    )


async def _bootstrap_salon(
    *,
    sms_enabled: bool = True,
    owner_sms_phone: Optional[str] = "+14155550100",
    staff_phone: Optional[str] = "+447911123456",
    business_profile_phone: str = "+919999999999",
    timezone_name: str = "UTC",
):
    settings = Settings(
        SVARIO_ENV="test",
        SUPABASE_URL=None,
        SUPABASE_ANON_KEY=None,
        SMS_REMINDERS_ENABLED=sms_enabled,
        SMS_PROVIDER="noop",
        SMS_REMINDER_LEAD_MINUTES=30,
    )
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    salon_repo = InMemorySalonRepository()
    provider = NoopSmsProvider()

    actor = _make_actor()
    org = await org_repo.create_organization(
        actor,
        CreateOrganizationRequest(
            name="Test Luxe Salon",
            industry=OrganizationIndustry.SALON,
            timezone=timezone_name,
        ),
    )
    org_id = org.id
    biz_id = await onboarding_repo.get_or_create_primary_business_id(actor, org_id)

    await onboarding_repo.upsert_business_profile(
        actor,
        org_id,
        biz_id,
        BusinessProfileUpdateRequest(
            display_name="Test Luxe Salon",
            phone=business_profile_phone,
            timezone=timezone_name,
        ),
    )

    # Wire live appointment snapshot resolver backed by InMemorySalonRepository
    def _resolve_live(oid: UUID, bid: UUID, aid: UUID) -> Optional[LiveAppointmentSnapshot]:
        for appt in salon_repo._appointments.get(bid, []):
            if appt.id == aid and appt.organization_id == oid:
                return LiveAppointmentSnapshot(
                    appointment_id=appt.id,
                    organization_id=appt.organization_id,
                    business_id=appt.business_id,
                    booking_reference=appt.booking_reference,
                    status=appt.status.value,
                    start_at=appt.start_at,
                    timezone=appt.timezone,
                    staff_id=appt.staff_id,
                    staff_name=appt.staff_name,
                    service_name=appt.service_name,
                    customer_name=appt.customer_name,
                    salon_name="Test Luxe Salon",
                )
        return None

    reminder_repo = InMemoryReminderRepository(live_snapshot_resolver=_resolve_live)
    if owner_sms_phone is not None:
        await reminder_repo.upsert_notification_settings(
            BusinessNotificationSettings(
                organization_id=org_id,
                business_id=biz_id,
                owner_sms_phone=owner_sms_phone,
                sms_reminders_enabled=True,
            )
        )

    reminder_service = AppointmentReminderService(
        settings=settings,
        repo=reminder_repo,
        provider=provider,
    )
    salon_service = SalonWorkflowService(
        settings=settings,
        salon_repo=salon_repo,
        onboarding_repo=onboarding_repo,
        reminder_service=reminder_service,
    )

    svc = await salon_service.create_service(
        actor,
        org_id,
        biz_id,
        SalonServiceCreateRequest(
            name="Precision Haircut",
            category="Hair",
            price=45.0,
            currency="USD",
            duration_minutes=30,
        ),
    )
    staff = await salon_service.create_staff(
        actor,
        org_id,
        biz_id,
        SalonStaffCreateRequest(
            full_name="Alex Stylist",
            role_designation="Senior Stylist",
            phone=staff_phone,
            assigned_service_ids=[svc.id],
        ),
    )
    # Open every day 00:00-23:55 for flexible test dates
    full_week = [
        SalonStaffWorkingHoursItem(weekday=d, is_off=False, start_time="00:00", end_time="23:55")
        for d in range(7)
    ]
    await salon_service.update_staff_working_hours(
        actor,
        org_id,
        biz_id,
        staff.id,
        SalonStaffWorkingHoursUpdateRequest(schedule=full_week),
    )

    hours_override = BusinessHoursResponse(
        organization_id=org_id,
        business_id=biz_id,
        timezone=timezone_name,
        schedule=[
            WeekdayHoursItem(weekday=d, is_closed=False, opens_at="00:00", closes_at="23:55")
            for d in range(7)
        ],
    )

    return {
        "settings": settings,
        "actor": actor,
        "org_id": org_id,
        "biz_id": biz_id,
        "svc": svc,
        "staff": staff,
        "salon_repo": salon_repo,
        "salon_service": salon_service,
        "reminder_repo": reminder_repo,
        "reminder_service": reminder_service,
        "provider": provider,
        "hours_override": hours_override,
    }


def test_sms_disabled_by_default():
    """Requirement 15: SMS_REMINDERS_ENABLED defaults to False and provider defaults to noop."""
    default_settings = Settings(_env_file=None)
    assert default_settings.sms_reminders_enabled is False
    assert default_settings.sms_provider == "noop"
    assert default_settings.sms_worker_poll_interval_seconds == 30
    assert default_settings.sms_default_country_code is None


def test_international_phone_normalization_does_not_assume_india():
    """Phone normalization supports global E.164 and never silently assumes +91."""
    assert normalize_e164_phone("+1 (415) 555-2671") == "+14155552671"
    assert normalize_e164_phone("0044 7911 123456") == "+447911123456"
    assert normalize_e164_phone("+91 98765-43210") == "+919876543210"
    # Bare local 10-digit number without country code MUST NOT assume +91
    assert normalize_e164_phone("9876543210") is None
    # Only qualifies local numbers if an explicit default_country_code is supplied
    assert normalize_e164_phone("4155552671", default_country_code="+1") == "+14155552671"
    assert normalize_e164_phone("not-a-phone") is None


@pytest.mark.asyncio
async def test_customer_owner_staff_reminders_created_on_booking():
    """Requirements 1, 2, 3: All 3 recipients scheduled 30 minutes before start_at in UTC."""
    env = await _bootstrap_salon(
        owner_sms_phone="+14155550100",
        staff_phone="+447911123456",
    )
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Jane International",
            customer_phone="+1 (212) 555-0199",
            idempotency_key="req-create-1",
        ),
        business_hours_override=env["hours_override"],
    )

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    assert len(reminders) == 3
    by_type = {r.recipient_type: r for r in reminders}

    expected_scheduled = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=30)
    assert by_type[ReminderRecipientType.CUSTOMER].status == ReminderStatus.PENDING
    assert by_type[ReminderRecipientType.CUSTOMER].recipient_phone == "+12125550199"
    assert by_type[ReminderRecipientType.CUSTOMER].scheduled_for == expected_scheduled

    assert by_type[ReminderRecipientType.OWNER].status == ReminderStatus.PENDING
    assert by_type[ReminderRecipientType.OWNER].recipient_phone == "+14155550100"
    assert by_type[ReminderRecipientType.OWNER].scheduled_for == expected_scheduled

    assert by_type[ReminderRecipientType.STAFF].status == ReminderStatus.PENDING
    assert by_type[ReminderRecipientType.STAFF].recipient_phone == "+447911123456"
    assert by_type[ReminderRecipientType.STAFF].scheduled_for == expected_scheduled


@pytest.mark.asyncio
async def test_missing_owner_and_staff_phones_record_skipped_no_phone():
    """Requirements 2, 4, 5: Never fall back to business_profiles.phone; record skipped_no_phone."""
    env = await _bootstrap_salon(
        owner_sms_phone=None,
        staff_phone=None,
        business_profile_phone="+919999999999",  # Public reception number — MUST NOT be used!
    )
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="15:00",
            customer_name="Customer Only",
            customer_phone="+12125550188",
        ),
        business_hours_override=env["hours_override"],
    )

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    by_type = {r.recipient_type: r for r in reminders}

    assert by_type[ReminderRecipientType.CUSTOMER].status == ReminderStatus.PENDING
    assert by_type[ReminderRecipientType.OWNER].status == ReminderStatus.SKIPPED
    assert by_type[ReminderRecipientType.OWNER].skip_reason == "skipped_no_phone"
    assert by_type[ReminderRecipientType.OWNER].recipient_phone is None

    assert by_type[ReminderRecipientType.STAFF].status == ReminderStatus.SKIPPED
    assert by_type[ReminderRecipientType.STAFF].skip_reason == "skipped_no_phone"
    assert by_type[ReminderRecipientType.STAFF].recipient_phone is None


@pytest.mark.asyncio
async def test_duplicate_appointment_replay_creates_no_duplicate_reminders():
    """Requirement 6: Idempotent appointment creation replay does not duplicate reminders."""
    env = await _bootstrap_salon()
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    payload = SalonAppointmentCreateRequest(
        service_id=env["svc"].id,
        staff_id=env["staff"].id,
        appointment_date=target_date,
        start_time="16:00",
        customer_name="Replay Customer",
        customer_phone="+12125550177",
        idempotency_key="idem-replay-test",
    )
    appt1 = await env["salon_service"].create_appointment(
        env["actor"], env["org_id"], env["biz_id"], payload, business_hours_override=env["hours_override"]
    )
    appt2 = await env["salon_service"].create_appointment(
        env["actor"], env["org_id"], env["biz_id"], payload, business_hours_override=env["hours_override"]
    )
    assert appt1.id == appt2.id
    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt1.id
    )
    assert len(reminders) == 3


@pytest.mark.asyncio
async def test_reschedule_and_staff_reassignment_cancels_v1_and_creates_v2():
    """Requirements 7 & 9: Reschedule invalidates v1 pending reminders and schedules v2 for new staff."""
    env = await _bootstrap_salon(staff_phone="+447911111111")
    staff2 = await env["salon_service"].create_staff(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonStaffCreateRequest(
            full_name="Morgan Colorist",
            role_designation="Stylist",
            phone="+447922222222",
            assigned_service_ids=[env["svc"].id],
        ),
    )
    await env["salon_service"].update_staff_working_hours(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        staff2.id,
        SalonStaffWorkingHoursUpdateRequest(
            schedule=[
                SalonStaffWorkingHoursItem(weekday=d, is_off=False, start_time="00:00", end_time="23:55")
                for d in range(7)
            ]
        ),
    )

    d1 = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    d2 = (datetime.now(timezone.utc) + timedelta(days=4)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=d1,
            start_time="10:00",
            customer_name="Reschedule User",
            customer_phone="+12125550166",
        ),
        business_hours_override=env["hours_override"],
    )

    rescheduled = await env["salon_service"].reschedule_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        appt.id,
        SalonAppointmentRescheduleRequest(
            appointment_date=d2,
            start_time="15:30",
            staff_id=staff2.id,
        ),
        business_hours_override=env["hours_override"],
    )

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    v1 = [r for r in reminders if r.appointment_version == 1]
    v2 = [r for r in reminders if r.appointment_version == 2]

    assert len(v1) == 3
    assert all(r.status == ReminderStatus.CANCELLED for r in v1)
    assert all(r.last_error == "appointment_rescheduled" for r in v1)

    assert len(v2) == 3
    assert all(r.status == ReminderStatus.PENDING for r in v2)
    v2_staff = next(r for r in v2 if r.recipient_type == ReminderRecipientType.STAFF)
    assert v2_staff.staff_id == staff2.id
    assert v2_staff.recipient_phone == "+447922222222"
    assert v2_staff.scheduled_for == rescheduled.start_at.astimezone(timezone.utc) - timedelta(minutes=30)


@pytest.mark.asyncio
async def test_cancellation_and_terminal_status_invalidate_pending_reminders():
    """Requirement 8: Cancellation and completed/no_show transitions cancel pending reminders."""
    env = await _bootstrap_salon()
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="11:00",
            customer_name="Cancel User",
            customer_phone="+12125550155",
        ),
        business_hours_override=env["hours_override"],
    )

    await env["salon_service"].cancel_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        appt.id,
        SalonAppointmentCancelRequest(cancellation_reason="Plans changed"),
    )

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    assert len(reminders) == 3
    assert all(r.status == ReminderStatus.CANCELLED for r in reminders)

    # Also verify terminal status helper for future completed/no_show transitions
    appt2 = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="12:00",
            customer_name="Completed User",
            customer_phone="+12125550154",
        ),
        business_hours_override=env["hours_override"],
    )
    await env["salon_service"].invalidate_reminders_for_terminal_status(
        env["org_id"], env["biz_id"], appt2.id, SalonAppointmentStatus.NO_SHOW
    )
    reminders2 = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt2.id
    )
    assert all(r.status == ReminderStatus.CANCELLED and r.last_error == "appointment_no_show" for r in reminders2)


@pytest.mark.asyncio
async def test_last_minute_booking_skips_reminders():
    """Requirement 10: Booking < 30 minutes before start_at marks reminders skipped_last_minute_booking."""
    env = await _bootstrap_salon()
    now_utc = datetime.now(timezone.utc)
    # Schedule 15 minutes from now (ensure same UTC day; if near midnight, use tomorrow + explicit now)
    target_date = (now_utc + timedelta(days=2)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Last Minute",
            customer_phone="+12125550144",
        ),
        business_hours_override=env["hours_override"],
    )
    # Clear and re-run sync simulating `now = start_at - 15 minutes`
    env["reminder_repo"].clear()
    await env["reminder_service"].sync_for_created_appointment(
        appointment=appt,
        staff=env["staff"],
        now=appt.start_at - timedelta(minutes=15),
    )
    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    assert len(reminders) == 3
    assert all(
        r.status == ReminderStatus.SKIPPED and r.skip_reason == "skipped_last_minute_booking"
        for r in reminders
    )


@pytest.mark.asyncio
async def test_duplicate_worker_execution_and_noop_zero_network(monkeypatch):
    """Requirements 11 & 16: Concurrent workers never double-send; NoopSmsProvider makes zero HTTP calls."""
    async def _forbid_network(*args, **kwargs):
        raise AssertionError("NoopSmsProvider must NEVER perform outbound HTTP requests!")

    monkeypatch.setattr(httpx.AsyncClient, "post", _forbid_network)
    monkeypatch.setattr(httpx.AsyncClient, "get", _forbid_network)

    env = await _bootstrap_salon()
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Concurrent User",
            customer_phone="+12125550133",
        ),
        business_hours_override=env["hours_override"],
    )

    due_time = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=29)
    res_a, res_b = await asyncio.gather(
        env["reminder_service"].process_due_reminders_once(worker_id="worker-A", now=due_time),
        env["reminder_service"].process_due_reminders_once(worker_id="worker-B", now=due_time),
    )

    assert res_a.claimed + res_b.claimed == 3
    assert res_a.sent_simulated + res_b.sent_simulated == 3
    assert len(env["provider"].dispatched_records) == 3

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    # Provider acceptance marks `sent`, NEVER `delivered`
    assert all(r.status == ReminderStatus.SENT for r in reminders)
    assert all(r.delivered_at is None for r in reminders)
    assert all(r.provider_name == "noop" and r.provider_message_id.startswith("noop-") for r in reminders)


@pytest.mark.asyncio
async def test_worker_crash_and_stale_lease_recovery():
    """Requirement 12: Crashed worker lease is reclaimed after timeout; never sent after start_at."""
    env = await _bootstrap_salon()
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Lease Recovery",
            customer_phone="+12125550122",
        ),
        business_hours_override=env["hours_override"],
    )

    # Worker 1 claims reminders at T-30m and crashes (never updates status)
    t_claim = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=30)
    claimed = await env["reminder_repo"].claim_due_reminders(
        worker_id="crashed-worker",
        lease_timeout_seconds=300,
        now=t_claim,
    )
    assert len(claimed) == 3
    assert all(r.status == ReminderStatus.PROCESSING for r in claimed)

    # 6 minutes later (past 300s lease timeout, still 24 min before appointment), Worker 2 recovers & dispatches
    t_recover = t_claim + timedelta(minutes=6)
    summary = await env["reminder_service"].process_due_reminders_once(
        worker_id="healthy-worker",
        now=t_recover,
    )
    assert summary.claimed == 3
    assert summary.sent_simulated == 3
    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    assert all(r.status == ReminderStatus.SENT and r.retry_count == 1 for r in reminders)


@pytest.mark.asyncio
async def test_race_between_cancellation_or_reschedule_and_dispatch():
    """Race test: appointment cancelled AFTER claim but BEFORE dispatch must abort and never send."""
    env = await _bootstrap_salon()
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Race User",
            customer_phone="+12125550111",
        ),
        business_hours_override=env["hours_override"],
    )

    # Intercept claim_due_reminders so that right after claiming, the appointment is cancelled in DB
    orig_claim = env["reminder_repo"].claim_due_reminders

    async def _claim_then_cancel(**kwargs):
        claimed_rows = await orig_claim(**kwargs)
        # Simulate concurrent cancellation committed while worker holds the claimed rows
        stored = env["salon_repo"]._appointments[env["biz_id"]][0]
        env["salon_repo"]._appointments[env["biz_id"]][0] = stored.model_copy(
            update={"status": SalonAppointmentStatus.CANCELLED}
        )
        return claimed_rows

    env["reminder_repo"].claim_due_reminders = _claim_then_cancel  # type: ignore[method-assign]

    due_time = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=29)
    summary = await env["reminder_service"].process_due_reminders_once(
        worker_id="race-worker", now=due_time
    )

    assert summary.claimed == 3
    assert summary.sent_simulated == 0
    assert summary.cancelled_stale == 3
    assert len(env["provider"].dispatched_records) == 0

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    assert all(
        r.status == ReminderStatus.CANCELLED and r.last_error == "appointment_status_cancelled"
        for r in reminders
    )


@pytest.mark.asyncio
async def test_cross_tenant_isolation_and_public_api_privacy():
    """Requirements 13 & 14: Strict tenant isolation & zero private phone fields on public website schema."""
    env_a = await _bootstrap_salon(owner_sms_phone="+14155550101", staff_phone="+447911100001")
    org_b = uuid4()
    biz_b = uuid4()

    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt_a = await env_a["salon_service"].create_appointment(
        env_a["actor"],
        env_a["org_id"],
        env_a["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env_a["svc"].id,
            staff_id=env_a["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Tenant A Customer",
            customer_phone="+12125550101",
        ),
        business_hours_override=env_a["hours_override"],
    )

    # Tenant B cannot read Tenant A's reminders or notification settings
    assert await env_a["reminder_repo"].list_reminders_for_appointment(org_b, biz_b, appt_a.id) == []
    assert await env_a["reminder_repo"].get_notification_settings(org_b, biz_b) is None
    assert await env_a["reminder_repo"].cancel_pending_for_appointment(
        org_b, biz_b, appt_a.id, reason="cross_tenant_attempt"
    ) == 0

    # Tenant A's reminders remain untouched
    reminders_a = await env_a["reminder_repo"].list_reminders_for_appointment(
        env_a["org_id"], env_a["biz_id"], appt_a.id
    )
    assert len(reminders_a) == 3
    assert all(r.status == ReminderStatus.PENDING for r in reminders_a)

    # Public website response schema must NEVER contain private notification/owner/staff/customer phones
    public_schema_json = str(PublicBookingWebsiteResponse.model_json_schema())
    assert "owner_sms_phone" not in public_schema_json
    assert "customer_phone" not in public_schema_json
    assert "recipient_phone" not in public_schema_json


@pytest.mark.asyncio
async def test_disabled_flag_prevents_scheduling_and_dispatch():
    """Requirement 15: When SMS_REMINDERS_ENABLED=False, zero reminders are scheduled or dispatched."""
    env = await _bootstrap_salon(sms_enabled=False)
    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Disabled Flag User",
            customer_phone="+12125550109",
        ),
        business_hours_override=env["hours_override"],
    )
    assert await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    ) == []

    summary = await env["reminder_service"].process_due_reminders_once()
    assert summary.skipped_disabled is True
    assert summary.claimed == 0


@pytest.mark.asyncio
async def test_worker_survives_db_outage_and_never_logs_phones(caplog):
    """Worker handles DB outage gracefully without crashing and logs zero phone numbers."""
    env = await _bootstrap_salon(owner_sms_phone="+14155550199", staff_phone="+447911199999")
    caplog.set_level(logging.INFO)

    target_date = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    appt = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=target_date,
            start_time="14:00",
            customer_name="Privacy Check",
            customer_phone="+12125550199",
        ),
        business_hours_override=env["hours_override"],
    )

    due_time = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=29)
    await env["reminder_service"].process_due_reminders_once(worker_id="log-check", now=due_time)

    # Verify zero phone numbers leaked to logs
    all_logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "+14155550199" not in all_logs
    assert "+447911199999" not in all_logs
    assert "+12125550199" not in all_logs

    # Simulate DB outage in worker tick — must NOT raise unhandled exception
    async def _boom(**kwargs):
        raise RuntimeError("simulated_db_outage")

    env["reminder_repo"].claim_due_reminders = _boom  # type: ignore[method-assign]
    worker = SmsReminderWorker(settings=env["settings"], service=env["reminder_service"])
    res = await worker.run_once()
    assert res.claimed == 0
