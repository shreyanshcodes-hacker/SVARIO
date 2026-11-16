"""Stage 6 Clinic Workflow Agent Tools.

Implements backend execution handlers for the 10 Clinic AI Agent Tools:
1. `get_clinic_information`
2. `get_clinic_departments`
3. `get_clinic_doctors`
4. `get_clinic_specialities`
5. `get_clinic_consultation_types`
6. `check_clinic_availability`
7. `create_clinic_appointment`
8. `reschedule_clinic_appointment`
9. `cancel_clinic_appointment`
10. `request_clinic_human_escalation`

Security & Privacy Guarantees:
- Organization and business IDs are ALWAYS resolved strictly from verified session context (`bundle`).
- Model-supplied `organization_id`, `business_id`, or `tenant_id` are strictly forbidden.
- Appointments are confirmed ONLY after backend transaction commits.
- Rescheduling and cancellation require caller verification (`patient_contact_verification`)
  and never disclose whether an appointment exists when verification fails.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID
from fastapi import HTTPException
from app.agents.context import ConversationContextManager
from app.agents.schemas import (
    CancelClinicAppointmentToolInput,
    CancelClinicAppointmentToolOutput,
    CheckClinicAvailabilityToolInput,
    CheckClinicAvailabilityToolOutput,
    ClinicConsultationTypeSummaryItem,
    ClinicDepartmentSummaryItem,
    ClinicDoctorSummaryItem,
    ClinicSlotSummaryItem,
    ClinicSpecialitySummaryItem,
    CreateClinicAppointmentToolInput,
    CreateClinicAppointmentToolOutput,
    GetClinicConsultationTypesToolInput,
    GetClinicConsultationTypesToolOutput,
    GetClinicDepartmentsToolInput,
    GetClinicDepartmentsToolOutput,
    GetClinicDoctorsToolInput,
    GetClinicDoctorsToolOutput,
    GetClinicInformationToolInput,
    GetClinicInformationToolOutput,
    GetClinicSpecialitiesToolInput,
    GetClinicSpecialitiesToolOutput,
    RequestClinicHumanEscalationToolInput,
    RequestHumanEscalationToolOutput,
    RescheduleClinicAppointmentToolInput,
    RescheduleClinicAppointmentToolOutput,
)
from app.agents.tools.escalation import execute_request_human_escalation
from app.core.auth import AuthenticatedUser
from app.modules.clinics.schemas import (
    ClinicAppointmentCancelRequest,
    ClinicAppointmentCreateRequest,
    ClinicAppointmentRescheduleRequest,
    ClinicAppointmentSource,
)
from app.modules.clinics.service import INTERNAL_VOICE_ISSUER, ClinicWorkflowService
from app.modules.onboarding.schemas import OnboardingBundleResponse


def _get_system_actor(
    bundle: OnboardingBundleResponse, actor_user_id: Optional[UUID] = None
) -> AuthenticatedUser:
    """Create a scoped AuthenticatedUser representing the verified voice agent session."""
    user_id = actor_user_id or bundle.profile.id or bundle.organization.id
    return AuthenticatedUser(
        id=user_id,
        email=bundle.profile.email or "agent@svario.ai",
        issuer=INTERNAL_VOICE_ISSUER,
        audience="authenticated",
        raw_token="session-voice-agent-token",
    )


def _run_sync(coro: Any) -> Any:
    """Execute an async service coroutine from synchronous tool dispatch thread."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def execute_get_clinic_information(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
) -> GetClinicInformationToolOutput:
    """Execute `get_clinic_information` tool."""
    GetClinicInformationToolInput.model_validate(raw_arguments or {})
    p = bundle.profile
    address_parts = [part for part in [p.address, p.city, p.state, p.country, p.postal_code] if part]
    return GetClinicInformationToolOutput(
        clinic_name=p.display_name,
        description=p.description,
        phone=p.phone,
        email=p.email,
        address_summary=", ".join(address_parts) if address_parts else None,
        timezone=p.timezone,
        operating_hours=bundle.hours.schedule if bundle.hours else [],
        supported_languages=bundle.languages.supported_languages,
    )


def execute_get_clinic_departments(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> GetClinicDepartmentsToolOutput:
    """Execute `get_clinic_departments` tool."""
    validated = GetClinicDepartmentsToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)
    departments = _run_sync(
        clinic_service.list_departments(
            actor,
            bundle.organization.id,
            bundle.business_id,
            active_only=validated.active_only,
        )
    )
    items = [
        ClinicDepartmentSummaryItem(
            department_id=str(d.id),
            name=d.name,
            description=d.description,
        )
        for d in departments
    ]
    return GetClinicDepartmentsToolOutput(departments=items, total_count=len(items))


def execute_get_clinic_specialities(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> GetClinicSpecialitiesToolOutput:
    """Execute `get_clinic_specialities` tool."""
    validated = GetClinicSpecialitiesToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)
    specialities = _run_sync(
        clinic_service.list_specialities(
            actor,
            bundle.organization.id,
            bundle.business_id,
            active_only=validated.active_only,
        )
    )
    items = [
        ClinicSpecialitySummaryItem(
            speciality_id=str(s.id),
            name=s.name,
            description=s.description,
        )
        for s in specialities
    ]
    return GetClinicSpecialitiesToolOutput(specialities=items, total_count=len(items))


def execute_get_clinic_doctors(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> GetClinicDoctorsToolOutput:
    """Execute `get_clinic_doctors` tool."""
    validated = GetClinicDoctorsToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)
    doctors = _run_sync(
        clinic_service.list_doctors(
            actor,
            bundle.organization.id,
            bundle.business_id,
            active_only=validated.active_only,
            department_id=validated.department_id,
            speciality_id=validated.speciality_id,
        )
    )
    items = [
        ClinicDoctorSummaryItem(
            doctor_id=str(doc.id),
            display_name=doc.display_name,
            professional_title=doc.professional_title,
            languages=doc.languages,
            department_ids=[str(uid) for uid in doc.department_ids],
            speciality_ids=[str(uid) for uid in doc.speciality_ids],
            consultation_type_ids=[str(uid) for uid in doc.consultation_type_ids],
        )
        for doc in doctors
    ]
    return GetClinicDoctorsToolOutput(doctors=items, total_count=len(items))


def execute_get_clinic_consultation_types(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> GetClinicConsultationTypesToolOutput:
    """Execute `get_clinic_consultation_types` tool."""
    validated = GetClinicConsultationTypesToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)
    items_raw = _run_sync(
        clinic_service.list_consultation_types(
            actor,
            bundle.organization.id,
            bundle.business_id,
            active_only=validated.active_only,
        )
    )
    items = [
        ClinicConsultationTypeSummaryItem(
            consultation_type_id=str(c.id),
            name=c.name,
            description=c.description,
            duration_minutes=c.duration_minutes,
            consultation_mode=c.consultation_mode.value,
            fee_amount=float(c.fee_amount) if c.fee_amount is not None else None,
            currency_code=c.currency_code,
        )
        for c in items_raw
    ]
    return GetClinicConsultationTypesToolOutput(
        consultation_types=items, total_count=len(items)
    )


def execute_check_clinic_availability(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> CheckClinicAvailabilityToolOutput:
    """Execute `check_clinic_availability` tool."""
    validated = CheckClinicAvailabilityToolInput.model_validate(raw_arguments or {})
    parsed_date = date.fromisoformat(validated.target_date)
    actor = _get_system_actor(bundle, actor_user_id)
    availability = _run_sync(
        clinic_service.get_availability(
            actor,
            bundle.organization.id,
            bundle.business_id,
            consultation_type_id=validated.consultation_type_id,
            target_date=parsed_date,
            doctor_id=validated.doctor_id,
            department_id=validated.department_id,
            speciality_id=validated.speciality_id,
        )
    )
    slots = [
        ClinicSlotSummaryItem(
            doctor_id=str(s.doctor_id),
            doctor_name=s.doctor_name,
            starts_at=s.starts_at.isoformat(),
            ends_at=s.ends_at.isoformat(),
            timezone=s.timezone,
        )
        for s in availability.slots
    ]
    return CheckClinicAvailabilityToolOutput(
        target_date=availability.target_date.isoformat(),
        timezone=availability.timezone,
        duration_minutes=availability.duration_minutes,
        available_slots=slots,
        total_slots=len(slots),
    )


def execute_create_clinic_appointment(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> CreateClinicAppointmentToolOutput:
    """Execute `create_clinic_appointment` tool."""
    validated = CreateClinicAppointmentToolInput.model_validate(raw_arguments or {})
    starts_dt = datetime.fromisoformat(validated.starts_at)
    actor = _get_system_actor(bundle, actor_user_id)
    idem = validated.idempotency_key or (
        f"voice-{bundle.business_id}-{validated.doctor_id}-{starts_dt.isoformat()}-{validated.patient_contact[-4:]}"
    )
    req = ClinicAppointmentCreateRequest(
        doctor_id=validated.doctor_id,
        consultation_type_id=validated.consultation_type_id,
        department_id=validated.department_id,
        patient_display_name=validated.patient_display_name,
        patient_contact=validated.patient_contact,
        starts_at=starts_dt,
        idempotency_key=idem[:120],
        source=ClinicAppointmentSource.VOICE_AGENT,
    )
    try:
        appt = _run_sync(
            clinic_service.create_appointment(
                actor, bundle.organization.id, bundle.business_id, req
            )
        )
        return CreateClinicAppointmentToolOutput(
            booked=True,
            booking_reference=appt.booking_reference,
            appointment_id=str(appt.id),
            doctor_name=appt.doctor_name,
            consultation_type_name=appt.consultation_type_name,
            starts_at=appt.starts_at.isoformat(),
            ends_at=appt.ends_at.isoformat(),
            timezone=appt.timezone,
            status=appt.status.value,
            message="Clinic appointment successfully booked and committed.",
        )
    except HTTPException as exc:
        return CreateClinicAppointmentToolOutput(
            booked=False,
            status="rejected",
            message=str(exc.detail),
        )


def execute_reschedule_clinic_appointment(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> RescheduleClinicAppointmentToolOutput:
    """Execute `reschedule_clinic_appointment` tool with strict patient verification."""
    validated = RescheduleClinicAppointmentToolInput.model_validate(raw_arguments or {})
    new_starts_dt = datetime.fromisoformat(validated.new_starts_at)
    actor = _get_system_actor(bundle, actor_user_id)

    appt = _run_sync(
        clinic_service.get_appointment_by_reference(
            actor, bundle.organization.id, bundle.business_id, validated.booking_reference
        )
    )
    if not appt:
        return RescheduleClinicAppointmentToolOutput(
            rescheduled=False,
            booking_reference=validated.booking_reference,
            status="verification_failed",
            message="Appointment could not be verified with the provided reference and contact.",
        )

    req = ClinicAppointmentRescheduleRequest(
        new_starts_at=new_starts_dt,
        new_doctor_id=validated.new_doctor_id,
        patient_contact_verification=validated.patient_contact_verification,
    )
    try:
        updated = _run_sync(
            clinic_service.reschedule_appointment(
                actor,
                bundle.organization.id,
                bundle.business_id,
                appt.id,
                req,
                require_patient_verification=True,
            )
        )
        return RescheduleClinicAppointmentToolOutput(
            rescheduled=True,
            booking_reference=updated.booking_reference,
            new_starts_at=updated.starts_at.isoformat(),
            new_ends_at=updated.ends_at.isoformat(),
            doctor_name=updated.doctor_name,
            status=updated.status.value,
            message="Clinic appointment successfully rescheduled.",
        )
    except HTTPException as exc:
        return RescheduleClinicAppointmentToolOutput(
            rescheduled=False,
            booking_reference=validated.booking_reference,
            status="rejected",
            message=str(exc.detail),
        )


def execute_cancel_clinic_appointment(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
    clinic_service: ClinicWorkflowService,
    actor_user_id: Optional[UUID] = None,
) -> CancelClinicAppointmentToolOutput:
    """Execute `cancel_clinic_appointment` tool with strict patient verification."""
    validated = CancelClinicAppointmentToolInput.model_validate(raw_arguments or {})
    actor = _get_system_actor(bundle, actor_user_id)

    appt = _run_sync(
        clinic_service.get_appointment_by_reference(
            actor, bundle.organization.id, bundle.business_id, validated.booking_reference
        )
    )
    if not appt:
        return CancelClinicAppointmentToolOutput(
            cancelled=False,
            booking_reference=validated.booking_reference,
            status="verification_failed",
            message="Appointment could not be verified with the provided reference and contact.",
        )

    req = ClinicAppointmentCancelRequest(
        reason=validated.reason,
        patient_contact_verification=validated.patient_contact_verification,
    )
    try:
        updated = _run_sync(
            clinic_service.cancel_appointment(
                actor,
                bundle.organization.id,
                bundle.business_id,
                appt.id,
                req,
                require_patient_verification=True,
            )
        )
        return CancelClinicAppointmentToolOutput(
            cancelled=True,
            booking_reference=updated.booking_reference,
            status=updated.status.value,
            message="Clinic appointment successfully cancelled.",
        )
    except HTTPException as exc:
        return CancelClinicAppointmentToolOutput(
            cancelled=False,
            booking_reference=validated.booking_reference,
            status="rejected",
            message=str(exc.detail),
        )


def execute_request_clinic_human_escalation(
    *,
    bundle: OnboardingBundleResponse,
    session_id: str,
    raw_arguments: Dict[str, Any],
    context_manager: ConversationContextManager,
    actor_user_id: Optional[UUID] = None,
) -> RequestHumanEscalationToolOutput:
    """Execute `request_clinic_human_escalation` by delegating to the controlled escalation pipeline."""
    validated = RequestClinicHumanEscalationToolInput.model_validate(raw_arguments or {})
    return execute_request_human_escalation(
        bundle=bundle,
        session_id=session_id,
        raw_arguments=validated.model_dump(),
        context_manager=context_manager,
        actor_user_id=actor_user_id,
    )
