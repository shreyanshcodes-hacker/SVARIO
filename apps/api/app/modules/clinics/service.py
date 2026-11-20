"""Stage 6 Clinic Workflow Service.

Handles tenant-isolated Clinic CRUD, doctor mappings, schedules, dynamic
availability calculation, and concurrency-safe appointment booking,
rescheduling, and cancellation.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from typing import List, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.modules.clinics.repository import (
    ClinicConflictError,
    ClinicNotFoundError,
    ClinicRepositoryProtocol,
    InMemoryClinicRepository,
)
from app.modules.clinics.supabase_repository import (
    SupabaseRestClinicRepository,
    set_current_clinic_actor,
)
from app.modules.clinics.schemas import (
    ClinicAppointmentCancelRequest,
    ClinicAppointmentCreateRequest,
    ClinicAppointmentRescheduleRequest,
    ClinicAppointmentResponse,
    ClinicAppointmentStatus,
    ClinicAvailabilityResponse,
    ClinicAvailableSlot,
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
    DoctorWorkingHoursBulkRequest,
    DoctorWorkingHoursResponse,
)
from app.modules.onboarding.repository import OnboardingRepositoryProtocol
from app.modules.onboarding.service import get_onboarding_repository
from app.modules.organizations.repository import OrganizationRepositoryProtocol
from app.modules.organizations.schemas import OrganizationIndustry, OrganizationRole
from app.modules.organizations.service import get_organization_repository

INTERNAL_VOICE_ISSUER = "https://svario.internal/auth/v1"


class ClinicWorkflowService:
    """Business logic and tenant-isolation layer for Svario Clinic workflows."""

    def __init__(
        self,
        *,
        clinic_repo: Optional[ClinicRepositoryProtocol] = None,
        org_repo: Optional[OrganizationRepositoryProtocol] = None,
        onboarding_repo: Optional[OnboardingRepositoryProtocol] = None,
        min_lead_time_minutes: int = 0,
    ) -> None:
        self._clinic_repo: ClinicRepositoryProtocol = clinic_repo or get_clinic_repository(
            settings=get_settings()
        )
        settings = get_settings()
        self._org_repo: OrganizationRepositoryProtocol = (
            org_repo or get_organization_repository(settings=settings)
        )
        self._onboarding_repo: OnboardingRepositoryProtocol = (
            onboarding_repo or get_onboarding_repository(settings=settings)
        )
        self._min_lead_time_minutes = min_lead_time_minutes

    async def _verify_org_access(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        require_admin: bool = False,
    ) -> None:
        """Verify tenant membership, clinic industry, business ownership, and role."""
        set_current_clinic_actor(actor)
        is_internal_voice = actor.issuer == INTERNAL_VOICE_ISSUER
        if is_internal_voice:
            if require_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Voice agent sessions cannot modify clinic administrative configuration.",
                )
            return

        role = await self._onboarding_repo.get_member_role(actor, organization_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or access denied.",
            )

        org = await self._org_repo.get_organization_for_member(actor, organization_id)
        if org is not None and org.industry != OrganizationIndustry.CLINIC:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinic workflow endpoints are only valid for clinic organizations.",
            )

        if require_admin and role not in {OrganizationRole.OWNER, OrganizationRole.ADMIN}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only clinic owners or admins can modify clinic configuration.",
            )

        # Verify business belongs to organization
        try:
            profile = await self._onboarding_repo.get_business_profile(
                actor, organization_id, business_id
            )
            if profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Clinic business not found in this organization.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic business not found in this organization.",
            ) from exc

    @staticmethod
    def _get_zoneinfo(tz_name: str):
        """Resolve DST-aware IANA timezone via ZoneInfo (backed by tzdata)."""
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return timezone.utc

    async def _resolve_timezone(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> str:
        try:
            hours = await self._onboarding_repo.get_business_hours(
                actor, organization_id, business_id
            )
            if hours and hours.timezone:
                return hours.timezone
        except Exception:
            pass
        try:
            profile = await self._onboarding_repo.get_business_profile(
                actor, organization_id, business_id
            )
            if profile and profile.timezone:
                return profile.timezone
        except Exception:
            pass
        return "UTC"

    # ------------------------------------------------------------------------
    # Departments
    # ------------------------------------------------------------------------

    async def list_departments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        active_only: bool = False,
    ) -> List[ClinicDepartmentResponse]:
        await self._verify_org_access(actor, organization_id, business_id)
        return await self._clinic_repo.list_departments(
            organization_id, business_id, active_only=active_only
        )

    async def create_department(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicDepartmentCreateRequest,
    ) -> ClinicDepartmentResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        try:
            return await self._clinic_repo.create_department(organization_id, business_id, payload)
        except ClinicConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    async def update_department(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        department_id: UUID,
        payload: ClinicDepartmentUpdateRequest,
    ) -> ClinicDepartmentResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        updated = await self._clinic_repo.update_department(
            organization_id, business_id, department_id, payload
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")
        return updated

    # ------------------------------------------------------------------------
    # Specialities
    # ------------------------------------------------------------------------

    async def list_specialities(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        active_only: bool = False,
    ) -> List[ClinicSpecialityResponse]:
        await self._verify_org_access(actor, organization_id, business_id)
        return await self._clinic_repo.list_specialities(
            organization_id, business_id, active_only=active_only
        )

    async def create_speciality(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicSpecialityCreateRequest,
    ) -> ClinicSpecialityResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        try:
            return await self._clinic_repo.create_speciality(organization_id, business_id, payload)
        except ClinicConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    async def update_speciality(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        speciality_id: UUID,
        payload: ClinicSpecialityUpdateRequest,
    ) -> ClinicSpecialityResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        updated = await self._clinic_repo.update_speciality(
            organization_id, business_id, speciality_id, payload
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Speciality not found.")
        return updated

    # ------------------------------------------------------------------------
    # Consultation Types
    # ------------------------------------------------------------------------

    async def list_consultation_types(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        active_only: bool = False,
    ) -> List[ClinicConsultationTypeResponse]:
        await self._verify_org_access(actor, organization_id, business_id)
        return await self._clinic_repo.list_consultation_types(
            organization_id, business_id, active_only=active_only
        )

    async def create_consultation_type(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicConsultationTypeCreateRequest,
    ) -> ClinicConsultationTypeResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        return await self._clinic_repo.create_consultation_type(
            organization_id, business_id, payload
        )

    async def update_consultation_type(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        consultation_type_id: UUID,
        payload: ClinicConsultationTypeUpdateRequest,
    ) -> ClinicConsultationTypeResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        updated = await self._clinic_repo.update_consultation_type(
            organization_id, business_id, consultation_type_id, payload
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Consultation type not found."
            )
        return updated

    # ------------------------------------------------------------------------
    # Doctors & Mappings
    # ------------------------------------------------------------------------

    async def list_doctors(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        active_only: bool = False,
        department_id: Optional[UUID] = None,
        speciality_id: Optional[UUID] = None,
    ) -> List[ClinicDoctorResponse]:
        await self._verify_org_access(actor, organization_id, business_id)
        doctors = await self._clinic_repo.list_doctors(
            organization_id, business_id, active_only=active_only
        )
        if department_id is not None:
            doctors = [d for d in doctors if department_id in d.department_ids]
        if speciality_id is not None:
            doctors = [d for d in doctors if speciality_id in d.speciality_ids]
        return doctors

    async def get_doctor(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
    ) -> ClinicDoctorResponse:
        await self._verify_org_access(actor, organization_id, business_id)
        doc = await self._clinic_repo.get_doctor(organization_id, business_id, doctor_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return doc

    async def _validate_doctor_mappings(
        self,
        organization_id: UUID,
        business_id: UUID,
        *,
        department_ids: Optional[List[UUID]] = None,
        speciality_ids: Optional[List[UUID]] = None,
        consultation_type_ids: Optional[List[UUID]] = None,
    ) -> None:
        for dept_id in department_ids or []:
            if not await self._clinic_repo.get_department(organization_id, business_id, dept_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid department_id '{dept_id}' for this clinic.",
                )
        for spec_id in speciality_ids or []:
            if not await self._clinic_repo.get_speciality(organization_id, business_id, spec_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid speciality_id '{spec_id}' for this clinic.",
                )
        for ct_id in consultation_type_ids or []:
            if not await self._clinic_repo.get_consultation_type(
                organization_id, business_id, ct_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid consultation_type_id '{ct_id}' for this clinic.",
                )

    async def create_doctor(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicDoctorCreateRequest,
    ) -> ClinicDoctorResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._validate_doctor_mappings(
            organization_id,
            business_id,
            department_ids=payload.department_ids,
            speciality_ids=payload.speciality_ids,
            consultation_type_ids=payload.consultation_type_ids,
        )
        return await self._clinic_repo.create_doctor(organization_id, business_id, payload)

    async def update_doctor(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: ClinicDoctorUpdateRequest,
    ) -> ClinicDoctorResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        updated = await self._clinic_repo.update_doctor(
            organization_id, business_id, doctor_id, payload
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return updated

    async def set_doctor_departments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        department_ids: List[UUID],
    ) -> ClinicDoctorResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._validate_doctor_mappings(
            organization_id, business_id, department_ids=department_ids
        )
        updated = await self._clinic_repo.set_doctor_departments(
            organization_id, business_id, doctor_id, department_ids
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return updated

    async def set_doctor_specialities(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        speciality_ids: List[UUID],
    ) -> ClinicDoctorResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._validate_doctor_mappings(
            organization_id, business_id, speciality_ids=speciality_ids
        )
        updated = await self._clinic_repo.set_doctor_specialities(
            organization_id, business_id, doctor_id, speciality_ids
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return updated

    async def set_doctor_consultation_types(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        consultation_type_ids: List[UUID],
    ) -> ClinicDoctorResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        await self._validate_doctor_mappings(
            organization_id, business_id, consultation_type_ids=consultation_type_ids
        )
        updated = await self._clinic_repo.set_doctor_consultation_types(
            organization_id, business_id, doctor_id, consultation_type_ids
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return updated

    # ------------------------------------------------------------------------
    # Schedules: Working Hours, Breaks, Unavailability
    # ------------------------------------------------------------------------

    async def get_doctor_working_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
    ) -> List[DoctorWorkingHoursResponse]:
        await self.get_doctor(actor, organization_id, business_id, doctor_id)
        return await self._clinic_repo.get_doctor_working_hours(
            organization_id, business_id, doctor_id
        )

    async def upsert_doctor_working_hours(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorWorkingHoursBulkRequest,
    ) -> List[DoctorWorkingHoursResponse]:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        doc = await self._clinic_repo.get_doctor(organization_id, business_id, doctor_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return await self._clinic_repo.upsert_doctor_working_hours(
            organization_id, business_id, doctor_id, payload.items
        )

    async def list_doctor_breaks(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
    ) -> List[DoctorBreakResponse]:
        await self.get_doctor(actor, organization_id, business_id, doctor_id)
        return await self._clinic_repo.list_doctor_breaks(
            organization_id, business_id, doctor_id
        )

    async def create_doctor_break(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorBreakCreateRequest,
    ) -> DoctorBreakResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        doc = await self._clinic_repo.get_doctor(organization_id, business_id, doctor_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return await self._clinic_repo.create_doctor_break(
            organization_id, business_id, doctor_id, payload
        )

    async def list_doctor_unavailability(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
    ) -> List[DoctorUnavailabilityResponse]:
        await self.get_doctor(actor, organization_id, business_id, doctor_id)
        return await self._clinic_repo.list_doctor_unavailability(
            organization_id, business_id, doctor_id
        )

    async def create_doctor_unavailability(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        doctor_id: UUID,
        payload: DoctorUnavailabilityCreateRequest,
    ) -> DoctorUnavailabilityResponse:
        await self._verify_org_access(actor, organization_id, business_id, require_admin=True)
        doc = await self._clinic_repo.get_doctor(organization_id, business_id, doctor_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        return await self._clinic_repo.create_doctor_unavailability(
            organization_id, business_id, doctor_id, payload
        )

    # ------------------------------------------------------------------------
    # Dynamic Availability Calculation
    # ------------------------------------------------------------------------

    @staticmethod
    def _parse_hhmm(hhmm: str) -> time:
        parts = hhmm.strip().split(":")
        return time(hour=int(parts[0]), minute=int(parts[1]))

    @staticmethod
    def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
        return a_start < b_end and b_start < a_end

    async def _get_clinic_hours_window(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        svario_weekday: int,
    ) -> Optional[Tuple[time, time]]:
        """Return clinic-level (opens_at, closes_at) if configured, or None if closed."""
        try:
            hours_bundle = await self._onboarding_repo.get_business_hours(
                actor, organization_id, business_id
            )
        except Exception:
            return (time(0, 0), time(23, 59))
        if not hours_bundle or not hours_bundle.schedule:
            return (time(0, 0), time(23, 59))
        day_item = next(
            (h for h in hours_bundle.schedule if h.weekday == svario_weekday), None
        )
        if day_item is None:
            return (time(0, 0), time(23, 59))
        if day_item.is_closed or not day_item.opens_at or not day_item.closes_at:
            return None
        return (self._parse_hhmm(day_item.opens_at), self._parse_hhmm(day_item.closes_at))

    async def get_availability(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        consultation_type_id: UUID,
        target_date: date,
        doctor_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        speciality_id: Optional[UUID] = None,
    ) -> ClinicAvailabilityResponse:
        """Compute valid conflict-free appointment slots for a clinic consultation."""
        await self._verify_org_access(actor, organization_id, business_id)

        consultation = await self._clinic_repo.get_consultation_type(
            organization_id, business_id, consultation_type_id
        )
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Consultation type not found."
            )
        if not consultation.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Consultation type '{consultation.name}' is currently inactive.",
            )

        if department_id is not None:
            dept = await self._clinic_repo.get_department(
                organization_id, business_id, department_id
            )
            if not dept or not dept.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Requested department is invalid or inactive.",
                )

        tz_name = await self._resolve_timezone(actor, organization_id, business_id)
        tz = self._get_zoneinfo(tz_name)

        svario_weekday = (target_date.weekday() + 1) % 7
        clinic_window = await self._get_clinic_hours_window(
            actor, organization_id, business_id, svario_weekday
        )
        if clinic_window is None:
            return ClinicAvailabilityResponse(
                organization_id=organization_id,
                business_id=business_id,
                target_date=target_date,
                timezone=tz_name,
                consultation_type_id=consultation_type_id,
                duration_minutes=consultation.duration_minutes,
                slots=[],
            )

        # Resolve candidate doctors
        if doctor_id is not None:
            doc = await self._clinic_repo.get_doctor(organization_id, business_id, doctor_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found."
                )
            if not doc.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Doctor '{doc.display_name}' is currently inactive.",
                )
            candidates = [doc]
        else:
            candidates = await self._clinic_repo.list_doctors(
                organization_id, business_id, active_only=True
            )

        eligible_doctors: List[ClinicDoctorResponse] = []
        for doc in candidates:
            if consultation_type_id not in doc.consultation_type_ids:
                continue
            if department_id is not None and department_id not in doc.department_ids:
                continue
            if speciality_id is not None and speciality_id not in doc.speciality_ids:
                continue
            eligible_doctors.append(doc)

        now_utc = datetime.now(timezone.utc)
        min_start_utc = now_utc + timedelta(minutes=self._min_lead_time_minutes)
        duration = timedelta(minutes=consultation.duration_minutes)

        slots: List[ClinicAvailableSlot] = []
        for doc in eligible_doctors:
            wh_list = await self._clinic_repo.get_doctor_working_hours(
                organization_id, business_id, doc.id
            )
            day_wh = next((w for w in wh_list if w.day_of_week == svario_weekday), None)
            if not day_wh or not day_wh.is_active or not day_wh.start_time or not day_wh.end_time:
                continue

            # Intersect doctor working hours with clinic hours
            eff_start = max(day_wh.start_time, clinic_window[0])
            eff_end = min(day_wh.end_time, clinic_window[1])
            if eff_start >= eff_end:
                continue

            window_start_dt = datetime.combine(target_date, eff_start, tzinfo=tz)
            window_end_dt = datetime.combine(target_date, eff_end, tzinfo=tz)

            # Collect breaks on this date
            breaks = await self._clinic_repo.list_doctor_breaks(
                organization_id, business_id, doc.id
            )
            break_windows: List[Tuple[datetime, datetime]] = []
            for br in breaks:
                if br.specific_date == target_date or (
                    br.specific_date is None and br.day_of_week == svario_weekday
                ):
                    break_windows.append(
                        (
                            datetime.combine(target_date, br.break_start, tzinfo=tz),
                            datetime.combine(target_date, br.break_end, tzinfo=tz),
                        )
                    )

            unavailabilities = await self._clinic_repo.list_doctor_unavailability(
                organization_id, business_id, doc.id
            )
            existing_appts = await self._clinic_repo.list_appointments(
                organization_id, business_id, doctor_id=doc.id
            )
            active_appts = [
                a
                for a in existing_appts
                if a.status
                in {ClinicAppointmentStatus.CONFIRMED, ClinicAppointmentStatus.RESCHEDULED}
            ]

            cursor = window_start_dt
            while cursor + duration <= window_end_dt:
                slot_start = cursor
                slot_end = cursor + duration
                cursor = cursor + duration

                if self._min_lead_time_minutes > 0 and slot_start.astimezone(timezone.utc) < min_start_utc:
                    continue

                if any(self._overlaps(slot_start, slot_end, b_s, b_e) for b_s, b_e in break_windows):
                    continue

                if any(
                    self._overlaps(slot_start, slot_end, u.starts_at, u.ends_at)
                    for u in unavailabilities
                ):
                    continue

                if any(
                    self._overlaps(slot_start, slot_end, a.starts_at, a.ends_at)
                    for a in active_appts
                ):
                    continue

                slots.append(
                    ClinicAvailableSlot(
                        doctor_id=doc.id,
                        doctor_name=doc.display_name,
                        consultation_type_id=consultation.id,
                        starts_at=slot_start,
                        ends_at=slot_end,
                        timezone=tz_name,
                    )
                )

        slots.sort(key=lambda s: (s.starts_at, s.doctor_name.lower()))
        return ClinicAvailabilityResponse(
            organization_id=organization_id,
            business_id=business_id,
            target_date=target_date,
            timezone=tz_name,
            consultation_type_id=consultation_type_id,
            duration_minutes=consultation.duration_minutes,
            slots=slots,
        )

    # ------------------------------------------------------------------------
    # Appointments (Booking, Rescheduling, Cancellation)
    # ------------------------------------------------------------------------

    async def _assert_slot_valid_for_doctor(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        doctor: ClinicDoctorResponse,
        consultation: ClinicConsultationTypeResponse,
        starts_at: datetime,
        ends_at: datetime,
    ) -> str:
        tz_name = await self._resolve_timezone(actor, organization_id, business_id)
        tz = self._get_zoneinfo(tz_name)

        local_start = starts_at.astimezone(tz)
        local_end = ends_at.astimezone(tz)
        if local_start.date() != local_end.date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment cannot span across midnight.",
            )

        target_date = local_start.date()
        svario_weekday = (target_date.weekday() + 1) % 7

        clinic_window = await self._get_clinic_hours_window(
            actor, organization_id, business_id, svario_weekday
        )
        if clinic_window is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinic is closed on the requested date.",
            )

        wh_list = await self._clinic_repo.get_doctor_working_hours(
            organization_id, business_id, doctor.id
        )
        day_wh = next((w for w in wh_list if w.day_of_week == svario_weekday), None)
        if not day_wh or not day_wh.is_active or not day_wh.start_time or not day_wh.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor '{doctor.display_name}' is not scheduled to work on that day.",
            )

        eff_start = max(day_wh.start_time, clinic_window[0])
        eff_end = min(day_wh.end_time, clinic_window[1])
        window_start_dt = datetime.combine(target_date, eff_start, tzinfo=tz)
        window_end_dt = datetime.combine(target_date, eff_end, tzinfo=tz)
        if local_start < window_start_dt or local_end > window_end_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested time is outside the doctor's working hours.",
            )

        breaks = await self._clinic_repo.list_doctor_breaks(
            organization_id, business_id, doctor.id
        )
        for br in breaks:
            if br.specific_date == target_date or (
                br.specific_date is None and br.day_of_week == svario_weekday
            ):
                b_start = datetime.combine(target_date, br.break_start, tzinfo=tz)
                b_end = datetime.combine(target_date, br.break_end, tzinfo=tz)
                if self._overlaps(local_start, local_end, b_start, b_end):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Requested slot overlaps with the doctor's scheduled break.",
                    )

        unavailabilities = await self._clinic_repo.list_doctor_unavailability(
            organization_id, business_id, doctor.id
        )
        if any(self._overlaps(local_start, local_end, u.starts_at, u.ends_at) for u in unavailabilities):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor is unavailable during the requested time window.",
            )

        return tz_name

    async def list_appointments(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        *,
        doctor_id: Optional[UUID] = None,
        target_date: Optional[date] = None,
        status_filter: Optional[ClinicAppointmentStatus] = None,
    ) -> List[ClinicAppointmentResponse]:
        await self._verify_org_access(actor, organization_id, business_id)
        return await self._clinic_repo.list_appointments(
            organization_id,
            business_id,
            doctor_id=doctor_id,
            target_date=target_date,
            status_filter=status_filter,
        )

    async def get_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
    ) -> ClinicAppointmentResponse:
        await self._verify_org_access(actor, organization_id, business_id)
        appt = await self._clinic_repo.get_appointment(
            organization_id, business_id, appointment_id
        )
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found."
            )
        return appt

    async def get_appointment_by_reference(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        booking_reference: str,
    ) -> Optional[ClinicAppointmentResponse]:
        await self._verify_org_access(actor, organization_id, business_id)
        return await self._clinic_repo.get_appointment_by_reference(
            organization_id, business_id, booking_reference
        )

    async def create_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        payload: ClinicAppointmentCreateRequest,
    ) -> ClinicAppointmentResponse:
        await self._verify_org_access(actor, organization_id, business_id)

        doctor = await self._clinic_repo.get_doctor(
            organization_id, business_id, payload.doctor_id
        )
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found.")
        if not doctor.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor '{doctor.display_name}' is currently inactive.",
            )

        consultation = await self._clinic_repo.get_consultation_type(
            organization_id, business_id, payload.consultation_type_id
        )
        if not consultation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Consultation type not found."
            )
        if not consultation.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Consultation type '{consultation.name}' is currently inactive.",
            )

        if consultation.id not in doctor.consultation_type_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor '{doctor.display_name}' does not offer consultation type '{consultation.name}'.",
            )

        if payload.department_id is not None:
            dept = await self._clinic_repo.get_department(
                organization_id, business_id, payload.department_id
            )
            if not dept or not dept.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or inactive department.",
                )
            if payload.department_id not in doctor.department_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected doctor is not assigned to the specified department.",
                )

        starts_at = (
            payload.starts_at
            if payload.starts_at.tzinfo is not None
            else payload.starts_at.replace(tzinfo=timezone.utc)
        )
        ends_at = starts_at + timedelta(minutes=consultation.duration_minutes)

        tz_name = await self._assert_slot_valid_for_doctor(
            actor,
            organization_id,
            business_id,
            doctor=doctor,
            consultation=consultation,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        normalized_payload = payload.model_copy(update={"starts_at": starts_at})
        try:
            return await self._clinic_repo.create_appointment_atomic(
                organization_id=organization_id,
                business_id=business_id,
                payload=normalized_payload,
                ends_at=ends_at,
                tz_name=tz_name,
                doctor_name=doctor.display_name,
                consultation_type_name=consultation.name,
            )
        except ClinicConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    @staticmethod
    def _verify_patient_contact(stored_contact: str, provided_verification: Optional[str]) -> bool:
        if not provided_verification:
            return False
        s_clean = "".join(ch for ch in stored_contact.lower() if ch.isalnum())
        p_clean = "".join(ch for ch in provided_verification.lower() if ch.isalnum())
        if len(p_clean) < 4:
            return False
        return s_clean == p_clean or s_clean.endswith(p_clean)

    async def reschedule_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        payload: ClinicAppointmentRescheduleRequest,
        *,
        require_patient_verification: bool = False,
    ) -> ClinicAppointmentResponse:
        await self._verify_org_access(actor, organization_id, business_id)
        existing = await self._clinic_repo.get_appointment(
            organization_id, business_id, appointment_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found or verification failed."
            )

        if require_patient_verification and not self._verify_patient_contact(
            existing.patient_contact, payload.patient_contact_verification
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found or verification failed.",
            )

        target_doctor_id = payload.new_doctor_id or existing.doctor_id
        doctor = await self._clinic_repo.get_doctor(
            organization_id, business_id, target_doctor_id
        )
        if not doctor or not doctor.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target doctor is invalid or inactive.",
            )

        consultation = await self._clinic_repo.get_consultation_type(
            organization_id, business_id, existing.consultation_type_id
        )
        if not consultation or not consultation.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consultation type is no longer active.",
            )
        if consultation.id not in doctor.consultation_type_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target doctor does not offer this consultation type.",
            )

        new_starts_at = (
            payload.new_starts_at
            if payload.new_starts_at.tzinfo is not None
            else payload.new_starts_at.replace(tzinfo=timezone.utc)
        )
        new_ends_at = new_starts_at + timedelta(minutes=consultation.duration_minutes)

        await self._assert_slot_valid_for_doctor(
            actor,
            organization_id,
            business_id,
            doctor=doctor,
            consultation=consultation,
            starts_at=new_starts_at,
            ends_at=new_ends_at,
        )

        try:
            return await self._clinic_repo.reschedule_appointment_atomic(
                organization_id=organization_id,
                business_id=business_id,
                appointment_id=appointment_id,
                new_doctor_id=doctor.id,
                new_doctor_name=doctor.display_name,
                new_starts_at=new_starts_at,
                new_ends_at=new_ends_at,
            )
        except ClinicNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ClinicConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    async def cancel_appointment(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        appointment_id: UUID,
        payload: ClinicAppointmentCancelRequest,
        *,
        require_patient_verification: bool = False,
    ) -> ClinicAppointmentResponse:
        await self._verify_org_access(actor, organization_id, business_id)
        existing = await self._clinic_repo.get_appointment(
            organization_id, business_id, appointment_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found or verification failed."
            )

        if require_patient_verification and not self._verify_patient_contact(
            existing.patient_contact, payload.patient_contact_verification
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found or verification failed.",
            )

        try:
            return await self._clinic_repo.cancel_appointment_atomic(
                organization_id=organization_id,
                business_id=business_id,
                appointment_id=appointment_id,
                reason=payload.reason,
            )
        except ClinicNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


_in_memory_clinic_repo = InMemoryClinicRepository()


def get_in_memory_clinic_repository() -> InMemoryClinicRepository:
    """Return the shared in-memory clinic repository (explicitly for local dev/tests only)."""
    return _in_memory_clinic_repo


def get_clinic_repository(
    settings: Settings = Depends(get_settings),
) -> ClinicRepositoryProtocol:
    """Resolve the active Clinic repository with fail-closed production enforcement.

    - Live Supabase configured -> SupabaseRestClinicRepository (real PostgreSQL persistence)
    - Production without live Supabase -> RuntimeError (fail closed; never fall back to memory)
    - Non-production without live Supabase -> InMemoryClinicRepository
    """
    resolved_settings = settings if isinstance(settings, Settings) else get_settings()
    if resolved_settings.is_live_supabase_configured:
        return SupabaseRestClinicRepository(settings=resolved_settings)
    if resolved_settings.svario_env.strip().lower() == "production":
        raise RuntimeError(
            "Production environment requires live Supabase database configuration "
            "(SUPABASE_URL and SUPABASE_ANON_KEY); in-memory clinic repository fallback is forbidden."
        )
    return _in_memory_clinic_repo


def get_clinic_workflow_service(
    settings: Settings = Depends(get_settings),
    org_repo: OrganizationRepositoryProtocol = Depends(get_organization_repository),
    onboarding_repo: OnboardingRepositoryProtocol = Depends(get_onboarding_repository),
) -> ClinicWorkflowService:
    """Resolve ClinicWorkflowService backed by the environment-appropriate repository."""
    resolved_settings = settings if isinstance(settings, Settings) else get_settings()
    clinic_repo = get_clinic_repository(settings=resolved_settings)
    resolved_org_repo = (
        get_organization_repository(settings=resolved_settings)
        if not hasattr(org_repo, "get_organization_for_member")
        else org_repo
    )
    resolved_onboarding_repo = (
        get_onboarding_repository(settings=resolved_settings)
        if not hasattr(onboarding_repo, "get_member_role")
        else onboarding_repo
    )
    return ClinicWorkflowService(
        clinic_repo=clinic_repo,
        org_repo=resolved_org_repo,
        onboarding_repo=resolved_onboarding_repo,
    )
