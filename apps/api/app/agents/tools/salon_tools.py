"""Stage 5 Salon Workflow Agent Tools.

Implements backend execution handlers for the 6 Salon AI Agent Tools:
1. `get_salon_services`
2. `get_salon_staff`
3. `check_salon_availability`
4. `create_salon_appointment`
5. `reschedule_salon_appointment`
6. `cancel_salon_appointment`

Security & Architecture Guarantees:
- Organization and business IDs are ALWAYS resolved strictly from verified session context (`bundle`).
- Model-supplied `organization_id`, `business_id`, or `tenant_id` are strictly forbidden.
- Appointments are confirmed ONLY when successfully committed by the backend service.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID
from app.agents.schemas import (
    CancelSalonAppointmentToolInput,
    CancelSalonAppointmentToolOutput,
    CheckSalonAvailabilityToolInput,
    CheckSalonAvailabilityToolOutput,
    CreateSalonAppointmentToolInput,
    CreateSalonAppointmentToolOutput,
    GetSalonServicesToolInput,
    GetSalonServicesToolOutput,
    GetSalonStaffToolInput,
    GetSalonStaffToolOutput,
    RescheduleSalonAppointmentToolInput,
    RescheduleSalonAppointmentToolOutput,
    SalonServiceSummaryItem,
    SalonSlotSummaryItem,
    SalonStaffSummaryItem,
)
from app.core.auth import AuthenticatedUser
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentSource,
)
from app.modules.salons.service import SalonWorkflowService


def _get_system_actor(bundle: OnboardingBundleResponse, actor_user_id: Optional[UUID] = None) -> AuthenticatedUser:
    """Create a scoped AuthenticatedUser instance representing the voice agent session."""
    user_id = actor_user_id or bundle.profile.id or bundle.organization.id
    return AuthenticatedUser(
        id=user_id,
        email=bundle.profile.email or "agent@svario.ai",
        issuer="https://svario.internal/auth/v1",
        audience="authenticated",
        raw_token="session-voice-agent-token",
    )


def execute_get_salon_services(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    salon_service: SalonWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> GetSalonServicesToolOutput:
    """Execute `get_salon_services` tool synchronously."""
    validated = GetSalonServicesToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    # Run coroutine synchronously inside the worker thread
    loop = asyncio.new_event_loop()
    try:
        services = loop.run_until_complete(
            salon_service.list_services(
                actor=actor,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                category=validated.category,
                is_active=validated.is_active,
            )
        )
    finally:
        loop.close()

    items = [
        SalonServiceSummaryItem(
            service_id=str(s.id),
            name=s.name,
            category=s.category,
            price=s.price,
            currency=s.currency,
            duration_minutes=s.duration_minutes,
        )
        for s in services
    ]
    categories = sorted(list({s.category for s in services}))

    return GetSalonServicesToolOutput(
        services=items,
        count=len(items),
        categories=categories,
    )


def execute_get_salon_staff(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    salon_service: SalonWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> GetSalonStaffToolOutput:
    """Execute `get_salon_staff` tool synchronously."""
    validated = GetSalonStaffToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    svc_uuid: Optional[UUID] = None
    if validated.service_id:
        try:
            svc_uuid = UUID(validated.service_id.strip())
        except ValueError:
            svc_uuid = None

    loop = asyncio.new_event_loop()
    try:
        staff_list = loop.run_until_complete(
            salon_service.list_staff(
                actor=actor,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                service_id=svc_uuid,
                is_active=True,
            )
        )
    finally:
        loop.close()

    items = [
        SalonStaffSummaryItem(
            staff_id=str(st.id),
            name=st.full_name,
            role=st.role_designation,
            assigned_service_names=st.assigned_service_names,
        )
        for st in staff_list
    ]

    return GetSalonStaffToolOutput(
        staff=items,
        count=len(items),
    )


def execute_check_salon_availability(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    salon_service: SalonWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> CheckSalonAvailabilityToolOutput:
    """Execute `check_salon_availability` tool synchronously."""
    validated = CheckSalonAvailabilityToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    try:
        svc_uuid = UUID(validated.service_id.strip())
    except ValueError:
        raise ValueError(f"Invalid service_id format: '{validated.service_id}'. Must be a valid UUID.")

    try:
        req_date = date.fromisoformat(validated.requested_date.strip())
    except ValueError:
        raise ValueError(f"Invalid requested_date format: '{validated.requested_date}'. Must be YYYY-MM-DD.")

    staff_uuid: Optional[UUID] = None
    if validated.staff_id:
        try:
            staff_uuid = UUID(validated.staff_id.strip())
        except ValueError:
            pass

    loop = asyncio.new_event_loop()
    try:
        avail = loop.run_until_complete(
            salon_service.get_salon_availability(
                actor=actor,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                service_id=svc_uuid,
                requested_date=req_date,
                staff_id=staff_uuid,
            )
        )
    finally:
        loop.close()

    slot_items = [
        SalonSlotSummaryItem(
            start_time=s.start_time,
            end_time=s.end_time,
            staff_id=str(s.staff_id),
            staff_name=s.staff_name,
            staff_role=s.staff_role,
        )
        for s in avail.available_slots
    ]

    return CheckSalonAvailabilityToolOutput(
        service_name=avail.service_name,
        duration_minutes=avail.duration_minutes,
        requested_date=str(avail.requested_date),
        timezone=avail.timezone,
        is_business_closed=avail.is_business_closed,
        closure_reason=avail.closure_reason,
        available_slots=slot_items,
        total_slots_available=len(slot_items),
    )


def execute_create_salon_appointment(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    salon_service: SalonWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> CreateSalonAppointmentToolOutput:
    """Execute `create_salon_appointment` tool synchronously."""
    validated = CreateSalonAppointmentToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    try:
        svc_uuid = UUID(validated.service_id.strip())
    except ValueError:
        raise ValueError(f"Invalid service_id format: '{validated.service_id}'.")

    try:
        appt_date = date.fromisoformat(validated.appointment_date.strip())
    except ValueError:
        raise ValueError(f"Invalid appointment_date format: '{validated.appointment_date}'.")

    staff_uuid: Optional[UUID] = None
    if validated.staff_id:
        try:
            staff_uuid = UUID(validated.staff_id.strip())
        except ValueError:
            pass

    create_req = SalonAppointmentCreateRequest(
        service_id=svc_uuid,
        staff_id=staff_uuid,
        appointment_date=appt_date,
        start_time=validated.start_time,
        customer_name=validated.customer_name,
        customer_phone=validated.customer_phone,
        customer_email=validated.customer_email,
        notes=validated.notes,
        idempotency_key=validated.idempotency_key,
        source=SalonAppointmentSource.VOICE_AGENT,
    )

    loop = asyncio.new_event_loop()
    try:
        appt = loop.run_until_complete(
            salon_service.create_appointment(
                actor=actor,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                payload=create_req,
            )
        )
    finally:
        loop.close()

    msg = (
        f"Appointment successfully booked for {appt.customer_name} on {appt.appointment_date} "
        f"at {appt.start_time} with {appt.staff_name}. Booking reference: {appt.booking_reference}."
    )

    return CreateSalonAppointmentToolOutput(
        booking_confirmed=True,
        booking_reference=appt.booking_reference,
        service_name=appt.service_name,
        staff_name=appt.staff_name,
        appointment_date=str(appt.appointment_date),
        start_time=appt.start_time,
        end_time=appt.end_time,
        duration_minutes=appt.service_duration_minutes,
        price=appt.service_price,
        currency=appt.service_currency,
        customer_name=appt.customer_name,
        customer_phone=appt.customer_phone,
        timezone=appt.timezone,
        message=msg,
    )


def execute_reschedule_salon_appointment(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    salon_service: SalonWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> RescheduleSalonAppointmentToolOutput:
    """Execute `reschedule_salon_appointment` tool synchronously."""
    validated = RescheduleSalonAppointmentToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    try:
        appt_uuid = UUID(validated.appointment_id.strip())
    except ValueError:
        raise ValueError(f"Invalid appointment_id: '{validated.appointment_id}'. Must be a UUID.")

    try:
        new_date = date.fromisoformat(validated.new_date.strip())
    except ValueError:
        raise ValueError(f"Invalid new_date format: '{validated.new_date}'. Must be YYYY-MM-DD.")

    new_staff_uuid: Optional[UUID] = None
    if validated.new_staff_id:
        try:
            new_staff_uuid = UUID(validated.new_staff_id.strip())
        except ValueError:
            pass

    reschedule_req = SalonAppointmentRescheduleRequest(
        appointment_date=new_date,
        start_time=validated.new_start_time,
        staff_id=new_staff_uuid,
        notes=validated.notes,
    )

    loop = asyncio.new_event_loop()
    try:
        appt = loop.run_until_complete(
            salon_service.reschedule_appointment(
                actor=actor,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                appointment_id=appt_uuid,
                payload=reschedule_req,
            )
        )
    finally:
        loop.close()

    msg = (
        f"Appointment {appt.booking_reference} successfully rescheduled to {appt.appointment_date} "
        f"at {appt.start_time} with {appt.staff_name}."
    )

    return RescheduleSalonAppointmentToolOutput(
        reschedule_confirmed=True,
        booking_reference=appt.booking_reference,
        service_name=appt.service_name,
        staff_name=appt.staff_name,
        new_date=str(appt.appointment_date),
        new_start_time=appt.start_time,
        new_end_time=appt.end_time,
        message=msg,
    )


def execute_cancel_salon_appointment(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    salon_service: SalonWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> CancelSalonAppointmentToolOutput:
    """Execute `cancel_salon_appointment` tool synchronously."""
    validated = CancelSalonAppointmentToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    try:
        appt_uuid = UUID(validated.appointment_id.strip())
    except ValueError:
        raise ValueError(f"Invalid appointment_id: '{validated.appointment_id}'. Must be a UUID.")

    cancel_req = SalonAppointmentCancelRequest(
        cancellation_reason=validated.cancellation_reason,
    )

    loop = asyncio.new_event_loop()
    try:
        appt = loop.run_until_complete(
            salon_service.cancel_appointment(
                actor=actor,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                appointment_id=appt_uuid,
                payload=cancel_req,
            )
        )
    finally:
        loop.close()

    msg = f"Appointment {appt.booking_reference} for {appt.service_name} on {appt.appointment_date} has been cancelled."

    return CancelSalonAppointmentToolOutput(
        cancellation_confirmed=True,
        booking_reference=appt.booking_reference,
        service_name=appt.service_name,
        appointment_date=str(appt.appointment_date),
        start_time=appt.start_time,
        message=msg,
    )
