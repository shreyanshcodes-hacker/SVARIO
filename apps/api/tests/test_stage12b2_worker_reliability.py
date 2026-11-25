"""Stage 12B.2 — Worker Reliability Finalization Tests.

Covers:
1. Lease fencing: stale worker cannot overwrite `sent`, `cancelled`, or reclaimed leases.
2. PostgREST lease-fencing query parameters on `SupabaseRestReminderRepository`.
3. Ambiguous provider timeouts (`AMBIGUOUS_TIMEOUT` & `httpx.ReadTimeout`) are NOT retried.
4. Safe pre-send failures (`TRANSIENT` & `httpx.ConnectTimeout`) remain retryable with backoff.
5. Recipient-level reconciliation: idempotency, partial set repair, intentionally skipped
   preservation, last-minute/past exclusion, cancelled/obsolete version exclusion, and
   missing phone handling.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import httpx
import pytest
from app.core.config import Settings
from app.modules.notifications.providers import (
    NoopSmsProvider,
    SmsProviderError,
    classify_transport_error,
)
from app.modules.notifications.repository import (
    InMemoryReminderRepository,
    SupabaseRestReminderRepository,
)
from app.modules.notifications.schemas import (
    AppointmentSmsReminder,
    BusinessNotificationSettings,
    LiveAppointmentSnapshot,
    ReconciliationCandidateAppointment,
    ReminderRecipientType,
    ReminderStatus,
    SmsErrorCategory,
    SmsSendRequest,
    SmsSendResult,
)
from app.modules.notifications.service import AppointmentReminderService
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentStatus,
)
from app.workers.sms_reminder_worker import SmsReminderWorker
from tests.test_stage12b_sms_reminders import _bootstrap_salon


def _attach_upcoming_resolver(env: Dict[str, Any]) -> None:
    """Attach upcoming confirmed appointment resolver backed by InMemorySalonRepository."""
    salon_repo = env["salon_repo"]

    def _resolve_upcoming(min_start_at: datetime, limit: int) -> List[ReconciliationCandidateAppointment]:
        staff_by_id = {}
        for st_list in salon_repo._staff.values():
            for st in st_list:
                staff_by_id[st.id] = st

        out: List[ReconciliationCandidateAppointment] = []
        for appts in salon_repo._appointments.values():
            for appt in appts:
                if appt.status not in {
                    SalonAppointmentStatus.CONFIRMED,
                    SalonAppointmentStatus.RESCHEDULED,
                }:
                    continue
                if appt.start_at.astimezone(timezone.utc) <= min_start_at.astimezone(timezone.utc):
                    continue
                st = staff_by_id.get(appt.staff_id)
                out.append(
                    ReconciliationCandidateAppointment(
                        appointment_id=appt.id,
                        organization_id=appt.organization_id,
                        business_id=appt.business_id,
                        start_at=appt.start_at,
                        timezone=appt.timezone,
                        status=appt.status.value,
                        staff_id=appt.staff_id,
                        staff_name=st.full_name if st else appt.staff_name,
                        staff_phone=st.phone if st else None,
                        customer_name=appt.customer_name,
                        customer_phone=appt.customer_phone,
                    )
                )
        out.sort(key=lambda a: a.start_at)
        return out[:limit]

    env["reminder_repo"].set_upcoming_appointments_resolver(_resolve_upcoming)


@pytest.mark.asyncio
async def test_stale_worker_cannot_overwrite_sent_state():
    """Lease fencing: once a reminder is `sent`, a stale worker's update is rejected with lease_lost=True."""
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
            customer_name="Fence Sent",
            customer_phone="+12125550201",
        ),
        business_hours_override=env["hours_override"],
    )

    t0 = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=30)
    claimed = await env["reminder_repo"].claim_due_reminders(
        worker_id="worker-old", lease_timeout_seconds=300, now=t0
    )
    stale_rem = claimed[0]
    assert stale_rem.locked_at is not None

    # Worker-old finishes and marks it `sent` legitimately
    ok = await env["reminder_repo"].update_reminder(
        stale_rem.model_copy(
            update={
                "status": ReminderStatus.SENT,
                "provider_name": "noop",
                "provider_message_id": "noop-legit",
                "locked_at": None,
                "locked_by": None,
            }
        ),
        expected_worker_id="worker-old",
        expected_locked_at=stale_rem.locked_at,
    )
    assert ok.updated is True and ok.lease_lost is False

    # Stale duplicate attempt trying to overwrite `sent` with `failed` MUST be rejected
    rejected = await env["reminder_repo"].update_reminder(
        stale_rem.model_copy(
            update={
                "status": ReminderStatus.FAILED,
                "last_error": "late_overwrite_attempt",
                "locked_at": None,
                "locked_by": None,
            }
        ),
        expected_worker_id="worker-old",
        expected_locked_at=stale_rem.locked_at,
    )
    assert rejected.updated is False and rejected.lease_lost is True

    stored = env["reminder_repo"]._reminders[stale_rem.id]
    assert stored.status == ReminderStatus.SENT
    assert stored.provider_message_id == "noop-legit"


@pytest.mark.asyncio
async def test_stale_worker_cannot_overwrite_cancelled_state():
    """Lease fencing: once a reminder is `cancelled`, a stale worker cannot transition it to `sent`."""
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
            customer_name="Fence Cancel",
            customer_phone="+12125550202",
        ),
        business_hours_override=env["hours_override"],
    )

    t0 = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=30)
    claimed = await env["reminder_repo"].claim_due_reminders(
        worker_id="worker-A", lease_timeout_seconds=300, now=t0
    )
    rem = claimed[0]
    assert rem.locked_at is not None

    # Simulate external transition to `cancelled`
    env["reminder_repo"]._reminders[rem.id] = rem.model_copy(
        update={"status": ReminderStatus.CANCELLED, "locked_at": None, "locked_by": None}
    )

    rejected = await env["reminder_repo"].update_reminder(
        rem.model_copy(
            update={
                "status": ReminderStatus.SENT,
                "provider_name": "noop",
                "provider_message_id": "noop-bad",
                "locked_at": None,
                "locked_by": None,
            }
        ),
        expected_worker_id="worker-A",
        expected_locked_at=rem.locked_at,
    )
    assert rejected.updated is False and rejected.lease_lost is True
    assert env["reminder_repo"]._reminders[rem.id].status == ReminderStatus.CANCELLED


@pytest.mark.asyncio
async def test_reclaimed_lease_rejects_old_worker():
    """Lease fencing: after Worker B reclaims a stale lease, Worker A's delayed write is rejected."""
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
            customer_name="Reclaim Fence",
            customer_phone="+12125550203",
        ),
        business_hours_override=env["hours_override"],
    )

    t_a = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=30)
    claimed_a = await env["reminder_repo"].claim_due_reminders(
        worker_id="worker-A", lease_timeout_seconds=300, now=t_a
    )
    rem_a = claimed_a[0]
    assert rem_a.locked_at == t_a

    # 6 minutes later, Worker B reclaims the expired lease
    t_b = t_a + timedelta(minutes=6)
    claimed_b = await env["reminder_repo"].claim_due_reminders(
        worker_id="worker-B", lease_timeout_seconds=300, now=t_b
    )
    rem_b = next(r for r in claimed_b if r.id == rem_a.id)
    assert rem_b.locked_by == "worker-B"
    assert rem_b.locked_at == t_b

    # Worker A wakes up and attempts to commit `failed` using its old lease
    res_a = await env["reminder_repo"].update_reminder(
        rem_a.model_copy(
            update={"status": ReminderStatus.FAILED, "last_error": "old_worker_write", "locked_at": None, "locked_by": None}
        ),
        expected_worker_id="worker-A",
        expected_locked_at=t_a,
    )
    assert res_a.updated is False and res_a.lease_lost is True

    # Worker B still owns the lease and can commit `sent` cleanly
    res_b = await env["reminder_repo"].update_reminder(
        rem_b.model_copy(
            update={
                "status": ReminderStatus.SENT,
                "provider_name": "noop",
                "provider_message_id": "noop-worker-b",
                "locked_at": None,
                "locked_by": None,
            }
        ),
        expected_worker_id="worker-B",
        expected_locked_at=t_b,
    )
    assert res_b.updated is True and res_b.lease_lost is False
    assert env["reminder_repo"]._reminders[rem_a.id].status == ReminderStatus.SENT
    assert env["reminder_repo"]._reminders[rem_a.id].provider_message_id == "noop-worker-b"


@pytest.mark.asyncio
async def test_supabase_repo_update_reminder_enforces_lease_fencing_params(monkeypatch):
    """SupabaseRestReminderRepository sends full lease-fencing filters and returns lease_lost on 0 rows."""
    captured: Dict[str, Any] = {}

    class _FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> List[Dict[str, Any]]:
            return []  # Simulate 0 rows matched (lease lost)

    async def _fake_patch(self, url, headers=None, params=None, json=None):
        captured["params"] = params
        return _FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "patch", _fake_patch)

    repo = SupabaseRestReminderRepository(
        Settings(
            _env_file=None,
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="sb_secret_test_only",
        )
    )
    now = datetime.now(timezone.utc)
    rem = AppointmentSmsReminder(
        id=uuid4(),
        organization_id=uuid4(),
        business_id=uuid4(),
        appointment_id=uuid4(),
        appointment_version=1,
        appointment_start_at=now + timedelta(hours=1),
        recipient_type=ReminderRecipientType.CUSTOMER,
        recipient_phone="+12125550299",
        scheduled_for=now + timedelta(minutes=30),
        status=ReminderStatus.SENT,
        template_key="customer_30m",
        created_at=now,
        updated_at=now,
    )
    res = await repo.update_reminder(
        rem,
        expected_worker_id="worker-xyz",
        expected_locked_at=now,
    )
    assert res.updated is False and res.lease_lost is True
    assert captured["params"]["id"] == f"eq.{rem.id}"
    assert captured["params"]["organization_id"] == f"eq.{rem.organization_id}"
    assert captured["params"]["business_id"] == f"eq.{rem.business_id}"
    assert captured["params"]["status"] == "eq.processing"
    assert captured["params"]["locked_by"] == "eq.worker-xyz"
    assert captured["params"]["locked_at"] == f"eq.{now.isoformat()}"


@pytest.mark.asyncio
async def test_ambiguous_timeout_is_not_retried_and_logs_zero_pii(caplog):
    """AMBIGUOUS_TIMEOUT and ReadTimeout go straight to manual-review failed state (never retried)."""
    assert classify_transport_error(httpx.ReadTimeout("read timed out")) == SmsErrorCategory.AMBIGUOUS_TIMEOUT
    assert classify_transport_error(httpx.RemoteProtocolError("closed")) == SmsErrorCategory.AMBIGUOUS_TIMEOUT
    assert classify_transport_error(httpx.ConnectTimeout("connect timed out")) == SmsErrorCategory.TRANSIENT

    class _AmbiguousProvider:
        provider_name = "noop"
        calls = 0

        async def send_sms(self, request: SmsSendRequest) -> SmsSendResult:
            self.calls += 1
            raise SmsProviderError(
                "gateway read timeout",
                category=SmsErrorCategory.AMBIGUOUS_TIMEOUT,
                error_code="provider_timeout_ambiguous",
            )

    caplog.set_level(logging.INFO)
    env = await _bootstrap_salon(owner_sms_phone=None, staff_phone=None)
    provider = _AmbiguousProvider()
    env["reminder_service"]._provider = provider

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
            customer_name="Ambiguous User",
            customer_phone="+12125550204",
        ),
        business_hours_override=env["hours_override"],
    )

    due_time = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=29)
    summary = await env["reminder_service"].process_due_reminders_once(
        worker_id="w-ambig", now=due_time
    )
    assert summary.ambiguous_timeout == 1
    assert summary.retried == 0
    assert summary.failed == 1
    assert provider.calls == 1

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    cust = next(r for r in reminders if r.recipient_type == ReminderRecipientType.CUSTOMER)
    assert cust.status == ReminderStatus.FAILED
    assert cust.provider_status == "manual_review_ambiguous_timeout"
    assert cust.next_retry_at is None
    assert cust.retry_count == 0

    # Subsequent tick must NOT re-claim or retry
    summary2 = await env["reminder_service"].process_due_reminders_once(
        worker_id="w-ambig", now=due_time + timedelta(minutes=5)
    )
    assert summary2.claimed == 0
    assert provider.calls == 1

    all_logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "+12125550204" not in all_logs
    assert "Precision Haircut" not in all_logs


@pytest.mark.asyncio
async def test_safe_pre_send_transient_failure_remains_retryable():
    """Pre-send TRANSIENT errors (e.g. ConnectTimeout / HTTP 429) remain retryable with backoff."""

    class _TransientThenOkProvider:
        provider_name = "noop"
        calls = 0

        async def send_sms(self, request: SmsSendRequest) -> SmsSendResult:
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectTimeout("connect timed out before transmission")
            return SmsSendResult(
                provider_name="noop",
                provider_message_id="noop-retry-ok",
                provider_status="simulated_accepted",
                simulated=True,
            )

    env = await _bootstrap_salon(owner_sms_phone=None, staff_phone=None)
    provider = _TransientThenOkProvider()
    env["reminder_service"]._provider = provider

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
            customer_name="Retry User",
            customer_phone="+12125550205",
        ),
        business_hours_override=env["hours_override"],
    )

    t1 = appt.start_at.astimezone(timezone.utc) - timedelta(minutes=29)
    s1 = await env["reminder_service"].process_due_reminders_once(worker_id="w-retry", now=t1)
    assert s1.retried == 1 and s1.failed == 0

    # After 60s backoff, second attempt succeeds
    s2 = await env["reminder_service"].process_due_reminders_once(
        worker_id="w-retry", now=t1 + timedelta(seconds=65)
    )
    assert s2.sent_simulated == 1
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_reconciliation_repairs_partial_and_missing_sets_idempotently():
    """Reconciliation repairs missing recipients independently without duplicating or recreating skipped rows."""
    env = await _bootstrap_salon(
        owner_sms_phone="+14155550210",
        staff_phone=None,  # Missing staff phone -> skipped_no_phone
    )
    _attach_upcoming_resolver(env)

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
            customer_name="Partial Repair",
            customer_phone="+12125550206",
        ),
        business_hours_override=env["hours_override"],
    )

    # Simulate partial failure: remove ONLY the owner reminder, leaving customer (pending) and staff (skipped_no_phone)
    owner_rem = next(
        r
        for r in env["reminder_repo"]._reminders.values()
        if r.appointment_id == appt.id and r.recipient_type == ReminderRecipientType.OWNER
    )
    del env["reminder_repo"]._reminders[owner_rem.id]
    del env["reminder_repo"]._dedup_keys[(appt.id, ReminderRecipientType.OWNER, 1)]

    # First reconciliation pass repairs ONLY the missing owner reminder in version 1
    rec1 = await env["reminder_service"].reconcile_missing_reminders_once()
    assert rec1.appointments_checked == 1
    assert rec1.reminders_repaired == 1

    reminders = await env["reminder_repo"].list_reminders_for_appointment(
        env["org_id"], env["biz_id"], appt.id
    )
    assert len(reminders) == 3
    by_type = {r.recipient_type: r for r in reminders}
    assert by_type[ReminderRecipientType.OWNER].appointment_version == 1
    assert by_type[ReminderRecipientType.OWNER].status == ReminderStatus.PENDING
    assert by_type[ReminderRecipientType.OWNER].recipient_phone == "+14155550210"
    # Intentionally skipped staff reminder must remain untouched
    assert by_type[ReminderRecipientType.STAFF].status == ReminderStatus.SKIPPED
    assert by_type[ReminderRecipientType.STAFF].skip_reason == "skipped_no_phone"

    # Duplicate reconciliation is strictly idempotent (0 repaired)
    rec2 = await env["reminder_service"].reconcile_missing_reminders_once()
    assert rec2.reminders_repaired == 0


@pytest.mark.asyncio
async def test_reconciliation_excludes_last_minute_past_cancelled_and_obsolete_versions():
    """Reconciliation ignores last-minute (<30m), past, cancelled, and obsolete appointment versions."""
    env = await _bootstrap_salon(owner_sms_phone=None, staff_phone="+447911123456")
    _attach_upcoming_resolver(env)

    d1 = (datetime.now(timezone.utc) + timedelta(days=3)).date()
    d2 = (datetime.now(timezone.utc) + timedelta(days=4)).date()

    # 1. Cancelled appointment -> must NOT be reconciled
    appt_cancel = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=d1,
            start_time="10:00",
            customer_name="Cancelled Appt",
            customer_phone="+12125550207",
        ),
        business_hours_override=env["hours_override"],
    )
    await env["salon_service"].cancel_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        appt_cancel.id,
        SalonAppointmentCancelRequest(cancellation_reason="No longer needed"),
    )

    # 2. Rescheduled appointment -> v1 is obsolete/cancelled, v2 is current; must NOT recreate v1
    appt_resched = await env["salon_service"].create_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        SalonAppointmentCreateRequest(
            service_id=env["svc"].id,
            staff_id=env["staff"].id,
            appointment_date=d1,
            start_time="12:00",
            customer_name="Rescheduled Appt",
            customer_phone="+12125550208",
        ),
        business_hours_override=env["hours_override"],
    )
    rescheduled = await env["salon_service"].reschedule_appointment(
        env["actor"],
        env["org_id"],
        env["biz_id"],
        appt_resched.id,
        SalonAppointmentRescheduleRequest(appointment_date=d2, start_time="15:00"),
        business_hours_override=env["hours_override"],
    )

    # 3. Last-minute / past appointment (evaluate at `now = rescheduled.start_at - 20 minutes`)
    rec_last_min = await env["reminder_service"].reconcile_missing_reminders_once(
        now=rescheduled.start_at - timedelta(minutes=20)
    )
    assert rec_last_min.appointments_checked == 0
    assert rec_last_min.reminders_repaired == 0

    # Normal-time reconciliation must NOT recreate cancelled appt or obsolete v1
    rec_normal = await env["reminder_service"].reconcile_missing_reminders_once()
    assert rec_normal.reminders_repaired == 0

    # Verify worker wrapper runs reconciliation cleanly without error
    worker = SmsReminderWorker(settings=env["settings"], service=env["reminder_service"])
    w_rec = await worker.run_reconciliation_once()
    assert w_rec.reminders_repaired == 0
