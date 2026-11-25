"""Stage 12C.2: MSG91 Delivery Receipt (DLR) Handling & SMS Logs Reconciliation.

Verified against official MSG91 documentation:
- https://docs.msg91.com/sms/send-sms (Webhook / DLR push payload & custom headers)
- https://docs.msg91.com/sms/sms-logs (`POST https://control.msg91.com/api/v5/report/logs/p/sms`)

Security & Integrity Guarantees:
- Webhook authentication uses constant-time `hmac.compare_digest` on backend-only
  `MSG91_WEBHOOK_SECRET`; fails closed if secret is unconfigured.
- Resolves reminders exclusively by `(provider_name, provider_message_id)`; never trusts
  callback-supplied tenant or appointment IDs.
- Verifies recipient correlation when the provider supplies a mobile number.
- Deterministic non-PII SHA-256 event fingerprint for database-level deduplication.
- Strict monotonic state-transition policy: `delivered` never regresses; older or
  unorderable events never overwrite newer confirmed outcomes; `unknown` never mutates.
- Never triggers SMS retries or outbound SMS sends.
- Never logs phone numbers, message bodies, secrets, or raw callback payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import hashlib
import hmac
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import httpx
from pydantic import BaseModel, ConfigDict
from app.core.config import Settings
from app.modules.notifications.repository import ReminderRepositoryProtocol
from app.modules.notifications.schemas import (
    AppointmentSmsReminder,
    ReminderStatus,
    normalize_e164_phone,
)

logger = logging.getLogger("svario.notifications.dlr")

_DIGITS_ONLY_REGEX = re.compile(r"[^0-9]")

# Verified MSG91 SMS DLR numeric status codes & descriptions:
# 1 = Delivered, 2 = Failed, 9 = NDNC, 16/25 = Rejected (DLT/content), 17 = Blocked
_MSG91_CODE_MAP: Dict[str, str] = {
    "1": "delivered",
    "2": "failed",
    "9": "rejected",
    "16": "rejected",
    "17": "rejected",
    "25": "rejected",
}

_MSG91_DESC_MAP: Dict[str, str] = {
    "DELIVERED": "delivered",
    "DELIVRD": "delivered",
    "FAILED": "failed",
    "UNDELIVERED": "failed",
    "UNDELIV": "failed",
    "EXPIRED": "failed",
    "REJECTED": "rejected",
    "REJECTD": "rejected",
    "NDNC": "rejected",
    "DND": "rejected",
    "BLOCKED": "rejected",
    "BLOCKED NUMBER": "rejected",
}


class DeliveryOutcome(str, Enum):
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class NormalizedDeliveryReceipt(BaseModel):
    """Sanitized, normalized delivery event parsed from MSG91 webhook or Logs API."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    provider_message_id: str
    recipient_mobile: Optional[str] = None  # Digits only (no `+`); never logged or persisted in events
    outcome: DeliveryOutcome
    raw_status_code: Optional[str] = None
    provider_event_at: Optional[datetime] = None
    timestamp_valid: bool = False
    event_fingerprint: str
    source: str = "webhook"


class DeliveryEventRecord(BaseModel):
    """Non-PII delivery receipt audit/deduplication record."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    organization_id: UUID
    business_id: UUID
    reminder_id: UUID
    provider_name: str
    provider_message_id: str
    event_fingerprint: str
    source: str
    normalized_outcome: DeliveryOutcome
    raw_status_code: Optional[str] = None
    provider_event_at: Optional[datetime] = None
    applied: bool = False
    ignored_reason: Optional[str] = None
    received_at: datetime


@dataclass(frozen=True)
class DlrProcessingOutcome:
    status: str  # applied | duplicate | ignored | not_found | ambiguous_match | recipient_mismatch
    ignored_reason: Optional[str] = None


@dataclass(frozen=True)
class LogsReconciliationSummary:
    checked: int = 0
    applied: int = 0
    ignored: int = 0
    skipped_disabled: bool = False


def verify_msg91_webhook_secret(
    provided_secret: Optional[str],
    configured_secret: Optional[str],
) -> Tuple[bool, str]:
    """Constant-time verification of MSG91 custom webhook secret header (fail-closed)."""
    expected = (configured_secret or "").strip()
    if not expected or "placeholder" in expected.lower():
        return False, "webhook_secret_not_configured"
    supplied = (provided_secret or "").strip()
    if not supplied:
        return False, "missing_webhook_secret"
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        return False, "invalid_webhook_secret"
    return True, "ok"


def map_msg91_dlr_status(
    raw_code: Optional[Any],
    raw_desc: Optional[Any] = None,
) -> DeliveryOutcome:
    """Map verified MSG91 DLR status codes/descriptions to normalized outcomes."""
    code_str = str(raw_code).strip() if raw_code is not None else ""
    if code_str in _MSG91_CODE_MAP:
        return DeliveryOutcome(_MSG91_CODE_MAP[code_str])

    desc_str = str(raw_desc).strip().upper() if raw_desc is not None else ""
    if desc_str in _MSG91_DESC_MAP:
        return DeliveryOutcome(_MSG91_DESC_MAP[desc_str])

    # Some Logs API payloads put the textual status inside `status` directly
    if code_str.upper() in _MSG91_DESC_MAP:
        return DeliveryOutcome(_MSG91_DESC_MAP[code_str.upper()])

    return DeliveryOutcome.UNKNOWN


def parse_msg91_timestamp(
    raw_value: Optional[Any],
    *,
    configured_timezone: str = "Asia/Kolkata",
) -> Tuple[Optional[datetime], bool]:
    """Validate and normalize an MSG91 timestamp to UTC without fabricating times."""
    if raw_value is None:
        return None, False
    cleaned = str(raw_value).strip()
    if not cleaned:
        return None, False

    try:
        tz = ZoneInfo(configured_timezone.strip())
    except ZoneInfoNotFoundError:
        return None, False

    # Try ISO-8601 first (handles `Z`, `+05:30`, `YYYY-MM-DDTHH:MM:SS`, `YYYY-MM-DD HH:MM:SS`)
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None, False

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc), True


def _normalize_digits(raw_phone: Optional[Any]) -> Optional[str]:
    if raw_phone is None:
        return None
    digits = _DIGITS_ONLY_REGEX.sub("", str(raw_phone).strip())
    if len(digits) < 7 or len(digits) > 15:
        return None
    return digits


def compute_dlr_fingerprint(
    *,
    provider_name: str,
    provider_message_id: str,
    outcome: DeliveryOutcome,
    raw_status_code: Optional[str],
    provider_event_at: Optional[datetime],
    recipient_mobile: Optional[str],
) -> str:
    """Compute a deterministic 64-char SHA-256 fingerprint without storing raw PII."""
    recipient_hash = (
        hashlib.sha256(recipient_mobile.encode("utf-8")).hexdigest()[:16]
        if recipient_mobile
        else "none"
    )
    ts_part = provider_event_at.astimezone(timezone.utc).isoformat() if provider_event_at else "no_ts"
    canonical = "|".join(
        [
            provider_name.strip().lower(),
            provider_message_id.strip(),
            outcome.value,
            (raw_status_code or "").strip(),
            ts_part,
            recipient_hash,
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_msg91_webhook_payload(
    payload: Any,
    *,
    configured_timezone: str = "Asia/Kolkata",
) -> List[NormalizedDeliveryReceipt]:
    """Parse and strictly validate official MSG91 DLR JSON webhook payload.

    Accepts either:
    - Standard MSG91 array of request objects: `[{"requestId": "...", "report": [{...}]}]`
    - Single request object: `{"requestId": "...", "report": [{...}]}`
    Raises `ValueError` on malformed structure or missing required fields.
    """
    if isinstance(payload, Mapping):
        batches = [payload]
    elif isinstance(payload, list) and len(payload) > 0:
        batches = payload
    else:
        raise ValueError("MSG91 webhook payload must be a JSON object or non-empty array.")

    receipts: List[NormalizedDeliveryReceipt] = []
    for item in batches:
        if not isinstance(item, Mapping):
            raise ValueError("Each MSG91 webhook batch entry must be a JSON object.")

        request_id = str(item.get("requestId") or item.get("request_id") or "").strip()
        if not request_id or len(request_id) > 128:
            raise ValueError("MSG91 webhook entry missing valid 'requestId'.")

        report = item.get("report")
        if not isinstance(report, list) or len(report) == 0:
            raise ValueError("MSG91 webhook entry missing non-empty 'report' array.")

        for rep in report:
            if not isinstance(rep, Mapping):
                raise ValueError("Each MSG91 report entry must be a JSON object.")
            raw_status = rep.get("status")
            raw_desc = rep.get("desc") if "desc" in rep else rep.get("description")
            if raw_status is None and raw_desc is None:
                raise ValueError("MSG91 report entry missing 'status' and 'desc'.")

            raw_code_str = str(raw_status).strip() if raw_status is not None else None
            outcome = map_msg91_dlr_status(raw_status, raw_desc)
            mobile = _normalize_digits(rep.get("number") or rep.get("mobile") or rep.get("telNum"))
            event_dt, ts_valid = parse_msg91_timestamp(
                rep.get("date") or rep.get("statusUpdatedAt"),
                configured_timezone=configured_timezone,
            )
            fingerprint = compute_dlr_fingerprint(
                provider_name="msg91",
                provider_message_id=request_id,
                outcome=outcome,
                raw_status_code=raw_code_str,
                provider_event_at=event_dt,
                recipient_mobile=mobile,
            )
            receipts.append(
                NormalizedDeliveryReceipt(
                    provider_name="msg91",
                    provider_message_id=request_id,
                    recipient_mobile=mobile,
                    outcome=outcome,
                    raw_status_code=raw_code_str,
                    provider_event_at=event_dt,
                    timestamp_valid=ts_valid,
                    event_fingerprint=fingerprint,
                    source="webhook",
                )
            )
    return receipts


class DeliveryReceiptService:
    """Applies verified, deduplicated, monotonic DLR transitions to reminder records."""

    def __init__(self, *, repo: ReminderRepositoryProtocol) -> None:
        self._repo = repo

    async def process_receipt(
        self,
        receipt: NormalizedDeliveryReceipt,
        *,
        now: Optional[datetime] = None,
    ) -> DlrProcessingOutcome:
        """Correlate, deduplicate, and apply a single normalized delivery receipt."""
        ref_now = now or datetime.now(timezone.utc)

        # 1. Resolve strictly by (provider_name, provider_message_id) — never callback tenant IDs
        matches: List[AppointmentSmsReminder] = (
            await self._repo.find_reminders_by_provider_message_id(
                receipt.provider_name, receipt.provider_message_id
            )
        )
        if not matches:
            logger.info(
                "dlr_unknown_provider_message_id provider=%s source=%s",
                receipt.provider_name,
                receipt.source,
            )
            return DlrProcessingOutcome(status="not_found", ignored_reason="unknown_provider_message_id")

        if len(matches) > 1:
            logger.warning(
                "dlr_ambiguous_provider_message_id provider=%s match_count=%s",
                receipt.provider_name,
                len(matches),
            )
            return DlrProcessingOutcome(status="ambiguous_match", ignored_reason="multiple_matching_reminders")

        reminder = matches[0]

        # 2. Verify recipient correlation when provider supplies a mobile number
        if receipt.recipient_mobile is not None:
            stored_digits = _normalize_digits(reminder.recipient_phone)
            if stored_digits != receipt.recipient_mobile:
                logger.warning(
                    "dlr_recipient_mismatch reminder_id=%s provider=%s",
                    reminder.id,
                    receipt.provider_name,
                )
                return DlrProcessingOutcome(status="recipient_mismatch", ignored_reason="recipient_mismatch")

        # 3. Determine monotonic state-transition decision BEFORE recording event
        applied = False
        ignored_reason: Optional[str] = None
        new_status: Optional[ReminderStatus] = None
        new_provider_status: Optional[str] = None
        new_delivered_at: Optional[datetime] = None
        new_last_error: Optional[str] = None

        if receipt.outcome == DeliveryOutcome.UNKNOWN:
            ignored_reason = "unknown_provider_status"
        elif reminder.status == ReminderStatus.DELIVERED:
            # Terminal positive state NEVER regresses
            ignored_reason = "already_delivered"
        elif reminder.status in {ReminderStatus.CANCELLED, ReminderStatus.SKIPPED, ReminderStatus.PENDING}:
            ignored_reason = f"invalid_source_state_{reminder.status.value}"
        else:
            last_event_at = await self._repo.get_latest_applied_delivery_event_at(reminder.id)
            if last_event_at is not None:
                if receipt.provider_event_at is None:
                    # Ordering cannot be established reliably -> preserve existing state
                    ignored_reason = "ordering_uncertain_missing_timestamp"
                elif receipt.provider_event_at <= last_event_at:
                    ignored_reason = "stale_event_timestamp"

            if ignored_reason is None:
                if receipt.outcome == DeliveryOutcome.DELIVERED:
                    new_status = ReminderStatus.DELIVERED
                    new_provider_status = "delivered"
                    new_delivered_at = receipt.provider_event_at or ref_now
                    applied = True
                elif receipt.outcome == DeliveryOutcome.FAILED:
                    new_status = ReminderStatus.FAILED
                    new_provider_status = "failed"
                    new_last_error = f"dlr_failed_{receipt.raw_status_code or 'unknown'}"
                    applied = True
                elif receipt.outcome == DeliveryOutcome.REJECTED:
                    new_status = ReminderStatus.FAILED
                    new_provider_status = "rejected"
                    new_last_error = f"dlr_rejected_{receipt.raw_status_code or 'unknown'}"
                    applied = True

        # 4. Atomic database-level deduplication via UNIQUE (provider_name, event_fingerprint)
        event_record = DeliveryEventRecord(
            id=uuid4(),
            organization_id=reminder.organization_id,
            business_id=reminder.business_id,
            reminder_id=reminder.id,
            provider_name=receipt.provider_name,
            provider_message_id=receipt.provider_message_id,
            event_fingerprint=receipt.event_fingerprint,
            source=receipt.source,
            normalized_outcome=receipt.outcome,
            raw_status_code=receipt.raw_status_code,
            provider_event_at=receipt.provider_event_at,
            applied=applied,
            ignored_reason=ignored_reason,
            received_at=ref_now,
        )
        inserted = await self._repo.record_delivery_event_if_new(event_record)
        if not inserted:
            return DlrProcessingOutcome(status="duplicate", ignored_reason="duplicate_event_fingerprint")

        # 5. Apply monotonic status update if eligible (never touches retry_count or resends SMS)
        if applied and new_status is not None:
            updated = await self._repo.apply_delivery_receipt_update(
                reminder_id=reminder.id,
                organization_id=reminder.organization_id,
                business_id=reminder.business_id,
                new_status=new_status,
                provider_status=new_provider_status or receipt.outcome.value,
                delivered_at=new_delivered_at,
                last_error=new_last_error,
            )
            if not updated:
                return DlrProcessingOutcome(status="ignored", ignored_reason="already_delivered_concurrent")
            logger.info(
                "dlr_applied reminder_id=%s provider=%s outcome=%s source=%s",
                reminder.id,
                receipt.provider_name,
                receipt.outcome.value,
                receipt.source,
            )
            return DlrProcessingOutcome(status="applied")

        logger.info(
            "dlr_ignored reminder_id=%s provider=%s outcome=%s reason=%s",
            reminder.id,
            receipt.provider_name,
            receipt.outcome.value,
            ignored_reason,
        )
        return DlrProcessingOutcome(status="ignored", ignored_reason=ignored_reason)


def validate_msg91_logs_date_window(
    start_date: date,
    end_date: date,
    *,
    today: Optional[date] = None,
) -> None:
    """Enforce MSG91 SMS Logs API documented 3-day date-window constraints."""
    ref_today = today or datetime.now(timezone.utc).date()
    if end_date < start_date:
        raise ValueError("MSG91 logs endDate must not precede startDate.")
    if (end_date - start_date).days > 3:
        raise ValueError("MSG91 logs date window cannot exceed 3 days.")
    if (ref_today - start_date).days > 3:
        raise ValueError("MSG91 logs startDate must be within the last 3 days.")


class Msg91LogsReconciler:
    """Optional, disabled-by-default MSG91 SMS Logs API reconciler.

    Endpoint: `POST https://control.msg91.com/api/v5/report/logs/p/sms`
    Never resends SMS and applies the exact same monotonic DLR rules.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        repo: ReminderRepositoryProtocol,
        dlr_service: Optional[DeliveryReceiptService] = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._dlr_service = dlr_service or DeliveryReceiptService(repo=repo)
        self._timeout = httpx.Timeout(
            connect=settings.msg91_connect_timeout_seconds,
            read=settings.msg91_read_timeout_seconds,
            write=settings.msg91_write_timeout_seconds,
            pool=settings.msg91_connect_timeout_seconds,
        )

    async def reconcile_recent_unresolved_once(
        self,
        *,
        now: Optional[datetime] = None,
        limit: int = 25,
    ) -> LogsReconciliationSummary:
        if not self._settings.msg91_logs_reconciliation_enabled:
            return LogsReconciliationSummary(skipped_disabled=True)

        api_key = (self._settings.msg91_api_key or "").strip()
        if not api_key or "placeholder" in api_key.lower():
            logger.warning("msg91_logs_reconcile_skipped reason=missing_api_key")
            return LogsReconciliationSummary()

        ref_now = now or datetime.now(timezone.utc)
        since = ref_now - timedelta(days=3)
        start_d = since.date()
        end_d = ref_now.date()
        validate_msg91_logs_date_window(start_d, end_d, today=end_d)

        unresolved = await self._repo.list_unresolved_sent_reminders(
            "msg91",
            since=since,
            limit=max(1, min(int(limit), 50)),
        )

        applied = 0
        ignored = 0
        for rem in unresolved:
            if not rem.provider_message_id:
                continue
            try:
                receipts = await self._fetch_logs_for_request_id(
                    api_key=api_key,
                    request_id=rem.provider_message_id,
                    start_date=start_d,
                    end_date=end_d,
                )
            except Exception as exc:
                logger.warning(
                    "msg91_logs_fetch_error reminder_id=%s error_type=%s",
                    rem.id,
                    type(exc).__name__,
                )
                continue

            for rcpt in receipts:
                outcome = await self._dlr_service.process_receipt(rcpt, now=ref_now)
                if outcome.status == "applied":
                    applied += 1
                else:
                    ignored += 1

        return LogsReconciliationSummary(
            checked=len(unresolved),
            applied=applied,
            ignored=ignored,
            skipped_disabled=False,
        )

    async def _fetch_logs_for_request_id(
        self,
        *,
        api_key: str,
        request_id: str,
        start_date: date,
        end_date: date,
    ) -> List[NormalizedDeliveryReceipt]:
        validate_msg91_logs_date_window(start_date, end_date, today=end_date)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._settings.msg91_logs_api_url.strip(),
                headers={
                    "accept": "application/json",
                    "authkey": api_key,
                },
                params={
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "requestId": request_id,
                    "fields": "requestDate,status,deliveryDate,deliveryTime,telNum,requestId,statusCode,failureReason",
                    "limit": "10",
                },
            )
            if resp.status_code != 200:
                return []
            body = resp.json()

        if not isinstance(body, Mapping):
            return []
        if str(body.get("type") or "").strip().lower() == "error":
            return []

        rows = body.get("data")
        if not isinstance(rows, list):
            return []

        receipts: List[NormalizedDeliveryReceipt] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            returned_req_id = str(row.get("requestId") or "").strip()
            if returned_req_id != request_id:
                continue
            raw_status_code = row.get("statusCode") if row.get("statusCode") is not None else row.get("status")
            raw_desc = row.get("status")
            outcome = map_msg91_dlr_status(raw_status_code, raw_desc)
            mobile = _normalize_digits(row.get("telNum"))
            raw_dt = row.get("deliveryTime") or row.get("deliveryDate") or row.get("requestDate")
            event_dt, ts_valid = parse_msg91_timestamp(
                raw_dt,
                configured_timezone=self._settings.msg91_webhook_timezone,
            )
            fp = compute_dlr_fingerprint(
                provider_name="msg91",
                provider_message_id=returned_req_id,
                outcome=outcome,
                raw_status_code=str(raw_status_code).strip() if raw_status_code is not None else None,
                provider_event_at=event_dt,
                recipient_mobile=mobile,
            )
            receipts.append(
                NormalizedDeliveryReceipt(
                    provider_name="msg91",
                    provider_message_id=returned_req_id,
                    recipient_mobile=mobile,
                    outcome=outcome,
                    raw_status_code=str(raw_status_code).strip() if raw_status_code is not None else None,
                    provider_event_at=event_dt,
                    timestamp_valid=ts_valid,
                    event_fingerprint=fp,
                    source="logs_reconciliation",
                )
            )
        return receipts
