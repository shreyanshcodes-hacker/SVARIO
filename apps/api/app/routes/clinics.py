"""Stage 6 Clinic Workflow Module — FastAPI Routes.

Mounted at:
`/api/v1/organizations/{organization_id}/clinics/{business_id}/...`
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from app.core.auth import AuthenticatedUser, get_current_user
from app.modules.clinics.schemas import (
    ClinicAppointmentCancelRequest,
    ClinicAppointmentCreateRequest,
    ClinicAppointmentRescheduleRequest,
    ClinicAppointmentResponse,
    ClinicAppointmentStatus,
    ClinicAvailabilityResponse,
    ClinicConsultationTypeCreateRequest,
    ClinicConsultationTypeResponse,
    ClinicConsultationTypeUpdateRequest,
    ClinicDepartmentCreateRequest,
    ClinicDepartmentResponse,
    ClinicDepartmentUpdateRequest,
    ClinicDoctorCreateRequest,
    ClinicDoctorMappingRequest,
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
from app.modules.clinics.service import ClinicWorkflowService, get_clinic_workflow_service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/clinics/{business_id}",
    tags=["Clinics"],
)


# ----------------------------------------------------------------------------
# Departments
# ----------------------------------------------------------------------------


@router.get("/departments", response_model=List[ClinicDepartmentResponse])
async def list_departments(
    organization_id: UUID,
    business_id: UUID,
    active_only: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[ClinicDepartmentResponse]:
    return await service.list_departments(
        current_user, organization_id, business_id, active_only=active_only
    )


@router.post(
    "/departments",
    response_model=ClinicDepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    organization_id: UUID,
    business_id: UUID,
    payload: ClinicDepartmentCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDepartmentResponse:
    return await service.create_department(current_user, organization_id, business_id, payload)


@router.patch("/departments/{department_id}", response_model=ClinicDepartmentResponse)
async def update_department(
    organization_id: UUID,
    business_id: UUID,
    department_id: UUID,
    payload: ClinicDepartmentUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDepartmentResponse:
    return await service.update_department(
        current_user, organization_id, business_id, department_id, payload
    )


# ----------------------------------------------------------------------------
# Specialities
# ----------------------------------------------------------------------------


@router.get("/specialities", response_model=List[ClinicSpecialityResponse])
async def list_specialities(
    organization_id: UUID,
    business_id: UUID,
    active_only: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[ClinicSpecialityResponse]:
    return await service.list_specialities(
        current_user, organization_id, business_id, active_only=active_only
    )


@router.post(
    "/specialities",
    response_model=ClinicSpecialityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_speciality(
    organization_id: UUID,
    business_id: UUID,
    payload: ClinicSpecialityCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicSpecialityResponse:
    return await service.create_speciality(current_user, organization_id, business_id, payload)


@router.patch("/specialities/{speciality_id}", response_model=ClinicSpecialityResponse)
async def update_speciality(
    organization_id: UUID,
    business_id: UUID,
    speciality_id: UUID,
    payload: ClinicSpecialityUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicSpecialityResponse:
    return await service.update_speciality(
        current_user, organization_id, business_id, speciality_id, payload
    )


# ----------------------------------------------------------------------------
# Consultation Types
# ----------------------------------------------------------------------------


@router.get("/consultation-types", response_model=List[ClinicConsultationTypeResponse])
async def list_consultation_types(
    organization_id: UUID,
    business_id: UUID,
    active_only: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[ClinicConsultationTypeResponse]:
    return await service.list_consultation_types(
        current_user, organization_id, business_id, active_only=active_only
    )


@router.post(
    "/consultation-types",
    response_model=ClinicConsultationTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_consultation_type(
    organization_id: UUID,
    business_id: UUID,
    payload: ClinicConsultationTypeCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicConsultationTypeResponse:
    return await service.create_consultation_type(
        current_user, organization_id, business_id, payload
    )


@router.patch(
    "/consultation-types/{consultation_type_id}",
    response_model=ClinicConsultationTypeResponse,
)
async def update_consultation_type(
    organization_id: UUID,
    business_id: UUID,
    consultation_type_id: UUID,
    payload: ClinicConsultationTypeUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicConsultationTypeResponse:
    return await service.update_consultation_type(
        current_user, organization_id, business_id, consultation_type_id, payload
    )


# ----------------------------------------------------------------------------
# Doctors & Mappings
# ----------------------------------------------------------------------------


@router.get("/doctors", response_model=List[ClinicDoctorResponse])
async def list_doctors(
    organization_id: UUID,
    business_id: UUID,
    active_only: bool = Query(default=False),
    department_id: Optional[UUID] = Query(default=None),
    speciality_id: Optional[UUID] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[ClinicDoctorResponse]:
    return await service.list_doctors(
        current_user,
        organization_id,
        business_id,
        active_only=active_only,
        department_id=department_id,
        speciality_id=speciality_id,
    )


@router.get("/doctors/{doctor_id}", response_model=ClinicDoctorResponse)
async def get_doctor(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDoctorResponse:
    return await service.get_doctor(current_user, organization_id, business_id, doctor_id)


@router.post(
    "/doctors",
    response_model=ClinicDoctorResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor(
    organization_id: UUID,
    business_id: UUID,
    payload: ClinicDoctorCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDoctorResponse:
    return await service.create_doctor(current_user, organization_id, business_id, payload)


@router.patch("/doctors/{doctor_id}", response_model=ClinicDoctorResponse)
async def update_doctor(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: ClinicDoctorUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDoctorResponse:
    return await service.update_doctor(
        current_user, organization_id, business_id, doctor_id, payload
    )


@router.put("/doctors/{doctor_id}/departments", response_model=ClinicDoctorResponse)
async def set_doctor_departments(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: ClinicDoctorMappingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDoctorResponse:
    return await service.set_doctor_departments(
        current_user, organization_id, business_id, doctor_id, payload.ids
    )


@router.put("/doctors/{doctor_id}/specialities", response_model=ClinicDoctorResponse)
async def set_doctor_specialities(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: ClinicDoctorMappingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDoctorResponse:
    return await service.set_doctor_specialities(
        current_user, organization_id, business_id, doctor_id, payload.ids
    )


@router.put("/doctors/{doctor_id}/consultation-types", response_model=ClinicDoctorResponse)
async def set_doctor_consultation_types(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: ClinicDoctorMappingRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicDoctorResponse:
    return await service.set_doctor_consultation_types(
        current_user, organization_id, business_id, doctor_id, payload.ids
    )


# ----------------------------------------------------------------------------
# Doctor Schedules, Breaks & Unavailability
# ----------------------------------------------------------------------------


@router.get("/doctors/{doctor_id}/working-hours", response_model=List[DoctorWorkingHoursResponse])
async def get_doctor_working_hours(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[DoctorWorkingHoursResponse]:
    return await service.get_doctor_working_hours(
        current_user, organization_id, business_id, doctor_id
    )


@router.put("/doctors/{doctor_id}/working-hours", response_model=List[DoctorWorkingHoursResponse])
async def upsert_doctor_working_hours(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: DoctorWorkingHoursBulkRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[DoctorWorkingHoursResponse]:
    return await service.upsert_doctor_working_hours(
        current_user, organization_id, business_id, doctor_id, payload
    )


@router.get("/doctors/{doctor_id}/breaks", response_model=List[DoctorBreakResponse])
async def list_doctor_breaks(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[DoctorBreakResponse]:
    return await service.list_doctor_breaks(current_user, organization_id, business_id, doctor_id)


@router.post(
    "/doctors/{doctor_id}/breaks",
    response_model=DoctorBreakResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor_break(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: DoctorBreakCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> DoctorBreakResponse:
    return await service.create_doctor_break(
        current_user, organization_id, business_id, doctor_id, payload
    )


@router.get(
    "/doctors/{doctor_id}/unavailability",
    response_model=List[DoctorUnavailabilityResponse],
)
async def list_doctor_unavailability(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[DoctorUnavailabilityResponse]:
    return await service.list_doctor_unavailability(
        current_user, organization_id, business_id, doctor_id
    )


@router.post(
    "/doctors/{doctor_id}/unavailability",
    response_model=DoctorUnavailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor_unavailability(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: UUID,
    payload: DoctorUnavailabilityCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> DoctorUnavailabilityResponse:
    return await service.create_doctor_unavailability(
        current_user, organization_id, business_id, doctor_id, payload
    )


# ----------------------------------------------------------------------------
# Availability & Appointments
# ----------------------------------------------------------------------------


@router.get("/availability", response_model=ClinicAvailabilityResponse)
async def get_clinic_availability(
    organization_id: UUID,
    business_id: UUID,
    consultation_type_id: UUID = Query(...),
    target_date: date = Query(...),
    doctor_id: Optional[UUID] = Query(default=None),
    department_id: Optional[UUID] = Query(default=None),
    speciality_id: Optional[UUID] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicAvailabilityResponse:
    return await service.get_availability(
        current_user,
        organization_id,
        business_id,
        consultation_type_id=consultation_type_id,
        target_date=target_date,
        doctor_id=doctor_id,
        department_id=department_id,
        speciality_id=speciality_id,
    )


@router.get("/appointments", response_model=List[ClinicAppointmentResponse])
async def list_appointments(
    organization_id: UUID,
    business_id: UUID,
    doctor_id: Optional[UUID] = Query(default=None),
    target_date: Optional[date] = Query(default=None),
    status_filter: Optional[ClinicAppointmentStatus] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> List[ClinicAppointmentResponse]:
    return await service.list_appointments(
        current_user,
        organization_id,
        business_id,
        doctor_id=doctor_id,
        target_date=target_date,
        status_filter=status_filter,
    )


@router.get("/appointments/{appointment_id}", response_model=ClinicAppointmentResponse)
async def get_appointment(
    organization_id: UUID,
    business_id: UUID,
    appointment_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicAppointmentResponse:
    return await service.get_appointment(
        current_user, organization_id, business_id, appointment_id
    )


@router.post(
    "/appointments",
    response_model=ClinicAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    organization_id: UUID,
    business_id: UUID,
    payload: ClinicAppointmentCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicAppointmentResponse:
    return await service.create_appointment(
        current_user, organization_id, business_id, payload
    )


@router.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=ClinicAppointmentResponse,
)
async def reschedule_appointment(
    organization_id: UUID,
    business_id: UUID,
    appointment_id: UUID,
    payload: ClinicAppointmentRescheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicAppointmentResponse:
    return await service.reschedule_appointment(
        current_user, organization_id, business_id, appointment_id, payload
    )


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=ClinicAppointmentResponse,
)
async def cancel_appointment(
    organization_id: UUID,
    business_id: UUID,
    appointment_id: UUID,
    payload: ClinicAppointmentCancelRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ClinicWorkflowService = Depends(get_clinic_workflow_service),
) -> ClinicAppointmentResponse:
    return await service.cancel_appointment(
        current_user, organization_id, business_id, appointment_id, payload
    )
