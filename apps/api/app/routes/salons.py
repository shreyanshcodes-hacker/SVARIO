"""API route handlers for Stage 5 Salon Workflow Module."""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response, status
from app.core.auth import AuthenticatedUser, get_current_user
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentResponse,
    SalonAppointmentStatus,
    SalonAvailabilityResponse,
    SalonHolidayCreateRequest,
    SalonHolidayResponse,
    SalonServiceCreateRequest,
    SalonServiceResponse,
    SalonServiceUpdateRequest,
    SalonStaffBreakCreateRequest,
    SalonStaffBreakResponse,
    SalonStaffCreateRequest,
    SalonStaffResponse,
    SalonStaffServiceAssignmentRequest,
    SalonStaffUpdateRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
)
from app.modules.salons.service import SalonWorkflowService, get_salon_workflow_service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/salons/{business_id}",
    tags=["Salon Workflow (Stage 5)"],
)


# =============================================================================
# A. Salon Services CRUD
# =============================================================================
@router.post(
    "/services",
    response_model=SalonServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new salon service (Owner/Admin only)",
)
async def create_service(
    organization_id: UUID,
    business_id: UUID,
    payload: SalonServiceCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonServiceResponse:
    return await service.create_service(current_user, organization_id, business_id, payload)


@router.get(
    "/services",
    response_model=List[SalonServiceResponse],
    summary="List salon services with optional category and active filtering",
)
async def list_services(
    organization_id: UUID,
    business_id: UUID,
    category: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonServiceResponse]:
    return await service.list_services(current_user, organization_id, business_id, category, is_active)


@router.get(
    "/services/{service_id}",
    response_model=SalonServiceResponse,
    summary="Get single salon service details",
)
async def get_service(
    organization_id: UUID,
    business_id: UUID,
    service_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonServiceResponse:
    return await service.get_service(current_user, organization_id, business_id, service_id)


@router.patch(
    "/services/{service_id}",
    response_model=SalonServiceResponse,
    summary="Update an existing salon service (Owner/Admin only)",
)
async def update_service(
    organization_id: UUID,
    business_id: UUID,
    service_id: UUID,
    payload: SalonServiceUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonServiceResponse:
    return await service.update_service(current_user, organization_id, business_id, service_id, payload)


@router.delete(
    "/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a salon service (Owner/Admin only)",
)
async def delete_service(
    organization_id: UUID,
    business_id: UUID,
    service_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> Response:
    await service.delete_service(current_user, organization_id, business_id, service_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# B. Staff Management & Service Assignments
# =============================================================================
@router.post(
    "/staff",
    response_model=SalonStaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new salon staff member profile (Owner/Admin only)",
)
async def create_staff(
    organization_id: UUID,
    business_id: UUID,
    payload: SalonStaffCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonStaffResponse:
    return await service.create_staff(current_user, organization_id, business_id, payload)


@router.get(
    "/staff",
    response_model=List[SalonStaffResponse],
    summary="List salon staff profiles with optional service and active filtering",
)
async def list_staff(
    organization_id: UUID,
    business_id: UUID,
    service_id: Optional[UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonStaffResponse]:
    return await service.list_staff(current_user, organization_id, business_id, service_id, is_active)


@router.get(
    "/staff/{staff_id}",
    response_model=SalonStaffResponse,
    summary="Get single staff member profile details",
)
async def get_staff(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonStaffResponse:
    return await service.get_staff(current_user, organization_id, business_id, staff_id)


@router.patch(
    "/staff/{staff_id}",
    response_model=SalonStaffResponse,
    summary="Update a salon staff member profile (Owner/Admin only)",
)
async def update_staff(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    payload: SalonStaffUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonStaffResponse:
    return await service.update_staff(current_user, organization_id, business_id, staff_id, payload)


@router.delete(
    "/staff/{staff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a salon staff member (Owner/Admin only)",
)
async def delete_staff(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> Response:
    await service.delete_staff(current_user, organization_id, business_id, staff_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/staff/{staff_id}/services",
    response_model=SalonStaffResponse,
    summary="Replace services assigned to a staff member (Owner/Admin only)",
)
async def assign_staff_services(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    payload: SalonStaffServiceAssignmentRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonStaffResponse:
    return await service.assign_staff_services(
        current_user, organization_id, business_id, staff_id, payload.service_ids
    )


# =============================================================================
# C. Schedules, Breaks & Holidays
# =============================================================================
@router.put(
    "/staff/{staff_id}/working-hours",
    response_model=List[SalonStaffWorkingHoursItem],
    summary="Update weekly working schedule for a staff member (Owner/Admin only)",
)
async def update_staff_working_hours(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    payload: SalonStaffWorkingHoursUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonStaffWorkingHoursItem]:
    return await service.update_staff_working_hours(
        current_user, organization_id, business_id, staff_id, payload
    )


@router.get(
    "/staff/{staff_id}/working-hours",
    response_model=List[SalonStaffWorkingHoursItem],
    summary="Get weekly working schedule for a staff member",
)
async def get_staff_working_hours(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonStaffWorkingHoursItem]:
    return await service.get_staff_working_hours(current_user, organization_id, business_id, staff_id)


@router.post(
    "/staff/{staff_id}/breaks",
    response_model=SalonStaffBreakResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a staff break window (Owner/Admin only)",
)
async def add_staff_break(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    payload: SalonStaffBreakCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonStaffBreakResponse:
    return await service.add_staff_break(current_user, organization_id, business_id, staff_id, payload)


@router.get(
    "/staff/{staff_id}/breaks",
    response_model=List[SalonStaffBreakResponse],
    summary="List breaks for a staff member",
)
async def list_staff_breaks(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonStaffBreakResponse]:
    return await service.list_staff_breaks(current_user, organization_id, business_id, staff_id)


@router.delete(
    "/staff/{staff_id}/breaks/{break_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a staff break (Owner/Admin only)",
)
async def delete_staff_break(
    organization_id: UUID,
    business_id: UUID,
    staff_id: UUID,
    break_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> Response:
    await service.delete_staff_break(current_user, organization_id, business_id, staff_id, break_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/holidays",
    response_model=SalonHolidayResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a whole-salon holiday/closure or staff leave (Owner/Admin only)",
)
async def create_holiday(
    organization_id: UUID,
    business_id: UUID,
    payload: SalonHolidayCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonHolidayResponse:
    return await service.create_holiday(current_user, organization_id, business_id, payload)


@router.get(
    "/holidays",
    response_model=List[SalonHolidayResponse],
    summary="List salon holidays and staff leaves",
)
async def list_holidays(
    organization_id: UUID,
    business_id: UUID,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonHolidayResponse]:
    return await service.list_holidays(current_user, organization_id, business_id, start_date, end_date)


@router.delete(
    "/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a salon holiday/closure (Owner/Admin only)",
)
async def delete_holiday(
    organization_id: UUID,
    business_id: UUID,
    holiday_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> Response:
    await service.delete_holiday(current_user, organization_id, business_id, holiday_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# D. Appointment Availability
# =============================================================================
@router.get(
    "/availability",
    response_model=SalonAvailabilityResponse,
    summary="Compute dynamic non-conflicting bookable salon appointment slots",
)
async def get_salon_availability(
    organization_id: UUID,
    business_id: UUID,
    service_id: UUID = Query(...),
    requested_date: date = Query(...),
    staff_id: Optional[UUID] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonAvailabilityResponse:
    return await service.get_salon_availability(
        current_user, organization_id, business_id, service_id, requested_date, staff_id
    )


# =============================================================================
# E. Appointment Management
# =============================================================================
@router.post(
    "/appointments",
    response_model=SalonAppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new salon appointment with concurrency protection and idempotency",
)
async def create_appointment(
    organization_id: UUID,
    business_id: UUID,
    payload: SalonAppointmentCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonAppointmentResponse:
    return await service.create_appointment(current_user, organization_id, business_id, payload)


@router.get(
    "/appointments",
    response_model=List[SalonAppointmentResponse],
    summary="List salon appointments with date, staff, and status filters",
)
async def list_appointments(
    organization_id: UUID,
    business_id: UUID,
    appointment_date: Optional[date] = Query(default=None),
    staff_id: Optional[UUID] = Query(default=None),
    status: Optional[SalonAppointmentStatus] = Query(default=None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> List[SalonAppointmentResponse]:
    return await service.list_appointments(
        current_user, organization_id, business_id, appointment_date, staff_id, status
    )


@router.get(
    "/appointments/{appointment_id}",
    response_model=SalonAppointmentResponse,
    summary="Get single salon appointment details",
)
async def get_appointment(
    organization_id: UUID,
    business_id: UUID,
    appointment_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonAppointmentResponse:
    return await service.get_appointment(current_user, organization_id, business_id, appointment_id)


@router.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=SalonAppointmentResponse,
    summary="Reschedule a confirmed salon appointment",
)
async def reschedule_appointment(
    organization_id: UUID,
    business_id: UUID,
    appointment_id: UUID,
    payload: SalonAppointmentRescheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonAppointmentResponse:
    return await service.reschedule_appointment(
        current_user, organization_id, business_id, appointment_id, payload
    )


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=SalonAppointmentResponse,
    summary="Cancel a salon appointment",
)
async def cancel_appointment(
    organization_id: UUID,
    business_id: UUID,
    appointment_id: UUID,
    payload: SalonAppointmentCancelRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: SalonWorkflowService = Depends(get_salon_workflow_service),
) -> SalonAppointmentResponse:
    return await service.cancel_appointment(
        current_user, organization_id, business_id, appointment_id, payload
    )
