"""Stage 6 Clinic Workflow Module — Pydantic v2 Schemas.

Strictly administrative clinic domain models:
- Departments, Doctors, Specialities, Consultation Types
- Doctor-Department, Doctor-Speciality, Doctor-ConsultationType mappings
- Doctor Working Hours, Breaks, Unavailability
- Dynamic Availability Slots & Transactional Appointments

No medical history, diagnosis, symptoms, prescriptions, or clinical notes are stored.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConsultationMode(str, Enum):
    IN_PERSON = "in_person"
    ONLINE = "online"


class ClinicAppointmentStatus(str, Enum):
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class ClinicAppointmentSource(str, Enum):
    DASHBOARD = "dashboard"
    VOICE_AGENT = "voice_agent"
    API = "api"


# ----------------------------------------------------------------------------
# Departments
# ----------------------------------------------------------------------------


class ClinicDepartmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True


class ClinicDepartmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class ClinicDepartmentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------------
# Specialities
# ----------------------------------------------------------------------------


class ClinicSpecialityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True


class ClinicSpecialityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class ClinicSpecialityResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------------
# Consultation Types
# ----------------------------------------------------------------------------


class ClinicConsultationTypeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    duration_minutes: int = Field(..., ge=5, le=240)
    consultation_mode: ConsultationMode = ConsultationMode.IN_PERSON
    fee_amount: Optional[Decimal] = Field(default=None, ge=0, le=1000000)
    currency_code: Optional[str] = Field(default="INR", min_length=3, max_length=3)
    is_active: bool = True


class ClinicConsultationTypeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    consultation_mode: Optional[ConsultationMode] = None
    fee_amount: Optional[Decimal] = Field(default=None, ge=0, le=1000000)
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    is_active: Optional[bool] = None


class ClinicConsultationTypeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    name: str
    description: Optional[str] = None
    duration_minutes: int
    consultation_mode: ConsultationMode
    fee_amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------------
# Doctors & Mappings
# ----------------------------------------------------------------------------


class ClinicDoctorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=2, max_length=120)
    professional_title: Optional[str] = Field(default=None, max_length=120)
    public_bio: Optional[str] = Field(default=None, max_length=600)
    languages: List[str] = Field(default_factory=lambda: ["en"], min_length=1)
    is_active: bool = True
    department_ids: List[UUID] = Field(default_factory=list)
    speciality_ids: List[UUID] = Field(default_factory=list)
    consultation_type_ids: List[UUID] = Field(default_factory=list)


class ClinicDoctorUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    professional_title: Optional[str] = Field(default=None, max_length=120)
    public_bio: Optional[str] = Field(default=None, max_length=600)
    languages: Optional[List[str]] = Field(default=None, min_length=1)
    is_active: Optional[bool] = None


class ClinicDoctorMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: List[UUID] = Field(default_factory=list)


class ClinicDoctorResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    display_name: str
    professional_title: Optional[str] = None
    public_bio: Optional[str] = None
    languages: List[str]
    is_active: bool
    department_ids: List[UUID] = Field(default_factory=list)
    speciality_ids: List[UUID] = Field(default_factory=list)
    consultation_type_ids: List[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------------
# Schedules: Working Hours, Breaks, Unavailability
# ----------------------------------------------------------------------------


class DoctorWorkingHoursItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(..., ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_hours(self) -> "DoctorWorkingHoursItem":
        if self.is_active:
            if self.start_time is None or self.end_time is None:
                raise ValueError("start_time and end_time are required when is_active is True.")
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be earlier than end_time.")
        return self


class DoctorWorkingHoursBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DoctorWorkingHoursItem] = Field(..., min_length=1, max_length=7)


class DoctorWorkingHoursResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    doctor_id: UUID
    day_of_week: int
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DoctorBreakCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    specific_date: Optional[date] = None
    break_start: time
    break_end: time
    reason: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_break(self) -> "DoctorBreakCreateRequest":
        if self.day_of_week is None and self.specific_date is None:
            raise ValueError("Either day_of_week or specific_date must be provided.")
        if self.break_start >= self.break_end:
            raise ValueError("break_start must be earlier than break_end.")
        return self


class DoctorBreakResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    doctor_id: UUID
    day_of_week: Optional[int] = None
    specific_date: Optional[date] = None
    break_start: time
    break_end: time
    reason: Optional[str] = None
    created_at: datetime


class DoctorUnavailabilityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_at: datetime
    ends_at: datetime
    reason: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_range(self) -> "DoctorUnavailabilityCreateRequest":
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be earlier than ends_at.")
        return self


class DoctorUnavailabilityResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    doctor_id: UUID
    starts_at: datetime
    ends_at: datetime
    reason: Optional[str] = None
    created_at: datetime


# ----------------------------------------------------------------------------
# Availability & Appointments
# ----------------------------------------------------------------------------


class ClinicAvailableSlot(BaseModel):
    doctor_id: UUID
    doctor_name: str
    consultation_type_id: UUID
    starts_at: datetime
    ends_at: datetime
    timezone: str


class ClinicAvailabilityResponse(BaseModel):
    organization_id: UUID
    business_id: UUID
    target_date: date
    timezone: str
    consultation_type_id: UUID
    duration_minutes: int
    slots: List[ClinicAvailableSlot]


class ClinicAppointmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doctor_id: UUID
    consultation_type_id: UUID
    department_id: Optional[UUID] = None
    patient_display_name: str = Field(..., min_length=2, max_length=120)
    patient_contact: str = Field(..., min_length=5, max_length=80)
    starts_at: datetime
    idempotency_key: Optional[str] = Field(default=None, min_length=4, max_length=120)
    source: ClinicAppointmentSource = ClinicAppointmentSource.DASHBOARD


class ClinicAppointmentRescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_starts_at: datetime
    new_doctor_id: Optional[UUID] = None
    patient_contact_verification: Optional[str] = Field(default=None, min_length=4, max_length=80)


class ClinicAppointmentCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Optional[str] = Field(default=None, max_length=250)
    patient_contact_verification: Optional[str] = Field(default=None, min_length=4, max_length=80)


class ClinicAppointmentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    business_id: UUID
    booking_reference: str
    doctor_id: UUID
    doctor_name: Optional[str] = None
    consultation_type_id: UUID
    consultation_type_name: Optional[str] = None
    department_id: Optional[UUID] = None
    patient_display_name: str
    patient_contact: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    status: ClinicAppointmentStatus
    source: ClinicAppointmentSource
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
