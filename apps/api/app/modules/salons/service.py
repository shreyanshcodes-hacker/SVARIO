"""Service layer for Stage 5 Salon Workflow Module.

Orchestrates:
- Salon Services CRUD with price (> 0) and duration (5-480 min) validation.
- Staff Profiles, Assignments, Schedules, Breaks, and Holidays.
- Real-time dynamic Availability Calculation considering opening hours,
  staff shifts, breaks, holidays, and active bookings.
- Appointment Booking, Rescheduling, and Cancellation with database
  concurrency protection, idempotency handling, and audit logging.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.core.internal_voice import (
    INTERNAL_VOICE_ISSUER,
    verify_internal_voice_actor,
)
from app.modules.onboarding.repository import OnboardingRepositoryProtocol
from app.modules.onboarding.schemas import BusinessHoursResponse
from app.modules.onboarding.service import get_onboarding_repository
from app.modules.organizations.schemas import OrganizationIndustry, OrganizationRole
from app.modules.salons.repository import (
    InMemorySalonRepository,
    SalonRepositoryProtocol,
    get_in_memory_salon_repository,
)
from app.modules.salons.supabase_repository import SupabaseRestSalonRepository
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentResponse,
    SalonAppointmentSource,
    SalonAppointmentStatus,
    SalonAvailabilityResponse,
    SalonAvailabilitySlot,
    SalonAvailabilityStatus,
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
    format_minutes_to_hhmm,
    normalize_time_string,
    parse_hhmm_to_minutes,
)

logger = logging.getLogger("svario.salons.availability")


_TIMEZONE_ALIASES: Dict[str, str] = {
    "IST": "Asia/Kolkata",
    "IND": "Asia/Kolkata",
    "INDIA": "Asia/Kolkata",
}


def _canonicalize_timezone_name(tz_str: Optional[str]) -> str:
    cleaned = (tz_str or "").strip()
    if not cleaned:
        return "Asia/Kolkata"
    return _TIMEZONE_ALIASES.get(cleaned.upper(), cleaned)


class SalonWorkflowService:
    """Domain service for Salon Workflow management."""

    def __init__(
        self,
        settings: Settings,
        salon_repo: SalonRepositoryProtocol,
        onboarding_repo: OnboardingRepositoryProtocol,
    ) -> None:
        self._settings = settings
        self._salon_repo = salon_repo
        self._onboarding_repo = onboarding_repo

    async def _verify_org_access(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        require_admin: bool = False,
    ) -> OrganizationRole:
        """Verify tenant membership, salon industry, internal voice binding, and role."""
        if actor.issuer == INTERNAL_VOICE_ISSUER:
            verify_internal_voice_actor(
                actor,
                organization_id=organization_id,
                business_id=business_id,
                expected_industry=OrganizationIndustry.SALON,
            )
            if require_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: voice agent cannot modify administrative configuration.",
                )
            return OrganizationRole.STAFF

        role = await self._onboarding_repo.get_member_role(actor, organization_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )

        org_detail = await self._onboarding_repo.get_organization_detail(actor, organization_id)
        if org_detail.industry != OrganizationIndustry.SALON:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Salon workflow operations are only valid for salon organizations.",
            )

        if require_admin and role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: salon administrative privileges (owner or admin) required.",
            )
        return role

    async def _resolve_business_timezone(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        business_hours_override: Optional[BusinessHoursResponse] = None,
    ) -> str:
        """Retrieve the configured business timezone (defaulting to Asia/Kolkata or UTC)."""
        if business_hours_override is not None and business_hours_override.timezone:
            return _canonicalize_timezone_name(business_hours_override.timezone)
        try:
            hours = await self._onboarding_repo.get_business_hours(actor, organization_id, business_id)
            return _canonicalize_timezone_name(hours.timezone)
        except Exception:
            return "Asia/Kolkata"

    # =========================================================================
    # A. SALON SERVICES CRUD
    # =========================================================================
    async def create_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonServiceCreateRequest
    ) -> SalonServiceResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        if payload.price <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Salon service price must be strictly greater than 0.",
            )
        if payload.duration_minutes < 5 or payload.duration_minutes > 480:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Salon service duration must be between 5 and 480 minutes.",
            )
        return await self._salon_repo.create_service(actor, organization_id, business_id, payload)

    async def get_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID
    ) -> SalonServiceResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.get_service(actor, organization_id, business_id, service_id)

    async def list_services(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, category: Optional[str] = None, is_active: Optional[bool] = None
    ) -> List[SalonServiceResponse]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.list_services(actor, organization_id, business_id, category, is_active)

    async def update_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID, payload: SalonServiceUpdateRequest
    ) -> SalonServiceResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        if payload.price is not None and payload.price <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Salon service price must be strictly greater than 0.",
            )
        if payload.duration_minutes is not None and (payload.duration_minutes < 5 or payload.duration_minutes > 480):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Salon service duration must be between 5 and 480 minutes.",
            )
        return await self._salon_repo.update_service(actor, organization_id, business_id, service_id, payload)

    async def delete_service(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: UUID
    ) -> None:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._salon_repo.delete_service(actor, organization_id, business_id, service_id)

    # =========================================================================
    # B. STAFF MANAGEMENT
    # =========================================================================
    async def create_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonStaffCreateRequest
    ) -> SalonStaffResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._salon_repo.create_staff(actor, organization_id, business_id, payload)

    async def get_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> SalonStaffResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.get_staff(actor, organization_id, business_id, staff_id)

    async def list_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, service_id: Optional[UUID] = None, is_active: Optional[bool] = None
    ) -> List[SalonStaffResponse]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.list_staff(actor, organization_id, business_id, service_id, is_active)

    async def update_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffUpdateRequest
    ) -> SalonStaffResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._salon_repo.update_staff(actor, organization_id, business_id, staff_id, payload)

    async def delete_staff(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> None:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._salon_repo.delete_staff(actor, organization_id, business_id, staff_id)

    async def assign_staff_services(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, service_ids: List[UUID]
    ) -> SalonStaffResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._salon_repo.assign_staff_services(actor, organization_id, business_id, staff_id, service_ids)

    # =========================================================================
    # C. WORKING SCHEDULES, BREAKS & HOLIDAYS
    # =========================================================================
    async def update_staff_working_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffWorkingHoursUpdateRequest
    ) -> List[SalonStaffWorkingHoursItem]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._salon_repo.update_staff_working_hours(actor, organization_id, business_id, staff_id, payload)

    async def get_staff_working_hours(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> List[SalonStaffWorkingHoursItem]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.get_staff_working_hours(actor, organization_id, business_id, staff_id)

    async def add_staff_break(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, payload: SalonStaffBreakCreateRequest
    ) -> SalonStaffBreakResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._salon_repo.add_staff_break(actor, organization_id, business_id, staff_id, payload)

    async def list_staff_breaks(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID
    ) -> List[SalonStaffBreakResponse]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.list_staff_breaks(actor, organization_id, business_id, staff_id)

    async def delete_staff_break(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, staff_id: UUID, break_id: UUID
    ) -> None:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._salon_repo.delete_staff_break(actor, organization_id, business_id, staff_id, break_id)

    async def create_holiday(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, payload: SalonHolidayCreateRequest
    ) -> SalonHolidayResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._salon_repo.create_holiday(actor, organization_id, business_id, payload)

    async def list_holidays(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[SalonHolidayResponse]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.list_holidays(actor, organization_id, business_id, start_date, end_date)

    async def delete_holiday(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, holiday_id: UUID
    ) -> None:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._salon_repo.delete_holiday(actor, organization_id, business_id, holiday_id)

    # =========================================================================
    # D. APPOINTMENT AVAILABILITY ENGINE
    # =========================================================================
    async def get_salon_availability(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        service_id: UUID,
        requested_date: date,
        staff_id: Optional[UUID] = None,
        requested_time: Optional[str] = None,
        business_hours_override: Optional[BusinessHoursResponse] = None,
    ) -> SalonAvailabilityResponse:
        """Compute all non-conflicting bookable slots for a service and date."""
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        normalized_req_time = normalize_time_string(requested_time) if requested_time else None

        service = await self._salon_repo.get_service(actor, organization_id, business_id, service_id)
        if not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Salon service '{service.name}' is currently inactive and cannot be booked.",
            )

        tz_str = await self._resolve_business_timezone(
            actor,
            organization_id,
            business_id,
            business_hours_override=business_hours_override,
        )
        try:
            tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            tz = timezone.utc

        # 1. Check business opening hours for this weekday (Python weekday: 0=Mon..6=Sun; convert to Svario 0=Sun..6=Sat)
        py_weekday = requested_date.weekday()
        svario_weekday = (py_weekday + 1) % 7

        biz_hours_resp = (
            business_hours_override
            if business_hours_override is not None
            else await self._onboarding_repo.get_business_hours(actor, organization_id, business_id)
        )
        matching_hours = next((h for h in biz_hours_resp.schedule if h.weekday == svario_weekday), None)
        if matching_hours is None or matching_hours.is_closed or not matching_hours.opens_at or not matching_hours.closes_at:
            reason = "Salon is closed on this day of the week according to regular operating hours."
            logger.info(
                "salon_availability business_id=%s service_id=%s date=%s weekday=%s tz=%s status=BUSINESS_CLOSED",
                business_id, service.id, requested_date, svario_weekday, tz_str,
            )
            return SalonAvailabilityResponse(
                organization_id=organization_id,
                business_id=business_id,
                service_id=service.id,
                service_name=service.name,
                duration_minutes=service.duration_minutes,
                price=service.price,
                currency=service.currency,
                requested_date=requested_date,
                timezone=tz_str,
                is_business_closed=True,
                closure_reason=reason,
                availability_status=SalonAvailabilityStatus.BUSINESS_CLOSED,
                status_reason=reason,
                requested_time=normalized_req_time,
                requested_time_available=False if normalized_req_time else None,
                available_slots=[],
            )

        biz_open_min = parse_hhmm_to_minutes(matching_hours.opens_at)
        biz_close_min = parse_hhmm_to_minutes(matching_hours.closes_at)

        # 2. Check whole-salon holidays/closures for this date
        holidays = await self._salon_repo.list_holidays(actor, organization_id, business_id, start_date=requested_date, end_date=requested_date)
        salon_closure = next((h for h in holidays if h.staff_id is None and h.is_closed_all_day), None)
        if salon_closure:
            reason = f"Salon is closed for holiday: {salon_closure.title}"
            logger.info(
                "salon_availability business_id=%s service_id=%s date=%s weekday=%s tz=%s status=BUSINESS_CLOSED reason=holiday",
                business_id, service.id, requested_date, svario_weekday, tz_str,
            )
            return SalonAvailabilityResponse(
                organization_id=organization_id,
                business_id=business_id,
                service_id=service.id,
                service_name=service.name,
                duration_minutes=service.duration_minutes,
                price=service.price,
                currency=service.currency,
                requested_date=requested_date,
                timezone=tz_str,
                is_business_closed=True,
                closure_reason=reason,
                availability_status=SalonAvailabilityStatus.BUSINESS_CLOSED,
                status_reason=reason,
                requested_time=normalized_req_time,
                requested_time_available=False if normalized_req_time else None,
                available_slots=[],
            )

        partial_salon_closures = [
            (parse_hhmm_to_minutes(h.start_time), parse_hhmm_to_minutes(h.end_time))
            for h in holidays
            if h.staff_id is None and not h.is_closed_all_day and h.start_time and h.end_time
        ]

        # 3. Resolve qualified staff
        qualified_staff: List[SalonStaffResponse] = []
        if staff_id is not None:
            st = await self._salon_repo.get_staff(actor, organization_id, business_id, staff_id)
            if not st.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Staff member '{st.full_name}' is currently inactive.",
                )
            if service.id not in st.assigned_service_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Staff member '{st.full_name}' is not qualified/assigned for service '{service.name}'.",
                )
            qualified_staff.append(st)
        else:
            all_staff = await self._salon_repo.list_staff(actor, organization_id, business_id, service_id=service.id, is_active=True)
            qualified_staff.extend(all_staff)

        if not qualified_staff:
            reason = (
                f"No active stylist is currently assigned to '{service.name}'. "
                "Please add an active stylist and assign this service in the Salon Dashboard before booking."
            )
            logger.warning(
                "salon_availability business_id=%s service_id=%s date=%s weekday=%s tz=%s status=NO_QUALIFIED_STAFF",
                business_id, service.id, requested_date, svario_weekday, tz_str,
            )
            return SalonAvailabilityResponse(
                organization_id=organization_id,
                business_id=business_id,
                service_id=service.id,
                service_name=service.name,
                duration_minutes=service.duration_minutes,
                price=service.price,
                currency=service.currency,
                requested_date=requested_date,
                timezone=tz_str,
                is_business_closed=False,
                closure_reason=None,
                availability_status=SalonAvailabilityStatus.NO_QUALIFIED_STAFF,
                status_reason=reason,
                requested_time=normalized_req_time,
                requested_time_available=False if normalized_req_time else None,
                available_slots=[],
            )

        # 4. Fetch existing active appointments for this date
        existing_appointments = await self._salon_repo.list_appointments(
            actor, organization_id, business_id, appointment_date=requested_date
        )
        active_appts = [
            a for a in existing_appointments
            if a.status in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}
        ]

        # 5. Compute available slots
        available_slots: List[SalonAvailabilitySlot] = []
        slot_step_minutes = 15
        duration = service.duration_minutes
        staff_with_valid_schedule = 0
        staff_with_missing_schedule = 0

        for staff in qualified_staff:
            # Check staff leave/holiday
            staff_leave = next((h for h in holidays if h.staff_id == staff.id and h.is_closed_all_day), None)
            if staff_leave:
                staff_with_valid_schedule += 1
                continue

            # Check staff working hours for this weekday
            wh_item = next((wh for wh in staff.working_hours if wh.weekday == svario_weekday), None)
            if wh_item is None or (not wh_item.is_off and (not wh_item.start_time or not wh_item.end_time)):
                staff_with_missing_schedule += 1
                continue
            staff_with_valid_schedule += 1
            if wh_item.is_off or not wh_item.start_time or not wh_item.end_time:
                continue

            staff_start_min = max(biz_open_min, parse_hhmm_to_minutes(wh_item.start_time))
            staff_end_min = min(biz_close_min, parse_hhmm_to_minutes(wh_item.end_time))
            if staff_start_min + duration > staff_end_min:
                continue

            # Gather breaks for this staff member (recurring or date-specific)
            staff_breaks_min: List[Tuple[int, int]] = []
            for brk in staff.breaks:
                if (brk.weekday is not None and brk.weekday == svario_weekday) or (brk.specific_date == requested_date):
                    staff_breaks_min.append((parse_hhmm_to_minutes(brk.start_time), parse_hhmm_to_minutes(brk.end_time)))

            # Staff-specific partial leaves
            for h in holidays:
                if h.staff_id == staff.id and not h.is_closed_all_day and h.start_time and h.end_time:
                    staff_breaks_min.append((parse_hhmm_to_minutes(h.start_time), parse_hhmm_to_minutes(h.end_time)))

            # Existing appointments for this staff
            staff_appts_min: List[Tuple[int, int]] = [
                (parse_hhmm_to_minutes(a.start_time), parse_hhmm_to_minutes(a.end_time))
                for a in active_appts
                if a.staff_id == staff.id
            ]

            # Slide slots
            current_start_min = staff_start_min
            while current_start_min + duration <= staff_end_min:
                candidate_start = current_start_min
                candidate_end = current_start_min + duration

                # Check conflict with partial salon closures
                conflict = any(max(candidate_start, c_s) < min(candidate_end, c_e) for c_s, c_e in partial_salon_closures)
                if not conflict:
                    # Check conflict with staff breaks
                    conflict = any(max(candidate_start, b_s) < min(candidate_end, b_e) for b_s, b_e in staff_breaks_min)
                if not conflict:
                    # Check conflict with existing appointments
                    conflict = any(max(candidate_start, a_s) < min(candidate_end, a_e) for a_s, a_e in staff_appts_min)

                if not conflict:
                    start_str = format_minutes_to_hhmm(candidate_start)
                    end_str = format_minutes_to_hhmm(candidate_end)

                    start_dt = datetime.combine(
                        requested_date,
                        time(candidate_start // 60, candidate_start % 60),
                        tzinfo=tz,
                    )
                    end_dt = datetime.combine(
                        requested_date,
                        time(candidate_end // 60, candidate_end % 60),
                        tzinfo=tz,
                    )

                    available_slots.append(
                        SalonAvailabilitySlot(
                            start_time=start_str,
                            end_time=end_str,
                            start_at=start_dt,
                            end_at=end_dt,
                            staff_id=staff.id,
                            staff_name=staff.full_name,
                            staff_role=staff.role_designation,
                        )
                    )

                current_start_min += slot_step_minutes

        available_slots.sort(key=lambda s: (s.start_time, s.staff_name))

        req_time_available: Optional[bool] = None
        if normalized_req_time is not None:
            req_time_available = any(s.start_time == normalized_req_time for s in available_slots)

        if available_slots:
            if normalized_req_time is not None and not req_time_available:
                avail_status = SalonAvailabilityStatus.REQUESTED_TIME_UNAVAILABLE
                status_reason = (
                    f"The requested time {normalized_req_time} is not available for '{service.name}' on {requested_date}, "
                    f"but {len(available_slots)} alternative slot(s) are open on that date."
                )
            else:
                avail_status = SalonAvailabilityStatus.AVAILABLE
                status_reason = (
                    f"Requested time {normalized_req_time} is available for '{service.name}' on {requested_date}."
                    if normalized_req_time
                    else f"{len(available_slots)} slot(s) available for '{service.name}' on {requested_date}."
                )
        elif staff_with_valid_schedule == 0 and staff_with_missing_schedule > 0:
            avail_status = SalonAvailabilityStatus.STAFF_SCHEDULE_MISSING
            status_reason = (
                f"Working hours for weekday {svario_weekday} are missing or incomplete for qualified staff "
                f"assigned to '{service.name}'."
            )
        else:
            avail_status = SalonAvailabilityStatus.REQUESTED_TIME_UNAVAILABLE
            status_reason = (
                f"No open slots remain for '{service.name}' on {requested_date} "
                "(existing appointments, breaks, or staff day-off cover available hours)."
            )

        logger.info(
            "salon_availability business_id=%s service_id=%s duration=%s date=%s weekday=%s tz=%s "
            "qualified_staff=%s blocking_appts=%s slots=%s req_time=%s req_avail=%s status=%s",
            business_id, service.id, duration, requested_date, svario_weekday, tz_str,
            len(qualified_staff), len(active_appts), len(available_slots),
            normalized_req_time, req_time_available, avail_status.value,
        )

        return SalonAvailabilityResponse(
            organization_id=organization_id,
            business_id=business_id,
            service_id=service.id,
            service_name=service.name,
            duration_minutes=service.duration_minutes,
            price=service.price,
            currency=service.currency,
            requested_date=requested_date,
            timezone=tz_str,
            is_business_closed=False,
            closure_reason=None,
            availability_status=avail_status,
            status_reason=status_reason,
            requested_time=normalized_req_time,
            requested_time_available=req_time_available,
            available_slots=available_slots,
        )

    # =========================================================================
    # E. APPOINTMENT MANAGEMENT
    # =========================================================================
    async def create_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: SalonAppointmentCreateRequest,
        *,
        business_hours_override: Optional[BusinessHoursResponse] = None,
    ) -> SalonAppointmentResponse:
        """Create a salon appointment with concurrency protection, auto-staff selection, and idempotency."""
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)

        # 1. Idempotency Check
        if payload.idempotency_key:
            existing = await self._salon_repo.get_appointment_by_idempotency_key(
                actor, organization_id, business_id, payload.idempotency_key
            )
            if existing:
                return existing

        # 2. Service Verification
        service = await self._salon_repo.get_service(actor, organization_id, business_id, payload.service_id)
        if not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service '{service.name}' is inactive and cannot be booked.",
            )

        # 3. Staff Selection & Availability Verification
        selected_staff_id = payload.staff_id
        if selected_staff_id is None:
            # Auto-assign: find available staff for this service at the requested start time
            avail = await self.get_salon_availability(
                actor,
                organization_id,
                business_id,
                service.id,
                payload.appointment_date,
                business_hours_override=business_hours_override,
            )
            matching_slot = next(
                (s for s in avail.available_slots if s.start_time == payload.start_time),
                None,
            )
            if not matching_slot:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No qualified stylist is available for '{service.name}' at {payload.start_time} on {payload.appointment_date}.",
                )
            selected_staff_id = matching_slot.staff_id
            staff = await self._salon_repo.get_staff(actor, organization_id, business_id, selected_staff_id)
        else:
            staff = await self._salon_repo.get_staff(actor, organization_id, business_id, selected_staff_id)
            if not staff.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Staff member '{staff.full_name}' is currently inactive.",
                )
            if service.id not in staff.assigned_service_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Staff member '{staff.full_name}' is not assigned to service '{service.name}'.",
                )
            # Verify specific staff availability
            avail = await self.get_salon_availability(
                actor,
                organization_id,
                business_id,
                service.id,
                payload.appointment_date,
                staff_id=staff.id,
                business_hours_override=business_hours_override,
            )
            is_avail = any(s.start_time == payload.start_time for s in avail.available_slots)
            if not is_avail:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{staff.full_name} is not available for '{service.name}' at {payload.start_time} on {payload.appointment_date}.",
                )

        # 4. Calculate Timestamps in Business Timezone
        tz_str = await self._resolve_business_timezone(
            actor,
            organization_id,
            business_id,
            business_hours_override=business_hours_override,
        )
        try:
            tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            tz = timezone.utc

        start_min = parse_hhmm_to_minutes(payload.start_time)
        end_min = start_min + service.duration_minutes
        end_time_str = format_minutes_to_hhmm(end_min)

        start_at = datetime.combine(
            payload.appointment_date,
            time(start_min // 60, start_min % 60),
            tzinfo=tz,
        )
        end_at = datetime.combine(
            payload.appointment_date,
            time(end_min // 60, end_min % 60),
            tzinfo=tz,
        )

        booking_ref = f"SV-SAL-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        appt_record = SalonAppointmentResponse(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            booking_reference=booking_ref,
            idempotency_key=payload.idempotency_key,
            service_id=service.id,
            service_name=service.name,
            service_duration_minutes=service.duration_minutes,
            service_price=service.price,
            service_currency=service.currency,
            staff_id=staff.id,
            staff_name=staff.full_name,
            staff_role=staff.role_designation,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            customer_email=payload.customer_email,
            notes=payload.notes,
            appointment_date=payload.appointment_date,
            start_time=payload.start_time,
            end_time=end_time_str,
            start_at=start_at,
            end_at=end_at,
            timezone=tz_str,
            status=SalonAppointmentStatus.CONFIRMED,
            source=payload.source,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=now,
            updated_at=now,
        )

        created = await self._salon_repo.create_appointment(actor, organization_id, business_id, appt_record)
        return created

    async def get_appointment(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID, appointment_id: UUID
    ) -> SalonAppointmentResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.get_appointment(actor, organization_id, business_id, appointment_id)

    async def list_appointments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_date: Optional[date] = None,
        staff_id: Optional[UUID] = None,
        status: Optional[SalonAppointmentStatus] = None,
    ) -> List[SalonAppointmentResponse]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        return await self._salon_repo.list_appointments(
            actor, organization_id, business_id, appointment_date, staff_id, status
        )

    async def reschedule_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        payload: SalonAppointmentRescheduleRequest,
        *,
        business_hours_override: Optional[BusinessHoursResponse] = None,
    ) -> SalonAppointmentResponse:
        """Reschedule an existing confirmed appointment with concurrency protection."""
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        existing = await self._salon_repo.get_appointment(actor, organization_id, business_id, appointment_id)
        if existing.status not in {SalonAppointmentStatus.CONFIRMED, SalonAppointmentStatus.RESCHEDULED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reschedule an appointment in '{existing.status.value}' status.",
            )

        # Check idempotency if key matches
        if payload.idempotency_key and existing.idempotency_key == payload.idempotency_key:
            return existing

        target_staff_id = payload.staff_id or existing.staff_id
        staff = await self._salon_repo.get_staff(actor, organization_id, business_id, target_staff_id)
        service = await self._salon_repo.get_service(actor, organization_id, business_id, existing.service_id)

        # Verify new slot availability
        avail = await self.get_salon_availability(
            actor,
            organization_id,
            business_id,
            service.id,
            payload.appointment_date,
            staff_id=staff.id,
            business_hours_override=business_hours_override,
        )
        is_avail = any(s.start_time == payload.start_time for s in avail.available_slots)
        if not is_avail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{staff.full_name} is not available at {payload.start_time} on {payload.appointment_date}.",
            )

        tz_str = existing.timezone
        try:
            tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            tz = timezone.utc

        start_min = parse_hhmm_to_minutes(payload.start_time)
        end_min = start_min + existing.service_duration_minutes
        end_time_str = format_minutes_to_hhmm(end_min)

        start_at = datetime.combine(
            payload.appointment_date,
            time(start_min // 60, start_min % 60),
            tzinfo=tz,
        )
        end_at = datetime.combine(
            payload.appointment_date,
            time(end_min // 60, end_min % 60),
            tzinfo=tz,
        )

        now = datetime.now(timezone.utc)
        updated_record = SalonAppointmentResponse(
            id=existing.id,
            organization_id=organization_id,
            business_id=business_id,
            booking_reference=existing.booking_reference,
            idempotency_key=payload.idempotency_key or existing.idempotency_key,
            service_id=existing.service_id,
            service_name=existing.service_name,
            service_duration_minutes=existing.service_duration_minutes,
            service_price=existing.service_price,
            service_currency=existing.service_currency,
            staff_id=staff.id,
            staff_name=staff.full_name,
            staff_role=staff.role_designation,
            customer_name=existing.customer_name,
            customer_phone=existing.customer_phone,
            customer_email=existing.customer_email,
            notes=payload.notes if payload.notes is not None else existing.notes,
            appointment_date=payload.appointment_date,
            start_time=payload.start_time,
            end_time=end_time_str,
            start_at=start_at,
            end_at=end_at,
            timezone=tz_str,
            status=SalonAppointmentStatus.RESCHEDULED,
            source=existing.source,
            cancelled_at=None,
            cancellation_reason=None,
            created_at=existing.created_at,
            updated_at=now,
        )

        return await self._salon_repo.update_appointment(actor, organization_id, business_id, updated_record)

    async def cancel_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        payload: SalonAppointmentCancelRequest,
    ) -> SalonAppointmentResponse:
        """Cancel a salon appointment."""
        await self._verify_org_access(actor, organization_id, business_id, require_admin=False)
        existing = await self._salon_repo.get_appointment(actor, organization_id, business_id, appointment_id)
        if existing.status == SalonAppointmentStatus.CANCELLED:
            return existing

        now = datetime.now(timezone.utc)
        cancelled_record = SalonAppointmentResponse(
            id=existing.id,
            organization_id=organization_id,
            business_id=business_id,
            booking_reference=existing.booking_reference,
            idempotency_key=existing.idempotency_key,
            service_id=existing.service_id,
            service_name=existing.service_name,
            service_duration_minutes=existing.service_duration_minutes,
            service_price=existing.service_price,
            service_currency=existing.service_currency,
            staff_id=existing.staff_id,
            staff_name=existing.staff_name,
            staff_role=existing.staff_role,
            customer_name=existing.customer_name,
            customer_phone=existing.customer_phone,
            customer_email=existing.customer_email,
            notes=existing.notes,
            appointment_date=existing.appointment_date,
            start_time=existing.start_time,
            end_time=existing.end_time,
            start_at=existing.start_at,
            end_at=existing.end_at,
            timezone=existing.timezone,
            status=SalonAppointmentStatus.CANCELLED,
            source=existing.source,
            cancelled_at=now,
            cancellation_reason=payload.cancellation_reason or "Customer requested cancellation.",
            created_at=existing.created_at,
            updated_at=now,
        )

        return await self._salon_repo.update_appointment(actor, organization_id, business_id, cancelled_record)


def get_salon_repository(
    settings: Optional[Settings] = None,
) -> SalonRepositoryProtocol:
    """Resolve the active Salon repository with fail-closed production enforcement.

    - Live Supabase configured -> SupabaseRestSalonRepository (real PostgreSQL persistence)
    - Production without live Supabase -> RuntimeError (fail closed; never fall back to memory)
    - Non-production without live Supabase -> InMemorySalonRepository
    """
    resolved_settings = settings if isinstance(settings, Settings) else get_settings()
    if resolved_settings.is_live_supabase_configured:
        return SupabaseRestSalonRepository(settings=resolved_settings)
    if resolved_settings.svario_env.strip().lower() == "production":
        raise RuntimeError(
            "Production environment requires live Supabase database configuration "
            "(SUPABASE_URL and SUPABASE_ANON_KEY); in-memory salon repository fallback is forbidden."
        )
    return get_in_memory_salon_repository()


_salon_service_cache: Dict[tuple[str, str, int], SalonWorkflowService] = {}


def clear_salon_service_cache() -> None:
    """Clear cached SalonWorkflowService instances (used on config reload or test isolation)."""
    _salon_service_cache.clear()


def _settings_fingerprint(settings: Settings) -> str:
    """Compute a non-reversible SHA-256 fingerprint of Supabase/env settings.

    Prevents stale cached repositories after credential or URL rotation without
    storing or logging raw secrets in cache keys.
    """
    raw = "|".join(
        [
            settings.svario_env.strip().lower(),
            (settings.supabase_url or "").strip(),
            (settings.supabase_anon_key or "").strip(),
            (settings.supabase_service_role_key or "").strip(),
        ]
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_salon_workflow_service(
    *,
    settings: Optional[Settings] = None,
    salon_repo: Optional[SalonRepositoryProtocol] = None,
    onboarding_repo: Optional[OnboardingRepositoryProtocol] = None,
) -> SalonWorkflowService:
    """Pure composition factory for SalonWorkflowService (no FastAPI Depends defaults).

    Safe to call from AgentOrchestrator, background tasks, or FastAPI routes.
    """
    resolved_settings = settings if isinstance(settings, Settings) else get_settings()
    resolved_salon_repo = (
        salon_repo
        if salon_repo is not None and hasattr(salon_repo, "list_services")
        else get_salon_repository(settings=resolved_settings)
    )
    resolved_onboarding_repo = (
        onboarding_repo
        if onboarding_repo is not None and hasattr(onboarding_repo, "get_member_role")
        else get_onboarding_repository(settings=resolved_settings)
    )

    if salon_repo is not None or onboarding_repo is not None:
        return SalonWorkflowService(
            settings=resolved_settings,
            salon_repo=resolved_salon_repo,
            onboarding_repo=resolved_onboarding_repo,
        )

    cache_key = (
        type(resolved_salon_repo).__name__,
        _settings_fingerprint(resolved_settings),
        id(resolved_onboarding_repo) if type(resolved_onboarding_repo).__name__.startswith("InMemory") else 0,
    )
    cached = _salon_service_cache.get(cache_key)
    if cached is None:
        cached = SalonWorkflowService(
            settings=resolved_settings,
            salon_repo=resolved_salon_repo,
            onboarding_repo=resolved_onboarding_repo,
        )
        _salon_service_cache[cache_key] = cached
    return cached


def get_salon_workflow_service(
    settings: Settings = Depends(get_settings),
    onboarding_repo: OnboardingRepositoryProtocol = Depends(get_onboarding_repository),
) -> SalonWorkflowService:
    """FastAPI dependency provider for SalonWorkflowService."""
    resolved_settings = settings if isinstance(settings, Settings) else get_settings()
    resolved_onboarding_repo = (
        onboarding_repo if hasattr(onboarding_repo, "get_member_role") else None
    )
    return build_salon_workflow_service(
        settings=resolved_settings,
        onboarding_repo=resolved_onboarding_repo,
    )
