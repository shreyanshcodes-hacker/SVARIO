"""Stage 12C.2 — Comprehensive Mocked Tests for MSG91 DLR Webhooks & SMS Logs Reconciliation.

NEVER sends SMS and NEVER contacts the real MSG91 API.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
import httpx
import pytest
from app.core.config import Settings, get_settings
from app.main import create_app
from app.modules.notifications.dlr import (
    DeliveryOutcome,
    DeliveryReceiptService,
    Msg91LogsReconciler,
    map_msg91_dlr_status,
    parse_msg91_timestamp,
    parse_msg91_webhook_payload,
    validate_msg91_logs_date_window,
)
from app.modules.notifications.msg91 import Msg91SmsProvider
from app.modules.notifications.repository import InMemoryReminderRepository
from app.modules.notifications.schemas import (
    AppointmentSmsReminder,
    ReminderRecipientType,
    ReminderStatus,
)
from app.routes.webhooks import get_dlr_service


def _seed_sent_reminder(
    repo: InMemoryReminderRepository,
    *,
    provider_message_id: str = "346a7b8c9d0e1f2a3b4c",
    recipient_phone: str = "+919876543210",
    status: ReminderStatus = ReminderStatus.SENT,
    org_id: Optional[UUID] = None,
    biz_id: Optional[UUID] = None,
    sent_at: Optional[datetime] = None,
) -> AppointmentSmsReminder:
    now = datetime.now(timezone.utc)
    rem = AppointmentSmsReminder(
        id=uuid4(),
        organization_id=org_id or uuid4(),
        business_id=biz_id or uuid4(),
        appointment_id=uuid4(),
        appointment_version=1,
        appointment_start_at=now + timedelta(minutes=30),
        recipient_type=ReminderRecipientType.CUSTOMER,
        recipient_phone=recipient_phone,
        recipient_name="Test Customer",
        scheduled_for=now,
        status=status,
        template_key="customer_30m",
        provider_name="msg91",
        provider_message_id=provider_message_id,
        provider_status="accepted",
        retry_count=0,
        max_retries=3,
        sent_at=sent_at or now,
        created_at=now,
        updated_at=now,
    )
    repo._reminders[rem.id] = rem
    return rem


def _build_webhook_client(
    repo: InMemoryReminderRepository,
    *,
    webhook_secret: Optional[str] = "super-secret-dlr-token-123",
    max_body_bytes: int = 65536,
) -> TestClient:
    app = create_app()
    test_settings = Settings(
        _env_file=None,
        SVARIO_ENV="test",
        SMS_REMINDERS_ENABLED=False,
        SMS_PROVIDER="noop",
        MSG91_WEBHOOK_SECRET=webhook_secret,
        MSG91_WEBHOOK_TIMEZONE="Asia/Kolkata",
        MSG91_WEBHOOK_MAX_BODY_BYTES=max_body_bytes,
        MSG91_LOGS_RECONCILIATION_ENABLED=False,
    )
    dlr_svc = DeliveryReceiptService(repo=repo)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_dlr_service] = lambda: dlr_svc
    return TestClient(app)


def test_stage12c2_defaults_remain_disabled_and_noop():
    """SMS reminders, MSG91 logs reconciliation, and webhook secret remain safe/disabled by default."""
    defaults = Settings(_env_file=None)
    assert defaults.sms_reminders_enabled is False
    assert defaults.sms_provider == "noop"
    assert defaults.msg91_logs_reconciliation_enabled is False
    assert defaults.msg91_webhook_secret is None


def test_webhook_auth_missing_invalid_unconfigured_oversized_and_malformed():
    """Tests: missing auth config (503), missing header (401), invalid secret (403), 415, 413, 400."""
    repo = InMemoryReminderRepository()

    # 1. Missing webhook secret config -> 503 fail closed
    client_no_cfg = _build_webhook_client(repo, webhook_secret=None)
    r_503 = client_no_cfg.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "anything", "Content-Type": "application/json"},
        json=[{"requestId": "req-1", "report": [{"number": "919876543210", "status": "1"}]}],
    )
    assert r_503.status_code == 503

    client = _build_webhook_client(repo, webhook_secret="valid-secret-xyz", max_body_bytes=1024)

    # 2. Missing header -> 401
    r_401 = client.post(
        "/api/v1/webhooks/sms/msg91",
        json=[{"requestId": "req-1", "report": [{"number": "919876543210", "status": "1"}]}],
    )
    assert r_401.status_code == 401

    # 3. Invalid secret -> 403
    r_403 = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "wrong-secret"},
        json=[{"requestId": "req-1", "report": [{"number": "919876543210", "status": "1"}]}],
    )
    assert r_403.status_code == 403

    # 4. Wrong content-type -> 415
    r_415 = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "valid-secret-xyz", "Content-Type": "text/plain"},
        content="not json",
    )
    assert r_415.status_code == 415

    # 5. Oversized payload -> 413
    r_413 = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "valid-secret-xyz", "Content-Type": "application/json"},
        content='{"pad":"' + ("x" * 2000) + '"}',
    )
    assert r_413.status_code == 413

    # 6. Malformed payload -> 400
    r_400 = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "valid-secret-xyz"},
        json={"missing": "requestId_and_report"},
    )
    assert r_400.status_code == 400


def test_valid_authenticated_callback_updates_delivered_with_zero_pii_and_zero_outbound_sms(
    monkeypatch, caplog
):
    """Valid callback transitions sent->delivered, returns generic body, logs zero PII, sends zero SMS."""
    async def _forbid_send(*args, **kwargs):
        raise AssertionError("Webhook handling must NEVER send outbound SMS!")

    monkeypatch.setattr(Msg91SmsProvider, "send_sms", _forbid_send)
    monkeypatch.setattr(httpx.AsyncClient, "post", _forbid_send)
    caplog.set_level(logging.INFO)

    repo = InMemoryReminderRepository()
    rem = _seed_sent_reminder(
        repo,
        provider_message_id="msg91-req-1001",
        recipient_phone="+919876543210",
    )
    client = _build_webhook_client(repo, webhook_secret="dlr-secret-999")

    resp = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "dlr-secret-999"},
        json=[
            {
                "requestId": "msg91-req-1001",
                "organization_id": str(uuid4()),  # Spoofed tenant ID — MUST be ignored
                "report": [
                    {
                        "number": "919876543210",
                        "status": "1",
                        "desc": "DELIVERED",
                        "date": "2026-11-25 14:05:00",
                    }
                ],
            }
        ],
    )
    assert resp.status_code == 200
    # Generic response leaks zero tenant IDs or reminder IDs
    assert resp.json() == {"status": "received"}
    assert str(rem.organization_id) not in resp.text
    assert str(rem.id) not in resp.text

    updated = repo._reminders[rem.id]
    assert updated.status == ReminderStatus.DELIVERED
    assert updated.provider_status == "delivered"
    assert updated.delivered_at is not None
    # 14:05 IST == 08:35 UTC
    assert updated.delivered_at == datetime(2026, 11, 25, 8, 35, 0, tzinfo=timezone.utc)
    assert updated.retry_count == 0

    # Zero raw PII or secrets in logs
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "919876543210" not in logs
    assert "dlr-secret-999" not in logs


def test_unknown_request_id_recipient_mismatch_and_cross_tenant_isolation():
    """Unknown requestId creates no rows; recipient mismatch & cross-tenant collisions update nothing."""
    repo = InMemoryReminderRepository()
    org_a, biz_a = uuid4(), uuid4()
    org_b, biz_b = uuid4(), uuid4()
    rem_a = _seed_sent_reminder(
        repo,
        provider_message_id="req-tenant-a",
        recipient_phone="+919876543210",
        org_id=org_a,
        biz_id=biz_a,
    )
    rem_b = _seed_sent_reminder(
        repo,
        provider_message_id="req-tenant-b",
        recipient_phone="+919876543299",
        org_id=org_b,
        biz_id=biz_b,
    )
    client = _build_webhook_client(repo, webhook_secret="sec-iso")

    # 1. Unknown provider request ID -> 200 generic, 0 new rows
    r_unk = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "sec-iso"},
        json=[{"requestId": "req-does-not-exist", "report": [{"number": "919876543210", "status": "1"}]}],
    )
    assert r_unk.status_code == 200
    assert len(repo._reminders) == 2

    # 2. Recipient mismatch -> does NOT update rem_a or rem_b
    r_mis = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "sec-iso"},
        json=[{"requestId": "req-tenant-a", "report": [{"number": "919999999999", "status": "1"}]}],
    )
    assert r_mis.status_code == 200
    assert repo._reminders[rem_a.id].status == ReminderStatus.SENT
    assert repo._reminders[rem_b.id].status == ReminderStatus.SENT

    # 3. Multiple matching records for same provider_message_id -> fails safely, updates 0 rows
    rem_dup = _seed_sent_reminder(
        repo,
        provider_message_id="req-tenant-b",
        recipient_phone="+919876543299",
        org_id=org_a,
        biz_id=biz_a,
    )
    r_amb = client.post(
        "/api/v1/webhooks/sms/msg91",
        headers={"X-Webhook-Secret": "sec-iso"},
        json=[{"requestId": "req-tenant-b", "report": [{"number": "919876543299", "status": "1"}]}],
    )
    assert r_amb.status_code == 200
    assert repo._reminders[rem_b.id].status == ReminderStatus.SENT
    assert repo._reminders[rem_dup.id].status == ReminderStatus.SENT


@pytest.mark.asyncio
async def test_duplicate_concurrent_out_of_order_unknown_and_missing_timestamp_handling():
    """Tests deduplication, concurrency, out-of-order protection, unknown status, and missing/invalid timestamps."""
    repo = InMemoryReminderRepository()
    svc = DeliveryReceiptService(repo=repo)
    rem = _seed_sent_reminder(repo, provider_message_id="req-order-1", recipient_phone="+919876543210")

    # 1. Invalid timestamp & invalid timezone never fabricate timestamps
    dt_bad, ok_bad = parse_msg91_timestamp("not-a-date", configured_timezone="Asia/Kolkata")
    assert dt_bad is None and ok_bad is False
    dt_tz, ok_tz = parse_msg91_timestamp("2026-11-25 14:00:00", configured_timezone="Invalid/Zone")
    assert dt_tz is None and ok_tz is False

    # 2. Unknown provider status preserves `sent`
    unk_receipt = parse_msg91_webhook_payload(
        [{"requestId": "req-order-1", "report": [{"number": "919876543210", "status": "99", "desc": "MYSTERY"}]}]
    )[0]
    assert unk_receipt.outcome == DeliveryOutcome.UNKNOWN
    out_unk = await svc.process_receipt(unk_receipt)
    assert out_unk.status == "ignored" and out_unk.ignored_reason == "unknown_provider_status"
    assert repo._reminders[rem.id].status == ReminderStatus.SENT

    # 3. Concurrent duplicate `delivered` callbacks -> exactly 1 applied, 1 duplicate
    deliv_receipt = parse_msg91_webhook_payload(
        [
            {
                "requestId": "req-order-1",
                "report": [{"number": "919876543210", "status": "1", "desc": "DELIVERED", "date": "2026-11-25 14:10:00"}],
            }
        ]
    )[0]
    r1, r2 = await asyncio.gather(svc.process_receipt(deliv_receipt), svc.process_receipt(deliv_receipt))
    statuses = sorted([r1.status, r2.status])
    assert statuses == ["applied", "duplicate"]
    delivered_at_first = repo._reminders[rem.id].delivered_at

    # 4. Late `failed` event after `delivered` MUST NOT regress `delivered`
    late_fail = parse_msg91_webhook_payload(
        [
            {
                "requestId": "req-order-1",
                "report": [{"number": "919876543210", "status": "2", "desc": "FAILED", "date": "2026-11-25 14:15:00"}],
            }
        ]
    )[0]
    out_late_fail = await svc.process_receipt(late_fail)
    assert out_late_fail.status == "ignored" and out_late_fail.ignored_reason == "already_delivered"
    assert repo._reminders[rem.id].status == ReminderStatus.DELIVERED
    assert repo._reminders[rem.id].delivered_at == delivered_at_first

    # 5. Missing timestamp after an existing terminal `failed` event -> ordering uncertain, preserve state
    rem2 = _seed_sent_reminder(repo, provider_message_id="req-order-2", recipient_phone="+919876543210")
    fail_ts = parse_msg91_webhook_payload(
        [
            {
                "requestId": "req-order-2",
                "report": [{"number": "919876543210", "status": "16", "desc": "REJECTED", "date": "2026-11-25 14:10:00"}],
            }
        ]
    )[0]
    assert (await svc.process_receipt(fail_ts)).status == "applied"
    assert repo._reminders[rem2.id].status == ReminderStatus.FAILED
    assert repo._reminders[rem2.id].provider_status == "rejected"

    no_ts_deliv = parse_msg91_webhook_payload(
        [{"requestId": "req-order-2", "report": [{"number": "919876543210", "status": "1", "desc": "DELIVERED"}]}]
    )[0]
    out_no_ts = await svc.process_receipt(no_ts_deliv)
    assert out_no_ts.status == "ignored"
    assert out_no_ts.ignored_reason == "ordering_uncertain_missing_timestamp"
    assert repo._reminders[rem2.id].status == ReminderStatus.FAILED


@pytest.mark.asyncio
async def test_msg91_logs_api_reconciliation_and_date_window_validation(monkeypatch):
    """Logs API enforces 3-day date window, stays disabled by default, and applies monotonic DLR updates."""
    # Date-window validation
    today = date(2026, 11, 25)
    validate_msg91_logs_date_window(date(2026, 11, 22), today, today=today)
    with pytest.raises(ValueError):
        validate_msg91_logs_date_window(date(2026, 11, 20), today, today=today)
    with pytest.raises(ValueError):
        validate_msg91_logs_date_window(date(2026, 11, 25), date(2026, 11, 24), today=today)

    repo = InMemoryReminderRepository()
    rem = _seed_sent_reminder(repo, provider_message_id="req-logs-555", recipient_phone="+919876543210")

    # Disabled by default -> makes zero HTTP requests
    async def _forbid_http(*args, **kwargs):
        raise AssertionError("Logs API must not be called when disabled!")

    monkeypatch.setattr(httpx.AsyncClient, "post", _forbid_http)
    disabled_reconciler = Msg91LogsReconciler(
        settings=Settings(_env_file=None, MSG91_LOGS_RECONCILIATION_ENABLED=False),
        repo=repo,
    )
    res_dis = await disabled_reconciler.reconcile_recent_unresolved_once()
    assert res_dis.skipped_disabled is True

    # Enabled with mocked MSG91 Logs API response
    captured_params: Dict[str, Any] = {}

    class _FakeLogsResp:
        status_code = 200

        def json(self) -> Dict[str, Any]:
            return {
                "type": "success",
                "data": [
                    {
                        "requestId": "req-logs-555",
                        "telNum": "919876543210",
                        "status": "DELIVERED",
                        "statusCode": "1",
                        "deliveryTime": "2026-11-25 14:20:00",
                    }
                ],
            }

    async def _mock_logs_post(self, url, headers=None, params=None):
        captured_params["url"] = url
        captured_params["params"] = params
        return _FakeLogsResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_logs_post)

    reconciler = Msg91LogsReconciler(
        settings=Settings(
            _env_file=None,
            MSG91_LOGS_RECONCILIATION_ENABLED=True,
            MSG91_API_KEY="mock-logs-authkey",
            MSG91_WEBHOOK_TIMEZONE="Asia/Kolkata",
        ),
        repo=repo,
    )
    summary = await reconciler.reconcile_recent_unresolved_once(
        now=datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc)
    )
    assert summary.skipped_disabled is False
    assert summary.checked == 1
    assert summary.applied == 1
    assert captured_params["url"] == "https://control.msg91.com/api/v5/report/logs/p/sms"
    assert captured_params["params"]["requestId"] == "req-logs-555"
    assert repo._reminders[rem.id].status == ReminderStatus.DELIVERED
