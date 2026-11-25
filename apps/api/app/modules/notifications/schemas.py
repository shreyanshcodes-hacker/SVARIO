"""Schemas, phone normalization, and transactional templates for Stage 12B SMS Reminders."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Dict, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field

_E164_REGEX = re.compile(r"^\+[1-9][0-9]{6,14}$")
_COUNTRY_CODE_REGEX = re.compile(r"^\+[1-9][0-9]{0,3}$")
_STRIP_CHARS_REGEX = re.compile(r"[\s\-\(\)\.]+")

_TZ_ALIASES = {
    "IST": "Asia/Kolkata",
    "IND": "Asia/Kolkata",
    "INDIA": "Asia/Kolkata",
}


class ReminderRecipientType(str, Enum):
    CUSTOMER = "customer"
    OWNER = "owner"
    STAFF = "staff"


class ReminderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class SmsErrorCategory(str, Enum):
    TRANSIENT = "transient"
    AMBIGUOUS_TIMEOUT = "ambiguous_timeout"
    PERMANENT = "permanent"


def normalize_e164_phone(
    raw: Optional[str],
    *,
    default_country_code: Optional[str] = None,
) -> Optional[str]:
    """Normalize a phone string into strict ITU-T E.164 (`+<country><number>`).

    International-safe: NEVER assumes a default country (such as India `+91`)
    unless `default_country_code` is explicitly supplied.
    Returns `None` if the value is empty or cannot be safely normalized.
    """
    if raw is None:
        return None
    cleaned = _STRIP_CHARS_REGEX.sub("", raw.strip())
    if not cleaned:
        return None

    # Convert standard international dialing prefix `00` to `+`
    if cleaned.startswith("00") and len(cleaned) > 4:
        cleaned = "+" + cleaned[2:]

    if cleaned.startswith("+"):
        return cleaned if _E164_REGEX.match(cleaned) else None

    # Local number without `+`: only qualify if an explicit default country code is configured
    if default_country_code:
        cc = _STRIP_CHARS_REGEX.sub("", default_country_code.strip())
        if not cc.startswith("+"):
            cc = "+" + cc
        if _COUNTRY_CODE_REGEX.match(cc) and cleaned.isdigit():
            local_digits = cleaned.lstrip("0")
            candidate = f"{cc}{local_digits}"
            return candidate if _E164_REGEX.match(candidate) else None

    return None


def _resolve_tz(tz_name: Optional[str]) -> ZoneInfo:
    raw = (tz_name or "UTC").strip()
    canonical = _TZ_ALIASES.get(raw.upper(), raw)
    try:
        return ZoneInfo(canonical)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def render_reminder_message(
    *,
    recipient_type: ReminderRecipientType,
    salon_name: str,
    service_name: str,
    appointment_start_at: datetime,
    timezone_name: str,
    customer_name: str,
    staff_name: str,
    booking_reference: str,
    lead_minutes: int = 30,
) -> str:
    """Render concise transactional SMS reminder copy (zero promotional content)."""
    tz = _resolve_tz(timezone_name)
    local_dt = appointment_start_at.astimezone(tz)
    date_str = local_dt.strftime("%Y-%m-%d")
    time_str = local_dt.strftime("%H:%M")

    if recipient_type == ReminderRecipientType.CUSTOMER:
        return (
            f"Reminder: Your {service_name} appointment at {salon_name} is in "
            f"{lead_minutes} minutes at {time_str} on {date_str} with {staff_name}. "
            f"Ref: {booking_reference}."
        )
    if recipient_type == ReminderRecipientType.OWNER:
        return (
            f"Upcoming appointment in {lead_minutes} mins at {salon_name}: "
            f"{customer_name} for {service_name} at {time_str} on {date_str} "
            f"with {staff_name}. Ref: {booking_reference}."
        )
    return (
        f"Reminder: You have {service_name} with {customer_name} in "
        f"{lead_minutes} minutes at {time_str} on {date_str} ({salon_name}). "
        f"Ref: {booking_reference}."
    )


class BusinessNotificationSettings(BaseModel):
    """Explicit backend-only notification settings for a business."""

    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    business_id: UUID
    owner_sms_phone: Optional[str] = None
    sms_reminders_enabled: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AppointmentSmsReminder(BaseModel):
    """Persisted reminder row matching `public.appointment_sms_reminders`."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    organization_id: UUID
    business_id: UUID
    appointment_id: UUID
    appointment_version: int = Field(default=1, ge=1)
    appointment_start_at: datetime
    staff_id: Optional[UUID] = None
    recipient_type: ReminderRecipientType
    recipient_phone: Optional[str] = None
    recipient_name: Optional[str] = None
    scheduled_for: datetime
    status: ReminderStatus = ReminderStatus.PENDING
    skip_reason: Optional[str] = None
    template_key: str
    provider_name: Optional[str] = None
    provider_message_id: Optional[str] = None
    provider_status: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    next_retry_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LiveAppointmentSnapshot(BaseModel):
    """Authoritative live appointment state re-read immediately before dispatch."""

    appointment_id: UUID
    organization_id: UUID
    business_id: UUID
    booking_reference: str
    status: str
    start_at: datetime
    timezone: str
    staff_id: UUID
    staff_name: str
    service_name: str
    customer_name: str
    salon_name: str


def build_reminder_template_variables(
    *,
    recipient_type: ReminderRecipientType,
    salon_name: str,
    service_name: str,
    appointment_start_at: datetime,
    timezone_name: str,
    customer_name: str,
    staff_name: str,
    booking_reference: str,
) -> Dict[str, str]:
    """Build sanitized, DLT-variable-safe key/value map for transactional templates."""
    tz = _resolve_tz(timezone_name)
    local_dt = appointment_start_at.astimezone(tz)
    date_str = local_dt.strftime("%Y-%m-%d")
    time_str = local_dt.strftime("%H:%M")

    def _clip(val: str, limit: int = 30) -> str:
        cleaned = " ".join((val or "").split())
        return cleaned[:limit]

    base = {
        "salon_name": _clip(salon_name),
        "service_name": _clip(service_name),
        "appointment_date": date_str,
        "start_time": time_str,
        "booking_reference": _clip(booking_reference),
    }
    if recipient_type == ReminderRecipientType.CUSTOMER:
        base["staff_name"] = _clip(staff_name)
    elif recipient_type == ReminderRecipientType.OWNER:
        base["customer_name"] = _clip(customer_name)
        base["staff_name"] = _clip(staff_name)
    else:
        base["customer_name"] = _clip(customer_name)
    return base


class SmsSendRequest(BaseModel):
    """Provider-independent outbound SMS request."""

    reminder_id: UUID
    recipient_type: ReminderRecipientType
    recipient_phone: str
    template_key: str
    message_body: str
    idempotency_key: str
    template_variables: Dict[str, str] = Field(default_factory=dict)


class SmsSendResult(BaseModel):
    """Provider-independent outbound SMS acceptance result (accepted != delivered)."""

    provider_name: str
    provider_message_id: str
    provider_status: str
    simulated: bool = False


class LeaseUpdateResult(BaseModel):
    """Explicit outcome of a lease-fenced reminder status update."""

    updated: bool
    lease_lost: bool = False
    reminder: Optional[AppointmentSmsReminder] = None


class ReconciliationCandidateAppointment(BaseModel):
    """Upcoming confirmed/rescheduled appointment evaluated by recipient-level reconciliation."""

    appointment_id: UUID
    organization_id: UUID
    business_id: UUID
    start_at: datetime
    timezone: str
    status: str
    staff_id: UUID
    staff_name: str
    staff_phone: Optional[str] = None
    customer_name: str
    customer_phone: str
