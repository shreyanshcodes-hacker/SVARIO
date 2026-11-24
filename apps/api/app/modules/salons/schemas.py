"""Pydantic v2 schemas for Stage 5 Salon Workflow Module.

Covers:
- A. Salon Services CRUD & validation
- B. Staff Management & Staff-Service Assignments
- C. Salon Working Schedules, Breaks, Holidays & Closures
- D. Appointment Availability Calculation
- E. Appointment Management (Create, View, Reschedule, Cancel, Idempotency)
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TIME_HHMM_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
TIME_12H_REGEX = re.compile(r"^(\d{1,2})(?::([0-5]\d))?\s*(am|pm)$", re.IGNORECASE)
TIME_24H_FLEX_REGEX = re.compile(r"^(\d{1,2}):([0-5]\d)(?::[0-5]\d)?$")
PHONE_BASIC_REGEX = re.compile(r"^\+?[0-9][0-9\-\s()]{4,28}[0-9]$")
EMAIL_BASIC_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_hhmm_to_minutes(hhmm: str) -> int:
    """Convert validated HH:MM string to minutes since midnight (0..1439)."""
    parts = hhmm.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def format_minutes_to_hhmm(total_minutes: int) -> str:
    """Format minutes since midnight to HH:MM string."""
    hours = (total_minutes // 60) % 24
    mins = total_minutes % 60
    return f"{hours:02d}:{mins:02d}"


def normalize_time_string(raw: Optional[str]) -> Optional[str]:
    """Normalize 24-hour (HH:MM, H:MM, HH:MM:SS) or 12-hour AM/PM time strings to canonical HH:MM."""
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None

    m12 = TIME_12H_REGEX.match(cleaned)
    if m12:
        hour_12 = int(m12.group(1))
        minute = int(m12.group(2) or "0")
        meridiem = m12.group(3).lower()
        if hour_12 < 1 or hour_12 > 12:
            raise ValueError(f"Time '{raw}' must be a valid 12-hour or 24-hour time.")
        if meridiem == "am":
            hour_24 = 0 if hour_12 == 12 else hour_12
        else:
            hour_24 = 12 if hour_12 == 12 else hour_12 + 12
        return f"{hour_24:02d}:{minute:02d}"

    m24 = TIME_24H_FLEX_REGEX.match(cleaned)
    if m24:
        hour_24 = int(m24.group(1))
        minute = int(m24.group(2))
        if 0 <= hour_24 <= 23:
            return f"{hour_24:02d}:{minute:02d}"

    raise ValueError(f"Time '{raw}' must be in 24-hour HH:MM format (00:00 to 23:59).")


class SalonAppointmentStatus(str, Enum):
    """Canonical lifecycle states for a salon appointment."""

    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class SalonAppointmentSource(str, Enum):
    """Origin channel of a salon appointment."""

    DASHBOARD = "dashboard"
    VOICE_AGENT = "voice_agent"
    API = "api"


# ============================================================================
# A. SALON SERVICES
# ============================================================================


class SalonServiceCreateRequest(BaseModel):
    """Payload to create a salon service (Owner/Admin only)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: str = Field(default="general", min_length=2, max_length=80)
    price: float = Field(..., ge=0.0, le=1_000_000.0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    duration_minutes: int = Field(..., ge=5, le=480)
    is_active: bool = Field(default=True)

    @field_validator("name", "category")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Field must contain at least 2 non-whitespace characters.")
        return trimmed

    @field_validator("description")
    @classmethod
    def clean_optional_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("Currency must be a 3-letter ISO code (e.g. INR, USD).")
        return cleaned

    @field_validator("price")
    @classmethod
    def round_price(cls, value: float) -> float:
        return round(float(value), 2)


class SalonServiceUpdateRequest(BaseModel):
    """Payload to update an existing salon service (Owner/Admin only)."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, min_length=2, max_length=80)
    price: Optional[float] = Field(default=None, ge=0.0, le=1_000_000.0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=480)
    is_active: Optional[bool] = None

    @field_validator("name", "category")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Field must contain at least 2 non-whitespace characters.")
        return trimmed

    @field_validator("currency")
    @classmethod
    def clean_optional_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("Currency must be a 3-letter ISO code (e.g. INR, USD).")
        return cleaned

    @field_validator("price")
    @classmethod
    def round_optional_price(cls, value: Optional[float]) -> Optional[float]:
        return round(float(value), 2) if value is not None else None


class SalonServiceResponse(BaseModel):
    """Salon service record scoped to an organization and business."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    name: str
    description: Optional[str] = None
    category: str
    price: float
    currency: str
    duration_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================================
# B & C. STAFF MANAGEMENT & WORKING SCHEDULES / BREAKS / HOLIDAYS
# ============================================================================


class SalonStaffWorkingHoursItem(BaseModel):
    """Single weekday working hours entry for a salon staff member (0=Sunday .. 6=Saturday)."""

    model_config = ConfigDict(extra="forbid")

    weekday: int = Field(..., ge=0, le=6)
    is_off: bool = Field(default=False)
    start_time: Optional[str] = Field(default="09:00")
    end_time: Optional[str] = Field(default="18:00")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_hhmm(cls, value: Optional[str]) -> Optional[str]:
        return normalize_time_string(value)

    @model_validator(mode="after")
    def verify_open_close_consistency(self) -> "SalonStaffWorkingHoursItem":
        if self.is_off:
            self.start_time = None
            self.end_time = None
            return self
        if not self.start_time or not self.end_time:
            raise ValueError(
                f"start_time and end_time are required for working weekday {self.weekday}."
            )
        if parse_hhmm_to_minutes(self.start_time) >= parse_hhmm_to_minutes(self.end_time):
            raise ValueError(
                f"Staff start_time ({self.start_time}) must be strictly earlier than end_time ({self.end_time})."
            )
        return self


class SalonStaffWorkingHoursUpdateRequest(BaseModel):
    """Payload to update weekly working hours for a staff member."""

    model_config = ConfigDict(extra="forbid")

    schedule: List[SalonStaffWorkingHoursItem] = Field(..., min_length=1, max_length=7)

    @model_validator(mode="after")
    def validate_unique_weekdays(self) -> "SalonStaffWorkingHoursUpdateRequest":
        seen = set()
        for item in self.schedule:
            if item.weekday in seen:
                raise ValueError(f"Duplicate weekday {item.weekday} in staff schedule.")
            seen.add(item.weekday)
        return self


class SalonStaffBreakCreateRequest(BaseModel):
    """Payload to add a recurring weekday break or date-specific break for a staff member."""

    model_config = ConfigDict(extra="forbid")

    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    specific_date: Optional[date] = None
    label: str = Field(default="Lunch Break", min_length=2, max_length=80)
    start_time: str
    end_time: str

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Break label must contain at least 2 characters.")
        return trimmed

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_hhmm(cls, value: str) -> str:
        norm = normalize_time_string(value)
        if not norm:
            raise ValueError("Break start_time and end_time are required.")
        return norm

    @model_validator(mode="after")
    def verify_break_validity(self) -> "SalonStaffBreakCreateRequest":
        if self.weekday is None and self.specific_date is None:
            raise ValueError("Provide either weekday (0..6) or specific_date for a staff break.")
        if parse_hhmm_to_minutes(self.start_time) >= parse_hhmm_to_minutes(self.end_time):
            raise ValueError(
                f"Break start_time ({self.start_time}) must be strictly before end_time ({self.end_time})."
            )
        return self


class SalonStaffBreakResponse(BaseModel):
    """Staff break entry."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    staff_id: UUID
    weekday: Optional[int] = None
    specific_date: Optional[date] = None
    label: str
    start_time: str
    end_time: str
    created_at: datetime


class SalonStaffCreateRequest(BaseModel):
    """Payload to create a salon staff profile (Owner/Admin only)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., min_length=2, max_length=120)
    role_designation: str = Field(default="Stylist", min_length=2, max_length=80)
    email: Optional[str] = Field(default=None, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=32)
    bio: Optional[str] = Field(default=None, max_length=1000)
    is_active: bool = Field(default=True)
    assigned_service_ids: List[UUID] = Field(default_factory=list)

    @field_validator("full_name", "role_designation")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Field must contain at least 2 non-whitespace characters.")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().lower()
        if not EMAIL_BASIC_REGEX.match(cleaned):
            raise ValueError("Invalid staff email address.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_optional_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not PHONE_BASIC_REGEX.match(cleaned):
            raise ValueError("Invalid staff phone number format.")
        return cleaned


class SalonStaffUpdateRequest(BaseModel):
    """Payload to update an existing salon staff profile (Owner/Admin only)."""

    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    role_designation: Optional[str] = Field(default=None, min_length=2, max_length=80)
    email: Optional[str] = Field(default=None, max_length=160)
    phone: Optional[str] = Field(default=None, max_length=32)
    bio: Optional[str] = Field(default=None, max_length=1000)
    is_active: Optional[bool] = None
    assigned_service_ids: Optional[List[UUID]] = None

    @field_validator("full_name", "role_designation")
    @classmethod
    def clean_optional_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Field must contain at least 2 non-whitespace characters.")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().lower()
        if not EMAIL_BASIC_REGEX.match(cleaned):
            raise ValueError("Invalid staff email address.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_optional_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip()
        if not PHONE_BASIC_REGEX.match(cleaned):
            raise ValueError("Invalid staff phone number format.")
        return cleaned


class SalonStaffServiceAssignmentRequest(BaseModel):
    """Payload to replace the list of services assigned to a staff member."""

    model_config = ConfigDict(extra="forbid")

    service_ids: List[UUID] = Field(default_factory=list)


class SalonStaffResponse(BaseModel):
    """Complete staff profile including assigned services, weekly schedule, and breaks."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    full_name: str
    role_designation: str
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool
    assigned_service_ids: List[UUID] = Field(default_factory=list)
    assigned_service_names: List[str] = Field(default_factory=list)
    working_hours: List[SalonStaffWorkingHoursItem] = Field(default_factory=list)
    breaks: List[SalonStaffBreakResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SalonHolidayCreateRequest(BaseModel):
    """Payload to create a whole-salon holiday/closure or staff-specific leave."""

    model_config = ConfigDict(extra="forbid")

    holiday_date: date
    title: str = Field(..., min_length=2, max_length=120)
    staff_id: Optional[UUID] = Field(
        default=None,
        description="Optional staff_id. When None, applies to the entire salon.",
    )
    is_closed_all_day: bool = Field(default=True)
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Holiday title must contain at least 2 characters.")
        return trimmed

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_hhmm(cls, value: Optional[str]) -> Optional[str]:
        return normalize_time_string(value)

    @model_validator(mode="after")
    def verify_partial_closure_times(self) -> "SalonHolidayCreateRequest":
        if self.is_closed_all_day:
            self.start_time = None
            self.end_time = None
            return self
        if not self.start_time or not self.end_time:
            raise ValueError(
                "start_time and end_time are required when is_closed_all_day is False."
            )
        if parse_hhmm_to_minutes(self.start_time) >= parse_hhmm_to_minutes(self.end_time):
            raise ValueError(
                f"Closure start_time ({self.start_time}) must be strictly before end_time ({self.end_time})."
            )
        return self


class SalonHolidayResponse(BaseModel):
    """Salon holiday or special closure entry."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    staff_id: Optional[UUID] = None
    staff_name: Optional[str] = None
    holiday_date: date
    title: str
    is_closed_all_day: bool
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    created_at: datetime


# ============================================================================
# D. APPOINTMENT AVAILABILITY
# ============================================================================


class SalonAvailabilitySlot(BaseModel):
    """Single non-conflicting bookable slot for a salon service and staff member."""

    start_time: str
    end_time: str
    start_at: datetime
    end_at: datetime
    staff_id: UUID
    staff_name: str
    staff_role: str


class SalonAvailabilityResponse(BaseModel):
    """Computed availability response for a requested service and date."""

    organization_id: UUID
    business_id: UUID
    service_id: UUID
    service_name: str
    duration_minutes: int
    price: float
    currency: str
    requested_date: date
    timezone: str
    is_business_closed: bool = False
    closure_reason: Optional[str] = None
    available_slots: List[SalonAvailabilitySlot] = Field(default_factory=list)


# ============================================================================
# E. APPOINTMENT MANAGEMENT
# ============================================================================


class SalonAppointmentCreateRequest(BaseModel):
    """Payload to create a salon appointment with concurrency & idempotency protection."""

    model_config = ConfigDict(extra="forbid")

    service_id: UUID
    staff_id: Optional[UUID] = None
    appointment_date: date
    start_time: str
    customer_name: str = Field(..., min_length=2, max_length=120)
    customer_phone: str = Field(..., min_length=6, max_length=32)
    customer_email: Optional[str] = Field(default=None, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=128)
    source: SalonAppointmentSource = Field(default=SalonAppointmentSource.DASHBOARD)

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, value: str) -> str:
        norm = normalize_time_string(value)
        if not norm:
            raise ValueError("start_time is required in HH:MM format.")
        return norm

    @field_validator("customer_name")
    @classmethod
    def clean_customer_name(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("customer_name must contain at least 2 characters.")
        return trimmed

    @field_validator("customer_phone")
    @classmethod
    def clean_customer_phone(cls, value: str) -> str:
        trimmed = value.strip()
        if not PHONE_BASIC_REGEX.match(trimmed):
            raise ValueError("customer_phone must be a valid phone number.")
        return trimmed

    @field_validator("customer_email")
    @classmethod
    def clean_customer_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        cleaned = value.strip().lower()
        if not EMAIL_BASIC_REGEX.match(cleaned):
            raise ValueError("customer_email must be a valid email address.")
        return cleaned


class SalonAppointmentRescheduleRequest(BaseModel):
    """Payload to reschedule an existing salon appointment."""

    model_config = ConfigDict(extra="forbid")

    appointment_date: date
    start_time: str
    staff_id: Optional[UUID] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=128)

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, value: str) -> str:
        norm = normalize_time_string(value)
        if not norm:
            raise ValueError("start_time is required in HH:MM format.")
        return norm


class SalonAppointmentCancelRequest(BaseModel):
    """Payload to cancel an existing salon appointment."""

    model_config = ConfigDict(extra="forbid")

    cancellation_reason: Optional[str] = Field(default=None, max_length=300)


class SalonAppointmentResponse(BaseModel):
    """Confirmed or updated salon appointment record."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    booking_reference: str
    idempotency_key: Optional[str] = None
    service_id: UUID
    service_name: str
    service_duration_minutes: int
    service_price: float
    service_currency: str
    staff_id: UUID
    staff_name: str
    staff_role: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    notes: Optional[str] = None
    appointment_date: date
    start_time: str
    end_time: str
    start_at: datetime
    end_at: datetime
    timezone: str
    status: SalonAppointmentStatus
    source: SalonAppointmentSource
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
