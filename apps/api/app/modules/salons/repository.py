"""Repository layer for Stage 5 Salon Workflow Module.

Provides:
1. `SalonRepositoryProtocol` — formal interface for salon data operations.
2. `InMemorySalonRepository` — thread-safe multi-tenant in-memory persistence with
   double-booking prevention, concurrency locks, and idempotency tracking.
3. `SupabaseRestSalonRepository` — Supabase PostgREST persistence forwarding the
   caller's Bearer JWT to enforce PostgreSQL RLS and database exclusion constraints.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
from typing import Dict, List, Optional, Protocol, Set, Tuple
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.modules.organizations.schemas import OrganizationRole
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentResponse,
    SalonAppointmentSource,
    SalonAppointmentStatus,
    SalonHolidayCreateRequest,
    SalonHolidayResponse,
    SalonServiceCreateRequest,
    SalonServiceResponse,
    SalonServiceUpdateRequest,
    SalonStaffBreakCreateRequest,
    SalonStaffBreakResponse,
    SalonStaffCreateRequest,
    SalonStaffResponse,
    SalonStaffUpdateRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
    parse_hhmm_to_minutes,
)


class SalonRepositoryProtocol(Protocol):
    """Protocol defining all Stage 5 salon data operations."""

    # Services
    async def create_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonServiceCreateRequest
    ) -> SalonServiceResponse: ...

    async def get_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID
    ) -> SalonServiceResponse: ...

    async def list_services(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, category: Optional[str] = None, is_active: Optional[bool] = None
    ) -> List[SalonServiceResponse]: ...

    async def update_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID, payload: SalonServiceUpdateRequest
    ) -> SalonServiceResponse: ...

    async def delete_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID
    ) -> None: ...

    # Staff
    async def create_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonStaffCreateRequest
    ) -> SalonStaffResponse: ...

    async def get_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> SalonStaffResponse: ...

    async def list_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: Optional[UUID] = None, is_active: Optional[bool] = None
    ) -> List[SalonStaffResponse]: ...

    async def update_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffUpdateRequest
    ) -> SalonStaffResponse: ...

    async def delete_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> None: ...

    async def assign_staff_services(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, service_ids: List[UUID]
    ) -> SalonStaffResponse: ...

    # Schedules & Breaks
    async def update_staff_working_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffWorkingHoursUpdateRequest
    ) -> List[SalonStaffWorkingHoursItem]: ...

    async def get_staff_working_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> List[SalonStaffWorkingHoursItem]: ...

    async def add_staff_break(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffBreakCreateRequest
    ) -> SalonStaffBreakResponse: ...

    async def list_staff_breaks(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> List[SalonStaffBreakResponse]: ...

    async def delete_staff_break(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, break_id: UUID
    ) -> None: ...

    # Holidays & Closures
    async def create_holiday(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonHolidayCreateRequest
    ) -> SalonHolidayResponse: ...

    async def list_holidays(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[SalonHolidayResponse]: ...

    async def delete_holiday(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, holiday_id: UUID
    ) -> None: ...

    # Appointments
    async def create_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment: SalonAppointmentResponse
    ) -> SalonAppointmentResponse: ...

    async def get_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> SalonAppointmentResponse: ...

    async def get_appointment_by_idempotency_key(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, idempotency_key: str
    ) -> Optional[SalonAppointmentResponse]: ...

    async def list_appointments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_date: Optional[date] = None,
        staff_id: Optional[UUID] = None,
        status: Optional[SalonAppointmentStatus] = None,
    ) -> List[SalonAppointmentResponse]: ...

    async def update_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment: SalonAppointmentResponse
    ) -> SalonAppointmentResponse: ...


def _default_staff_working_hours() -> List[SalonStaffWorkingHoursItem]:
    """Default staff working hours (Mon-Sat 09:00-18:00, Sun off)."""
    items: List[SalonStaffWorkingHoursItem] = []
    for day in range(7):
        if day == 0:
            items.append(SalonStaffWorkingHoursItem(weekday=0, is_off=True, start_time=None, end_time=None))
        else:
            items.append(SalonStaffWorkingHoursItem(weekday=day, is_off=False, start_time="09:00", end_time="18:00"))
    return items


class InMemorySalonRepository:
    """Thread-safe multi-tenant in-memory repository for salon operations."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._services: Dict[UUID, List[SalonServiceResponse]] = {}  # business_id -> services
        self._staff: Dict[UUID, List[SalonStaffResponse]] = {}  # business_id -> staff
        self._working_hours: Dict[UUID, List[SalonStaffWorkingHoursItem]] = {}  # staff_id -> hours
        self._breaks: Dict[UUID, List[SalonStaffBreakResponse]] = {}  # staff_id -> breaks
        self._holidays: Dict[UUID, List[SalonHolidayResponse]] = {}  # business_id -> holidays
        self._appointments: Dict[UUID, List[SalonAppointmentResponse]] = {}  # business_id -> appointments

    def clear(self) -> None:
        """Clear all in-memory salon state."""
        self._services.clear()
        self._staff.clear()
        self._working_hours.clear()
        self._breaks.clear()
        self._holidays.clear()
        self._appointments.clear()

    # -------------------------------------------------------------------------
    # Services CRUD
    # -------------------------------------------------------------------------
    async def create_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonServiceCreateRequest
    ) -> SalonServiceResponse:
        async with self._lock:
            now = datetime.now(timezone.utc)
            service = SalonServiceResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                name=payload.name,
                description=payload.description,
                category=payload.category,
                price=payload.price,
                currency=payload.currency,
                duration_minutes=payload.duration_minutes,
                is_active=payload.is_active,
                created_at=now,
                updated_at=now,
            )
            self._services.setdefault(business_id, []).append(service)
            return service

    async def get_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID
    ) -> SalonServiceResponse:
        services = self._services.get(business_id, [])
        for svc in services:
            if svc.id == service_id and svc.organization_id == organization_id:
                return svc
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salon service '{service_id}' was not found in this organization.",
        )

    async def list_services(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, category: Optional[str] = None, is_active: Optional[bool] = None
    ) -> List[SalonServiceResponse]:
        services = self._services.get(business_id, [])
        filtered: List[SalonServiceResponse] = []
        for svc in services:
            if svc.organization_id != organization_id:
                continue
            if category and svc.category.lower() != category.lower().strip():
                continue
            if is_active is not None and svc.is_active != is_active:
                continue
            filtered.append(svc)
        return filtered

    async def update_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID, payload: SalonServiceUpdateRequest
    ) -> SalonServiceResponse:
        async with self._lock:
            existing = await self.get_service(actor, organization_id, business_id, service_id)
            services = self._services[business_id]
            idx = services.index(existing)

            now = datetime.now(timezone.utc)
            updated = SalonServiceResponse(
                id=existing.id,
                organization_id=organization_id,
                business_id=business_id,
                name=payload.name if payload.name is not None else existing.name,
                description=payload.description if payload.description is not None else existing.description,
                category=payload.category if payload.category is not None else existing.category,
                price=payload.price if payload.price is not None else existing.price,
                currency=payload.currency if payload.currency is not None else existing.currency,
                duration_minutes=payload.duration_minutes if payload.duration_minutes is not None else existing.duration_minutes,
                is_active=payload.is_active if payload.is_active is not None else existing.is_active,
                created_at=existing.created_at,
                updated_at=now,
            )
            services[idx] = updated
            return updated

    async def delete_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID
    ) -> None:
        async with self._lock:
            existing = await self.get_service(actor, organization_id, business_id, service_id)
            # Check for active appointments
            appointments = self._appointments.get(business_id, [])
            for appt in appointments:
                if appt.service_id == service_id and appt.status in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot delete salon service with active confirmed or rescheduled appointments. Deactivate the service instead.",
                    )
            self._services[business_id].remove(existing)

    # -------------------------------------------------------------------------
    # Staff Management & Assignments
    # -------------------------------------------------------------------------
    async def create_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonStaffCreateRequest
    ) -> SalonStaffResponse:
        async with self._lock:
            now = datetime.now(timezone.utc)
            staff_id = uuid4()

            # Resolve service names
            assigned_names: List[str] = []
            valid_service_ids: List[UUID] = []
            all_services = self._services.get(business_id, [])
            svc_map = {s.id: s.name for s in all_services if s.organization_id == organization_id}

            for sid in payload.assigned_service_ids:
                if sid in svc_map:
                    valid_service_ids.append(sid)
                    assigned_names.append(svc_map[sid])

            default_wh = _default_staff_working_hours()
            self._working_hours[staff_id] = default_wh
            self._breaks[staff_id] = []

            staff = SalonStaffResponse(
                id=staff_id,
                organization_id=organization_id,
                business_id=business_id,
                full_name=payload.full_name,
                role_designation=payload.role_designation,
                email=payload.email,
                phone=payload.phone,
                bio=payload.bio,
                is_active=payload.is_active,
                assigned_service_ids=valid_service_ids,
                assigned_service_names=assigned_names,
                working_hours=default_wh,
                breaks=[],
                created_at=now,
                updated_at=now,
            )
            self._staff.setdefault(business_id, []).append(staff)
            return staff

    async def get_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> SalonStaffResponse:
        staff_list = self._staff.get(business_id, [])
        for st in staff_list:
            if st.id == staff_id and st.organization_id == organization_id:
                # refresh live working hours and breaks
                st.working_hours = self._working_hours.get(staff_id, _default_staff_working_hours())
                st.breaks = self._breaks.get(staff_id, [])
                return st
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member '{staff_id}' was not found in this organization.",
        )

    async def list_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: Optional[UUID] = None, is_active: Optional[bool] = None
    ) -> List[SalonStaffResponse]:
        staff_list = self._staff.get(business_id, [])
        filtered: List[SalonStaffResponse] = []
        for st in staff_list:
            if st.organization_id != organization_id:
                continue
            if is_active is not None and st.is_active != is_active:
                continue
            if service_id and service_id not in st.assigned_service_ids:
                continue
            st.working_hours = self._working_hours.get(st.id, _default_staff_working_hours())
            st.breaks = self._breaks.get(st.id, [])
            filtered.append(st)
        return filtered

    async def update_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffUpdateRequest
    ) -> SalonStaffResponse:
        async with self._lock:
            existing = await self.get_staff(actor, organization_id, business_id, staff_id)
            staff_list = self._staff[business_id]
            idx = staff_list.index(existing)

            assigned_ids = existing.assigned_service_ids
            assigned_names = existing.assigned_service_names
            if payload.assigned_service_ids is not None:
                all_services = self._services.get(business_id, [])
                svc_map = {s.id: s.name for s in all_services if s.organization_id == organization_id}
                assigned_ids = [sid for sid in payload.assigned_service_ids if sid in svc_map]
                assigned_names = [svc_map[sid] for sid in assigned_ids]

            now = datetime.now(timezone.utc)
            updated = SalonStaffResponse(
                id=existing.id,
                organization_id=organization_id,
                business_id=business_id,
                full_name=payload.full_name if payload.full_name is not None else existing.full_name,
                role_designation=payload.role_designation if payload.role_designation is not None else existing.role_designation,
                email=payload.email if payload.email is not None else existing.email,
                phone=payload.phone if payload.phone is not None else existing.phone,
                bio=payload.bio if payload.bio is not None else existing.bio,
                is_active=payload.is_active if payload.is_active is not None else existing.is_active,
                assigned_service_ids=assigned_ids,
                assigned_service_names=assigned_names,
                working_hours=self._working_hours.get(staff_id, _default_staff_working_hours()),
                breaks=self._breaks.get(staff_id, []),
                created_at=existing.created_at,
                updated_at=now,
            )
            staff_list[idx] = updated
            return updated

    async def delete_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> None:
        async with self._lock:
            existing = await self.get_staff(actor, organization_id, business_id, staff_id)
            appointments = self._appointments.get(business_id, [])
            for appt in appointments:
                if appt.staff_id == staff_id and appt.status in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot delete staff member with active confirmed or rescheduled appointments. Deactivate the staff profile instead.",
                    )
            self._staff[business_id].remove(existing)
            self._working_hours.pop(staff_id, None)
            self._breaks.pop(staff_id, None)

    async def assign_staff_services(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, service_ids: List[UUID]
    ) -> SalonStaffResponse:
        update_req = SalonStaffUpdateRequest(assigned_service_ids=service_ids)
        return await self.update_staff(actor, organization_id, business_id, staff_id, update_req)

    # -------------------------------------------------------------------------
    # Schedules & Breaks
    # -------------------------------------------------------------------------
    async def update_staff_working_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffWorkingHoursUpdateRequest
    ) -> List[SalonStaffWorkingHoursItem]:
        async with self._lock:
            await self.get_staff(actor, organization_id, business_id, staff_id)
            existing_map = {item.weekday: item for item in self._working_hours.get(staff_id, _default_staff_working_hours())}
            for updated_item in payload.schedule:
                existing_map[updated_item.weekday] = updated_item
            sorted_hours = [existing_map[day] for day in range(7) if day in existing_map]
            self._working_hours[staff_id] = sorted_hours
            return sorted_hours

    async def get_staff_working_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> List[SalonStaffWorkingHoursItem]:
        await self.get_staff(actor, organization_id, business_id, staff_id)
        return self._working_hours.get(staff_id, _default_staff_working_hours())

    async def add_staff_break(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffBreakCreateRequest
    ) -> SalonStaffBreakResponse:
        async with self._lock:
            await self.get_staff(actor, organization_id, business_id, staff_id)
            now = datetime.now(timezone.utc)
            break_item = SalonStaffBreakResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                staff_id=staff_id,
                weekday=payload.weekday,
                specific_date=payload.specific_date,
                label=payload.label,
                start_time=payload.start_time,
                end_time=payload.end_time,
                created_at=now,
            )
            self._breaks.setdefault(staff_id, []).append(break_item)
            return break_item

    async def list_staff_breaks(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> List[SalonStaffBreakResponse]:
        await self.get_staff(actor, organization_id, business_id, staff_id)
        return self._breaks.get(staff_id, [])

    async def delete_staff_break(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, break_id: UUID
    ) -> None:
        async with self._lock:
            await self.get_staff(actor, organization_id, business_id, staff_id)
            breaks = self._breaks.get(staff_id, [])
            for b in breaks:
                if b.id == break_id:
                    breaks.remove(b)
                    return
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff break '{break_id}' was not found.",
            )

    # -------------------------------------------------------------------------
    # Holidays & Closures
    # -------------------------------------------------------------------------
    async def create_holiday(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonHolidayCreateRequest
    ) -> SalonHolidayResponse:
        async with self._lock:
            now = datetime.now(timezone.utc)
            staff_name: Optional[str] = None
            if payload.staff_id:
                staff_profile = await self.get_staff(actor, organization_id, business_id, payload.staff_id)
                staff_name = staff_profile.full_name

            holiday = SalonHolidayResponse(
                id=uuid4(),
                organization_id=organization_id,
                business_id=business_id,
                staff_id=payload.staff_id,
                staff_name=staff_name,
                holiday_date=payload.holiday_date,
                title=payload.title,
                is_closed_all_day=payload.is_closed_all_day,
                start_time=payload.start_time,
                end_time=payload.end_time,
                created_at=now,
            )
            self._holidays.setdefault(business_id, []).append(holiday)
            return holiday

    async def list_holidays(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[SalonHolidayResponse]:
        holidays = self._holidays.get(business_id, [])
        filtered: List[SalonHolidayResponse] = []
        for h in holidays:
            if h.organization_id != organization_id:
                continue
            if start_date and h.holiday_date < start_date:
                continue
            if end_date and h.holiday_date > end_date:
                continue
            filtered.append(h)
        return sorted(filtered, key=lambda x: x.holiday_date)

    async def delete_holiday(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, holiday_id: UUID
    ) -> None:
        async with self._lock:
            holidays = self._holidays.get(business_id, [])
            for h in holidays:
                if h.id == holiday_id and h.organization_id == organization_id:
                    holidays.remove(h)
                    return
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Salon holiday/closure '{holiday_id}' was not found.",
            )

    # -------------------------------------------------------------------------
    # Appointments Management with Concurrency & Idempotency
    # -------------------------------------------------------------------------
    async def create_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment: SalonAppointmentResponse
    ) -> SalonAppointmentResponse:
        async with self._lock:
            # Idempotency check: if an appointment with this idempotency key already exists, return it
            if appointment.idempotency_key:
                existing = await self.get_appointment_by_idempotency_key(
                    actor, organization_id, business_id, appointment.idempotency_key
                )
                if existing:
                    return existing

            # Double-booking check: no overlapping confirmed/rescheduled appointment for the same staff
            existing_appts = self._appointments.get(business_id, [])
            for existing in existing_appts:
                if existing.staff_id != appointment.staff_id:
                    continue
                if existing.status not in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}:
                    continue
                # Overlap test: [start_at, end_at)
                if max(existing.start_at, appointment.start_at) < min(existing.end_at, appointment.end_at):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Appointment collision: Staff member is already booked from "
                            f"{existing.start_time} to {existing.end_time} on {existing.appointment_date}."
                        ),
                    )

            self._appointments.setdefault(business_id, []).append(appointment)
            return appointment

    async def get_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> SalonAppointmentResponse:
        appointments = self._appointments.get(business_id, [])
        for appt in appointments:
            if appt.id == appointment_id and appt.organization_id == organization_id:
                return appt
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salon appointment '{appointment_id}' was not found.",
        )

    async def get_appointment_by_idempotency_key(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, idempotency_key: str
    ) -> Optional[SalonAppointmentResponse]:
        appointments = self._appointments.get(business_id, [])
        for appt in appointments:
            if appt.organization_id == organization_id and appt.idempotency_key == idempotency_key:
                return appt
        return None

    async def list_appointments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_date: Optional[date] = None,
        staff_id: Optional[UUID] = None,
        status: Optional[SalonAppointmentStatus] = None,
    ) -> List[SalonAppointmentResponse]:
        appointments = self._appointments.get(business_id, [])
        filtered: List[SalonAppointmentResponse] = []
        for appt in appointments:
            if appt.organization_id != organization_id:
                continue
            if appointment_date and appt.appointment_date != appointment_date:
                continue
            if staff_id and appt.staff_id != staff_id:
                continue
            if status and appt.status != status:
                continue
            filtered.append(appt)
        return sorted(filtered, key=lambda a: (a.appointment_date, a.start_time))

    async def update_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment: SalonAppointmentResponse
    ) -> SalonAppointmentResponse:
        async with self._lock:
            existing = await self.get_appointment(actor, organization_id, business_id, appointment.id)
            appointments = self._appointments[business_id]
            idx = appointments.index(existing)

            # Check overlap if new timing conflicts with other appointments
            if appointment.status in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}:
                for other in appointments:
                    if other.id == appointment.id:
                        continue
                    if other.staff_id != appointment.staff_id:
                        continue
                    if other.status not in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}:
                        continue
                    if max(other.start_at, appointment.start_at) < min(other.end_at, appointment.end_at):
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                f"Appointment collision on update: Staff member is already booked from "
                                f"{other.start_time} to {other.end_time} on {other.appointment_date}."
                            ),
                        )

            appointments[idx] = appointment
            return appointment


_in_memory_salon_repo = InMemorySalonRepository()


def get_in_memory_salon_repository() -> InMemorySalonRepository:
    """Return the singleton InMemorySalonRepository instance."""
    return _in_memory_salon_repo
