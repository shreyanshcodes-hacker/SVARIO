"""Stage 6 Clinic Workflow Module — Repository Protocol & In-Memory Implementation.

Provides concurrency-safe, tenant-scoped persistence for clinic entities:
- Departments, Doctors, Specialities, Consultation Types
- Doctor mappings (departments, specialities, consultation types)
- Working hours, Breaks, Unavailability
- Idempotent & overlap-safe Clinic Appointments
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Protocol, Tuple
from uuid import UUID, uuid4
from app.modules.clinics.schemas import (
    ClinicAppointmentCreateRequest,
    ClinicAppointmentResponse,
    ClinicAppointmentStatus,
    ClinicConsultationTypeCreateRequest,
    ClinicConsultationTypeResponse,
    ClinicConsultationTypeUpdateRequest,
    ClinicDepartmentCreateRequest,
    ClinicDepartmentResponse,
    ClinicDepartmentUpdateRequest,
    ClinicDoctorCreateRequest,
    ClinicDoctorResponse,
    ClinicDoctorUpdateRequest,
    ClinicSpecialityCreateRequest,
    ClinicSpecialityResponse,
    ClinicSpecialityUpdateRequest,
    DoctorBreakCreateRequest,
    DoctorBreakResponse,
    DoctorUnavailabilityCreateRequest,
    DoctorUnavailabilityResponse,
    DoctorWorkingHoursItem,
    DoctorWorkingHoursResponse,
)


class ClinicConflictError(Exception):
    """Raised when an appointment slot overlaps or a unique constraint is violated."""


class ClinicNotFoundError(Exception):
    """Raised when a clinic resource is not found in the tenant scope."""


class ClinicRepositoryProtocol(Protocol):
    """Abstract repository interface for Clinic Workflow persistence."""

    async def list_departments(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicDepartmentResponse]: ...

    async def get_department(
        self, organization_id: UUID, business_id: UUID, department_id: UUID
    ) -> Optional[ClinicDepartmentResponse]: ...

    async def create_department(
        self, organization_id: UUID, business_id: UUID, payload: ClinicDepartmentCreateRequest
    ) -> ClinicDepartmentResponse: ...

    async def update_department(
        self,
        organization_id: UUID,
        business_id: UUID,
        department_id: UUID,
        payload: ClinicDepartmentUpdateRequest,
    ) -> Optional[ClinicDepartmentResponse]: ...

    async def list_specialities(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicSpecialityResponse]: ...

    async def get_speciality(
        self, organization_id: UUID, business_id: UUID, speciality_id: UUID
    ) -> Optional[ClinicSpecialityResponse]: ...

    async def create_speciality(
        self, organization_id: UUID, business_id: UUID, payload: ClinicSpecialityCreateRequest
    ) -> ClinicSpecialityResponse: ...

    async def update_speciality(
        self,
        organization_id: UUID,
        business_id: UUID,
        speciality_id: UUID,
        payload: ClinicSpecialityUpdateRequest,
    ) -> Optional[ClinicSpecialityResponse]: ...

    async def list_consultation_types(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicConsultationTypeResponse]: ...

    async def get_consultation_type(
        self, organization_id: UUID, business_id: UUID, consultation_type_id: UUID
    ) -> Optional[ClinicConsultationTypeResponse]: ...

    async def create_consultation_type(
        self,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicConsultationTypeCreateRequest,
    ) -> ClinicConsultationTypeResponse: ...

    async def update_consultation_type(
        self,
        organization_id: UUID,
        business_id: UUID,
        consultation_type_id: UUID,
        payload: ClinicConsultationTypeUpdateRequest,
    ) -> Optional[ClinicConsultationTypeResponse]: ...

    async def list_doctors(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicDoctorResponse]: ...

    async def get_doctor(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> Optional[ClinicDoctorResponse]: ...

    async def create_doctor(
        self, organization_id: UUID, business_id: UUID, payload: ClinicDoctorCreateRequest
    ) -> ClinicDoctorResponse: ...

    async def update_doctor(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: ClinicDoctorUpdateRequest,
    ) -> Optional[ClinicDoctorResponse]: ...

    async def set_doctor_departments(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID, department_ids: List[UUID]
    ) -> Optional[ClinicDoctorResponse]: ...

    async def set_doctor_specialities(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID, speciality_ids: List[UUID]
    ) -> Optional[ClinicDoctorResponse]: ...

    async def set_doctor_consultation_types(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        consultation_type_ids: List[UUID],
    ) -> Optional[ClinicDoctorResponse]: ...

    async def get_doctor_working_hours(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorWorkingHoursResponse]: ...

    async def upsert_doctor_working_hours(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        items: List[DoctorWorkingHoursItem],
    ) -> List[DoctorWorkingHoursResponse]: ...

    async def list_doctor_breaks(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorBreakResponse]: ...

    async def create_doctor_break(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorBreakCreateRequest,
    ) -> DoctorBreakResponse: ...

    async def list_doctor_unavailability(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorUnavailabilityResponse]: ...

    async def create_doctor_unavailability(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorUnavailabilityCreateRequest,
    ) -> DoctorUnavailabilityResponse: ...

    async def list_appointments(
        self,
        organization_id: UUID,
        business_id: UUID,
        *,
        doctor_id: Optional[UUID] = None,
        target_date: Optional[date] = None,
        status_filter: Optional[ClinicAppointmentStatus] = None,
    ) -> List[ClinicAppointmentResponse]: ...

    async def get_appointment(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> Optional[ClinicAppointmentResponse]: ...

    async def get_appointment_by_reference(
        self, organization_id: UUID, business_id: UUID, booking_reference: str
    ) -> Optional[ClinicAppointmentResponse]: ...

    async def create_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicAppointmentCreateRequest,
        ends_at: datetime,
        tz_name: str,
        doctor_name: str,
        consultation_type_name: str,
    ) -> ClinicAppointmentResponse: ...

    async def reschedule_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        new_doctor_id: UUID,
        new_doctor_name: str,
        new_starts_at: datetime,
        new_ends_at: datetime,
    ) -> ClinicAppointmentResponse: ...

    async def cancel_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        reason: Optional[str],
    ) -> ClinicAppointmentResponse: ...


class InMemoryClinicRepository:
    """Thread/async-safe in-memory Clinic repository simulating PostgreSQL constraints."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._departments: Dict[UUID, ClinicDepartmentResponse] = {}
        self._specialities: Dict[UUID, ClinicSpecialityResponse] = {}
        self._consultation_types: Dict[UUID, ClinicConsultationTypeResponse] = {}
        self._doctors: Dict[UUID, ClinicDoctorResponse] = {}
        self._working_hours: Dict[Tuple[UUID, int], DoctorWorkingHoursResponse] = {}
        self._breaks: Dict[UUID, DoctorBreakResponse] = {}
        self._unavailability: Dict[UUID, DoctorUnavailabilityResponse] = {}
        self._appointments: Dict[UUID, ClinicAppointmentResponse] = {}
        self._idempotency: Dict[Tuple[UUID, str], UUID] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # ---- Departments ----
    async def list_departments(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicDepartmentResponse]:
        items = [
            d
            for d in self._departments.values()
            if d.organization_id == organization_id and d.business_id == business_id
        ]
        if active_only:
            items = [d for d in items if d.is_active]
        return sorted(items, key=lambda d: d.name.lower())

    async def get_department(
        self, organization_id: UUID, business_id: UUID, department_id: UUID
    ) -> Optional[ClinicDepartmentResponse]:
        d = self._departments.get(department_id)
        if d and d.organization_id == organization_id and d.business_id == business_id:
            return d
        return None

    async def create_department(
        self, organization_id: UUID, business_id: UUID, payload: ClinicDepartmentCreateRequest
    ) -> ClinicDepartmentResponse:
        async with self._lock:
            for existing in self._departments.values():
                if (
                    existing.business_id == business_id
                    and existing.name.strip().lower() == payload.name.strip().lower()
                ):
                    raise ClinicConflictError("A department with this name already exists in this clinic.")
            now = self._now()
            dept = ClinicDepartmentResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                name=payload.name.strip(),
                description=payload.description.strip() if payload.description else None,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now,
            )
            self._departments[dept.id] = dept
            return dept

    async def update_department(
        self,
        organization_id: UUID,
        business_id: UUID,
        department_id: UUID,
        payload: ClinicDepartmentUpdateRequest,
    ) -> Optional[ClinicDepartmentResponse]:
        async with self._lock:
            existing = await self.get_department(organization_id, business_id, department_id)
            if not existing:
                return None
            updates = payload.model_dump(exclude_unset=True)
            if "name" in updates and updates["name"] is not None:
                updates["name"] = updates["name"].strip()
            updates["updated_at"] = self._now()
            updated = existing.model_copy(update=updates)
            self._departments[department_id] = updated
            return updated

    # ---- Specialities ----
    async def list_specialities(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicSpecialityResponse]:
        items = [
            s
            for s in self._specialities.values()
            if s.organization_id == organization_id and s.business_id == business_id
        ]
        if active_only:
            items = [s for s in items if s.is_active]
        return sorted(items, key=lambda s: s.name.lower())

    async def get_speciality(
        self, organization_id: UUID, business_id: UUID, speciality_id: UUID
    ) -> Optional[ClinicSpecialityResponse]:
        s = self._specialities.get(speciality_id)
        if s and s.organization_id == organization_id and s.business_id == business_id:
            return s
        return None

    async def create_speciality(
        self, organization_id: UUID, business_id: UUID, payload: ClinicSpecialityCreateRequest
    ) -> ClinicSpecialityResponse:
        async with self._lock:
            for existing in self._specialities.values():
                if (
                    existing.business_id == business_id
                    and existing.name.strip().lower() == payload.name.strip().lower()
                ):
                    raise ClinicConflictError("A speciality with this name already exists in this clinic.")
            now = self._now()
            spec = ClinicSpecialityResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                name=payload.name.strip(),
                description=payload.description.strip() if payload.description else None,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now,
            )
            self._specialities[spec.id] = spec
            return spec

    async def update_speciality(
        self,
        organization_id: UUID,
        business_id: UUID,
        speciality_id: UUID,
        payload: ClinicSpecialityUpdateRequest,
    ) -> Optional[ClinicSpecialityResponse]:
        async with self._lock:
            existing = await self.get_speciality(organization_id, business_id, speciality_id)
            if not existing:
                return None
            updates = payload.model_dump(exclude_unset=True)
            if "name" in updates and updates["name"] is not None:
                updates["name"] = updates["name"].strip()
            updates["updated_at"] = self._now()
            updated = existing.model_copy(update=updates)
            self._specialities[speciality_id] = updated
            return updated

    # ---- Consultation Types ----
    async def list_consultation_types(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicConsultationTypeResponse]:
        items = [
            c
            for c in self._consultation_types.values()
            if c.organization_id == organization_id and c.business_id == business_id
        ]
        if active_only:
            items = [c for c in items if c.is_active]
        return sorted(items, key=lambda c: c.name.lower())

    async def get_consultation_type(
        self, organization_id: UUID, business_id: UUID, consultation_type_id: UUID
    ) -> Optional[ClinicConsultationTypeResponse]:
        c = self._consultation_types.get(consultation_type_id)
        if c and c.organization_id == organization_id and c.business_id == business_id:
            return c
        return None

    async def create_consultation_type(
        self,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicConsultationTypeCreateRequest,
    ) -> ClinicConsultationTypeResponse:
        async with self._lock:
            now = self._now()
            item = ClinicConsultationTypeResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                name=payload.name.strip(),
                description=payload.description.strip() if payload.description else None,
                duration_minutes=payload.duration_minutes,
                consultation_mode=payload.consultation_mode,
                fee_amount=payload.fee_amount,
                currency_code=payload.currency_code.upper() if payload.currency_code else None,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now,
            )
            self._consultation_types[item.id] = item
            return item

    async def update_consultation_type(
        self,
        organization_id: UUID,
        business_id: UUID,
        consultation_type_id: UUID,
        payload: ClinicConsultationTypeUpdateRequest,
    ) -> Optional[ClinicConsultationTypeResponse]:
        async with self._lock:
            existing = await self.get_consultation_type(
                organization_id, business_id, consultation_type_id
            )
            if not existing:
                return None
            updates = payload.model_dump(exclude_unset=True)
            if "name" in updates and updates["name"] is not None:
                updates["name"] = updates["name"].strip()
            if "currency_code" in updates and updates["currency_code"] is not None:
                updates["currency_code"] = updates["currency_code"].upper()
            updates["updated_at"] = self._now()
            updated = existing.model_copy(update=updates)
            self._consultation_types[consultation_type_id] = updated
            return updated

    # ---- Doctors & Mappings ----
    async def list_doctors(
        self, organization_id: UUID, business_id: UUID, active_only: bool = False
    ) -> List[ClinicDoctorResponse]:
        items = [
            d
            for d in self._doctors.values()
            if d.organization_id == organization_id and d.business_id == business_id
        ]
        if active_only:
            items = [d for d in items if d.is_active]
        return sorted(items, key=lambda d: d.display_name.lower())

    async def get_doctor(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> Optional[ClinicDoctorResponse]:
        d = self._doctors.get(doctor_id)
        if d and d.organization_id == organization_id and d.business_id == business_id:
            return d
        return None

    async def create_doctor(
        self, organization_id: UUID, business_id: UUID, payload: ClinicDoctorCreateRequest
    ) -> ClinicDoctorResponse:
        async with self._lock:
            now = self._now()
            doc = ClinicDoctorResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                display_name=payload.display_name.strip(),
                professional_title=payload.professional_title.strip()
                if payload.professional_title
                else None,
                public_bio=payload.public_bio.strip() if payload.public_bio else None,
                languages=list(dict.fromkeys(payload.languages)),
                is_active=payload.is_active,
                department_ids=list(dict.fromkeys(payload.department_ids)),
                speciality_ids=list(dict.fromkeys(payload.speciality_ids)),
                consultation_type_ids=list(dict.fromkeys(payload.consultation_type_ids)),
                created_at=now,
                updated_at=now,
            )
            self._doctors[doc.id] = doc
            return doc

    async def update_doctor(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: ClinicDoctorUpdateRequest,
    ) -> Optional[ClinicDoctorResponse]:
        async with self._lock:
            existing = await self.get_doctor(organization_id, business_id, doctor_id)
            if not existing:
                return None
            updates = payload.model_dump(exclude_unset=True)
            if "display_name" in updates and updates["display_name"] is not None:
                updates["display_name"] = updates["display_name"].strip()
            updates["updated_at"] = self._now()
            updated = existing.model_copy(update=updates)
            self._doctors[doctor_id] = updated
            return updated

    async def set_doctor_departments(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID, department_ids: List[UUID]
    ) -> Optional[ClinicDoctorResponse]:
        async with self._lock:
            existing = await self.get_doctor(organization_id, business_id, doctor_id)
            if not existing:
                return None
            updated = existing.model_copy(
                update={
                    "department_ids": list(dict.fromkeys(department_ids)),
                    "updated_at": self._now(),
                }
            )
            self._doctors[doctor_id] = updated
            return updated

    async def set_doctor_specialities(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID, speciality_ids: List[UUID]
    ) -> Optional[ClinicDoctorResponse]:
        async with self._lock:
            existing = await self.get_doctor(organization_id, business_id, doctor_id)
            if not existing:
                return None
            updated = existing.model_copy(
                update={
                    "speciality_ids": list(dict.fromkeys(speciality_ids)),
                    "updated_at": self._now(),
                }
            )
            self._doctors[doctor_id] = updated
            return updated

    async def set_doctor_consultation_types(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        consultation_type_ids: List[UUID],
    ) -> Optional[ClinicDoctorResponse]:
        async with self._lock:
            existing = await self.get_doctor(organization_id, business_id, doctor_id)
            if not existing:
                return None
            updated = existing.model_copy(
                update={
                    "consultation_type_ids": list(dict.fromkeys(consultation_type_ids)),
                    "updated_at": self._now(),
                }
            )
            self._doctors[doctor_id] = updated
            return updated

    # ---- Schedules: Working Hours, Breaks, Unavailability ----
    async def get_doctor_working_hours(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorWorkingHoursResponse]:
        items = [
            wh
            for (d_id, _), wh in self._working_hours.items()
            if d_id == doctor_id
            and wh.organization_id == organization_id
            and wh.business_id == business_id
        ]
        return sorted(items, key=lambda wh: wh.day_of_week)

    async def upsert_doctor_working_hours(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        items: List[DoctorWorkingHoursItem],
    ) -> List[DoctorWorkingHoursResponse]:
        async with self._lock:
            now = self._now()
            for item in items:
                key = (doctor_id, item.day_of_week)
                existing = self._working_hours.get(key)
                if existing:
                    self._working_hours[key] = existing.model_copy(
                        update={
                            "start_time": item.start_time if item.is_active else None,
                            "end_time": item.end_time if item.is_active else None,
                            "is_active": item.is_active,
                            "updated_at": now,
                        }
                    )
                else:
                    self._working_hours[key] = DoctorWorkingHoursResponse(
                        id=uuid4(),
                        organization_id=organization_id,
                        business_id=business_id,
                        doctor_id=doctor_id,
                        day_of_week=item.day_of_week,
                        start_time=item.start_time if item.is_active else None,
                        end_time=item.end_time if item.is_active else None,
                        is_active=item.is_active,
                        created_at=now,
                        updated_at=now,
                    )
            return await self.get_doctor_working_hours(organization_id, business_id, doctor_id)

    async def list_doctor_breaks(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorBreakResponse]:
        return [
            b
            for b in self._breaks.values()
            if b.organization_id == organization_id
            and b.business_id == business_id
            and b.doctor_id == doctor_id
        ]

    async def create_doctor_break(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorBreakCreateRequest,
    ) -> DoctorBreakResponse:
        async with self._lock:
            item = DoctorBreakResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                doctor_id=doctor_id,
                day_of_week=payload.day_of_week,
                specific_date=payload.specific_date,
                break_start=payload.break_start,
                break_end=payload.break_end,
                reason=payload.reason,
                created_at=self._now(),
            )
            self._breaks[item.id] = item
            return item

    async def list_doctor_unavailability(
        self, organization_id: UUID, business_id: UUID, doctor_id: UUID
    ) -> List[DoctorUnavailabilityResponse]:
        items = [
            u
            for u in self._unavailability.values()
            if u.organization_id == organization_id
            and u.business_id == business_id
            and u.doctor_id == doctor_id
        ]
        return sorted(items, key=lambda u: u.starts_at)

    async def create_doctor_unavailability(
        self,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorUnavailabilityCreateRequest,
    ) -> DoctorUnavailabilityResponse:
        async with self._lock:
            item = DoctorUnavailabilityResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                doctor_id=doctor_id,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                reason=payload.reason,
                created_at=self._now(),
            )
            self._unavailability[item.id] = item
            return item

    # ---- Appointments (Concurrency-Safe & Idempotent) ----
    async def list_appointments(
        self,
        organization_id: UUID,
        business_id: UUID,
        *,
        doctor_id: Optional[UUID] = None,
        target_date: Optional[date] = None,
        status_filter: Optional[ClinicAppointmentStatus] = None,
    ) -> List[ClinicAppointmentResponse]:
        items = [
            a
            for a in self._appointments.values()
            if a.organization_id == organization_id and a.business_id == business_id
        ]
        if doctor_id is not None:
            items = [a for a in items if a.doctor_id == doctor_id]
        if target_date is not None:
            items = [a for a in items if a.starts_at.date() == target_date]
        if status_filter is not None:
            items = [a for a in items if a.status == status_filter]
        return sorted(items, key=lambda a: a.starts_at)

    async def get_appointment(
        self, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> Optional[ClinicAppointmentResponse]:
        appt = self._appointments.get(appointment_id)
        if appt and appt.organization_id == organization_id and appt.business_id == business_id:
            return appt
        return None

    async def get_appointment_by_reference(
        self, organization_id: UUID, business_id: UUID, booking_reference: str
    ) -> Optional[ClinicAppointmentResponse]:
        ref = booking_reference.strip().upper()
        for appt in self._appointments.values():
            if (
                appt.organization_id == organization_id
                and appt.business_id == business_id
                and appt.booking_reference.upper() == ref
            ):
                return appt
        return None

    def _has_overlap(
        self,
        *,
        doctor_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_appointment_id: Optional[UUID] = None,
    ) -> bool:
        for appt in self._appointments.values():
            if appt.doctor_id != doctor_id:
                continue
            if exclude_appointment_id and appt.id == exclude_appointment_id:
                continue
            if appt.status not in {
                ClinicAppointmentStatus.CONFIRMED,
                ClinicAppointmentStatus.RESCHEDULED,
            }:
                continue
            # Half-open interval [starts_at, ends_at) overlap check: a.start < b.end and b.start < a.end
            if appt.starts_at < ends_at and starts_at < appt.ends_at:
                return True
        return False

    async def create_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicAppointmentCreateRequest,
        ends_at: datetime,
        tz_name: str,
        doctor_name: str,
        consultation_type_name: str,
    ) -> ClinicAppointmentResponse:
        async with self._lock:
            if payload.idempotency_key:
                existing_id = self._idempotency.get((business_id, payload.idempotency_key))
                if existing_id and existing_id in self._appointments:
                    return self._appointments[existing_id]

            if self._has_overlap(
                doctor_id=payload.doctor_id,
                starts_at=payload.starts_at,
                ends_at=ends_at,
            ):
                raise ClinicConflictError(
                    "Selected time slot is no longer available for this doctor."
                )

            now = self._now()
            appt_id = uuid4()
            ref = f"CLN-{appt_id.hex[:8].upper()}"
            appt = ClinicAppointmentResponse(
                id=appt_id,
                organization_id=organization_id,
                business_id=business_id,
                booking_reference=ref,
                doctor_id=payload.doctor_id,
                doctor_name=doctor_name,
                consultation_type_id=payload.consultation_type_id,
                consultation_type_name=consultation_type_name,
                department_id=payload.department_id,
                patient_display_name=payload.patient_display_name.strip(),
                patient_contact=payload.patient_contact.strip(),
                starts_at=payload.starts_at,
                ends_at=ends_at,
                timezone=tz_name,
                status=ClinicAppointmentStatus.CONFIRMED,
                source=payload.source,
                cancellation_reason=None,
                cancelled_at=None,
                created_at=now,
                updated_at=now,
            )
            self._appointments[appt.id] = appt
            if payload.idempotency_key:
                self._idempotency[(business_id, payload.idempotency_key)] = appt.id
            return appt

    async def reschedule_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        new_doctor_id: UUID,
        new_doctor_name: str,
        new_starts_at: datetime,
        new_ends_at: datetime,
    ) -> ClinicAppointmentResponse:
        async with self._lock:
            existing = await self.get_appointment(organization_id, business_id, appointment_id)
            if not existing:
                raise ClinicNotFoundError("Appointment not found.")
            if existing.status == ClinicAppointmentStatus.CANCELLED:
                raise ClinicConflictError("Cancelled appointments cannot be rescheduled.")

            if self._has_overlap(
                doctor_id=new_doctor_id,
                starts_at=new_starts_at,
                ends_at=new_ends_at,
                exclude_appointment_id=appointment_id,
            ):
                raise ClinicConflictError(
                    "Requested new time slot conflicts with an existing doctor appointment."
                )

            updated = existing.model_copy(
                update={
                    "doctor_id": new_doctor_id,
                    "doctor_name": new_doctor_name,
                    "starts_at": new_starts_at,
                    "ends_at": new_ends_at,
                    "status": ClinicAppointmentStatus.RESCHEDULED,
                    "updated_at": self._now(),
                }
            )
            self._appointments[appointment_id] = updated
            return updated

    async def cancel_appointment_atomic(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        reason: Optional[str],
    ) -> ClinicAppointmentResponse:
        async with self._lock:
            existing = await self.get_appointment(organization_id, business_id, appointment_id)
            if not existing:
                raise ClinicNotFoundError("Appointment not found.")
            if existing.status == ClinicAppointmentStatus.CANCELLED:
                return existing  # Idempotent cancellation

            now = self._now()
            updated = existing.model_copy(
                update={
                    "status": ClinicAppointmentStatus.CANCELLED,
                    "cancellation_reason": reason.strip() if reason else None,
                    "cancelled_at": now,
                    "updated_at": now,
                }
            )
            self._appointments[appointment_id] = updated
            return updated
