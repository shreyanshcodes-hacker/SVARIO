"""Comprehensive test suite for Stage 5: Salon Workflow Module.

Covers:
1. Salon Service CRUD, validation (price > 0, duration 5..480), active filters.
2. Staff profiles, active status, service assignments.
3. Salon schedules, staff working hours, breaks, holidays.
4. Dynamic availability slot calculation.
5. Appointment booking, idempotency key replay, double-booking prevention.
6. Reschedule and cancellation workflows.
7. Authorization & multi-tenant isolation.
8. Agent tool execution and orchestrator integration.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException

from app.core.auth import AuthenticatedUser
from app.core.config import get_settings
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.schemas import (
    BusinessHoursUpdateRequest,
    BusinessProfileResponse,
    LanguageCode,
    OnboardingBundleResponse,
    WeekdayHoursItem,
)
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationIndustry,
    OrganizationRole,
)
from app.modules.salons.repository import InMemorySalonRepository
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAppointmentRescheduleRequest,
    SalonAppointmentStatus,
    SalonServiceCreateRequest,
    SalonServiceUpdateRequest,
    SalonStaffBreakCreateRequest,
    SalonStaffCreateRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
)
from app.modules.salons.service import SalonWorkflowService
from app.agents.schemas import AgentToolName
from app.agents.orchestrator import AgentOrchestrator
from app.agents.context import ConversationContextManager
from app.modules.voice.rate_limit import VoiceSessionRateLimiter


@pytest.fixture
def owner_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        email="salon_owner@example.com",
        role="authenticated",
        issuer="https://test.supabase.co",
        audience="authenticated",
        raw_token="mock.owner.token",
    )


@pytest.fixture
def viewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        email="salon_viewer@example.com",
        role="authenticated",
        issuer="https://test.supabase.co",
        audience="authenticated",
        raw_token="mock.viewer.token",
    )


@pytest.fixture
async def salon_env(
    owner_user: AuthenticatedUser, viewer_user: AuthenticatedUser
) -> Dict[str, Any]:
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)

    org_summary = await org_repo.create_organization(
        owner_user,
        CreateOrganizationRequest(
            name="Luxe Hair Lounge",
            industry=OrganizationIndustry.SALON,
            timezone="Asia/Kolkata",
        ),
    )
    org_id = org_summary.id
    biz_id = org_repo._businesses[org_id][0]["id"]

    # Add viewer_user as regular STAFF
    org_repo._members[org_id].append(
        {
            "id": uuid4(),
            "organization_id": org_id,
            "user_id": viewer_user.id,
            "role": OrganizationRole.STAFF,
            "created_at": datetime.now(timezone.utc),
        }
    )

    # Seed weekly hours: 0=Sun (closed), 1=Mon..6=Sat open 09:00 to 19:00
    hours = [
        WeekdayHoursItem(
            weekday=i,
            is_closed=(i == 0),
            opens_at="09:00" if i != 0 else None,
            closes_at="19:00" if i != 0 else None,
        )
        for i in range(7)
    ]
    await onboarding_repo.upsert_business_hours(
        owner_user,
        org_id,
        biz_id,
        BusinessHoursUpdateRequest(timezone="Asia/Kolkata", schedule=hours),
    )

    settings = get_settings()
    salon_repo = InMemorySalonRepository()
    service = SalonWorkflowService(
        settings=settings,
        salon_repo=salon_repo,
        onboarding_repo=onboarding_repo,
    )
    return {
        "org_id": org_id,
        "biz_id": biz_id,
        "service": service,
        "onboarding_repo": onboarding_repo,
        "org_repo": org_repo,
        "org_summary": org_summary,
    }


# ==============================================================================
# 1. SERVICES CRUD & VALIDATIONS
# ==============================================================================

@pytest.mark.anyio
async def test_salon_service_crud_and_validations(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
    viewer_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    test_org_id: UUID = salon_env["org_id"]
    test_biz_id: UUID = salon_env["biz_id"]

    # 1. Create valid service
    service_req = SalonServiceCreateRequest(
        name="Precision Haircut",
        description="Signature styling and wash",
        category="Hair",
        duration_minutes=45,
        price=650.0,
        currency="INR",
        is_active=True,
    )
    created = await service.create_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=service_req,
    )
    assert created.name == "Precision Haircut"
    assert created.duration_minutes == 45
    assert created.price == 650.0
    assert created.is_active is True

    # 2. Validation: Duration must be between 5 and 480 mins
    with pytest.raises(Exception):
        SalonServiceCreateRequest(
            name="Instant Cut",
            duration_minutes=2,
            price=200.0,
        )
    with pytest.raises(Exception):
        SalonServiceCreateRequest(
            name="Marathon Treatment",
            duration_minutes=500,
            price=200.0,
        )

    # 3. Update service
    updated = await service.update_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        service_id=created.id,
        payload=SalonServiceUpdateRequest(
            price=750.0,
            is_active=False,
        ),
    )
    assert updated.price == 750.0
    assert updated.is_active is False

    # 4. List services active_only filter
    active_list = await service.list_services(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        is_active=True,
    )
    assert len(active_list) == 0

    all_list = await service.list_services(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        is_active=None,
    )
    assert len(all_list) == 1

    # 5. Non-admin cannot create/modify service (403 Forbidden)
    with pytest.raises(HTTPException) as exc:
        await service.create_service(
            actor=viewer_user,
            organization_id=test_org_id,
            business_id=test_biz_id,
            payload=service_req,
        )
    assert exc.value.status_code == 403


# ==============================================================================
# 2. STAFF MANAGEMENT & SERVICE ASSIGNMENTS
# ==============================================================================

@pytest.mark.anyio
async def test_salon_staff_management(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    test_org_id: UUID = salon_env["org_id"]
    test_biz_id: UUID = salon_env["biz_id"]

    svc = await service.create_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonServiceCreateRequest(
            name="Blowdry",
            duration_minutes=30,
            price=450.0,
        ),
    )

    staff = await service.create_staff(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonStaffCreateRequest(
            full_name="Elena Rostova",
            role_designation="Senior Stylist",
            email="elena@luxehair.com",
            phone="+919876543210",
        ),
    )
    assert staff.full_name == "Elena Rostova"
    assert staff.is_active is True

    # Assign service
    assigned = await service.assign_staff_services(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        service_ids=[svc.id],
    )
    assert svc.id in assigned.assigned_service_ids

    # Verify assignment filter
    assigned_staff = await service.list_staff(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        service_id=svc.id,
    )
    assert len(assigned_staff) == 1
    assert assigned_staff[0].id == staff.id


# ==============================================================================
# 3. SCHEDULES, BREAKS, HOLIDAYS & AVAILABILITY SLOTS
# ==============================================================================

@pytest.mark.anyio
async def test_dynamic_availability_computation(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    test_org_id: UUID = salon_env["org_id"]
    test_biz_id: UUID = salon_env["biz_id"]

    svc = await service.create_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonServiceCreateRequest(
            name="Classic Manicure",
            duration_minutes=30,
            price=350.0,
        ),
    )

    staff = await service.create_staff(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonStaffCreateRequest(
            full_name="Marcus Vance",
            role_designation="Nail Artist",
        ),
    )
    await service.assign_staff_services(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        service_ids=[svc.id],
    )

    # Working hours: Monday (weekday=1) 10:00 to 14:00
    await service.update_staff_working_hours(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        payload=SalonStaffWorkingHoursUpdateRequest(
            schedule=[
                SalonStaffWorkingHoursItem(
                    weekday=1,
                    start_time="10:00",
                    end_time="14:00",
                )
            ]
        ),
    )

    # Break: Monday 12:00 to 13:00
    await service.add_staff_break(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        payload=SalonStaffBreakCreateRequest(
            weekday=1,
            start_time="12:00",
            end_time="13:00",
            label="Lunch Break",
        ),
    )

    # 2026-11-16 is Monday
    target_monday = date(2026, 11, 16)

    avail = await service.get_salon_availability(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        service_id=svc.id,
        requested_date=target_monday,
        staff_id=staff.id,
    )

    slot_times = [s.start_time for s in avail.available_slots]
    assert "10:00" in slot_times
    assert "11:30" in slot_times
    assert "12:00" not in slot_times
    assert "12:30" not in slot_times
    assert "13:00" in slot_times
    assert "13:30" in slot_times
    assert "14:00" not in slot_times


# ==============================================================================
# 4. APPOINTMENT BOOKING, IDEMPOTENCY & OVERLAP REJECTION
# ==============================================================================

@pytest.mark.anyio
async def test_appointment_booking_idempotency_and_double_booking_prevention(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    test_org_id: UUID = salon_env["org_id"]
    test_biz_id: UUID = salon_env["biz_id"]

    svc = await service.create_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonServiceCreateRequest(
            name="Balayage",
            duration_minutes=60,
            price=1500.0,
        ),
    )
    staff = await service.create_staff(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonStaffCreateRequest(
            full_name="Chloe Bennett",
            role_designation="Colorist",
        ),
    )
    await service.assign_staff_services(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        service_ids=[svc.id],
    )
    await service.update_staff_working_hours(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        payload=SalonStaffWorkingHoursUpdateRequest(
            schedule=[
                SalonStaffWorkingHoursItem(
                    weekday=1,
                    start_time="09:00",
                    end_time="18:00",
                )
            ]
        ),
    )

    target_monday = date(2026, 11, 16)

    booking_payload = SalonAppointmentCreateRequest(
        service_id=svc.id,
        staff_id=staff.id,
        appointment_date=target_monday,
        start_time="10:00",
        customer_name="Alice Smith",
        customer_phone="+919876543211",
        customer_email="alice@example.com",
        idempotency_key="req_alice_001",
    )

    # First booking succeeds
    appt1 = await service.create_appointment(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=booking_payload,
    )
    assert appt1.status == SalonAppointmentStatus.CONFIRMED
    assert appt1.customer_name == "Alice Smith"

    # Idempotent replay with same key returns identical appointment
    appt1_replay = await service.create_appointment(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=booking_payload,
    )
    assert appt1_replay.id == appt1.id

    # Second booking for SAME staff at SAME time with DIFFERENT key must be REJECTED (409 Conflict)
    conflict_payload = SalonAppointmentCreateRequest(
        service_id=svc.id,
        staff_id=staff.id,
        appointment_date=target_monday,
        start_time="10:00",
        customer_name="Bob Jones",
        customer_phone="+919876543212",
        idempotency_key="req_bob_002",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.create_appointment(
            actor=owner_user,
            organization_id=test_org_id,
            business_id=test_biz_id,
            payload=conflict_payload,
        )
    assert exc_info.value.status_code == 409


# ==============================================================================
# 5. RESCHEDULE & CANCELLATION
# ==============================================================================

@pytest.mark.anyio
async def test_appointment_reschedule_and_cancel(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    test_org_id: UUID = salon_env["org_id"]
    test_biz_id: UUID = salon_env["biz_id"]

    svc = await service.create_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonServiceCreateRequest(
            name="Facial Treatment",
            duration_minutes=45,
            price=800.0,
        ),
    )
    staff = await service.create_staff(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonStaffCreateRequest(
            full_name="Zara Khan",
            role_designation="Esthetician",
        ),
    )
    await service.assign_staff_services(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        service_ids=[svc.id],
    )
    # Tuesday working hours (weekday=2)
    await service.update_staff_working_hours(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        staff_id=staff.id,
        payload=SalonStaffWorkingHoursUpdateRequest(
            schedule=[
                SalonStaffWorkingHoursItem(
                    weekday=2,
                    start_time="09:00",
                    end_time="18:00",
                )
            ]
        ),
    )

    target_tuesday = date(2026, 11, 17)
    appt = await service.create_appointment(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonAppointmentCreateRequest(
            service_id=svc.id,
            staff_id=staff.id,
            appointment_date=target_tuesday,
            start_time="11:00",
            customer_name="Daniel Craig",
            customer_phone="+919876543213",
        ),
    )

    # Reschedule to 14:00
    rescheduled = await service.reschedule_appointment(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        appointment_id=appt.id,
        payload=SalonAppointmentRescheduleRequest(
            appointment_date=target_tuesday,
            start_time="14:00",
            notes="Client requested afternoon slot",
        ),
    )
    assert rescheduled.status == SalonAppointmentStatus.RESCHEDULED
    assert rescheduled.start_time == "14:00"

    # Cancel appointment
    cancelled = await service.cancel_appointment(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        appointment_id=appt.id,
        payload=SalonAppointmentCancelRequest(cancellation_reason="Personal conflict"),
    )
    assert cancelled.status == SalonAppointmentStatus.CANCELLED
    assert cancelled.cancellation_reason == "Personal conflict"


# ==============================================================================
# 6. MULTI-TENANT ISOLATION
# ==============================================================================

@pytest.mark.anyio
async def test_cross_tenant_isolation(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    foreign_org_id = uuid4()
    foreign_biz_id = uuid4()

    # Attempting to access foreign organization must fail (403 Forbidden)
    with pytest.raises(HTTPException) as exc_info:
        await service.list_services(
            actor=owner_user,
            organization_id=foreign_org_id,
            business_id=foreign_biz_id,
        )
    assert exc_info.value.status_code == 403


# ==============================================================================
# 7. AGENT TOOL INTEGRATION VIA ORCHESTRATOR
# ==============================================================================

@pytest.mark.anyio
async def test_agent_orchestrator_salon_tools(
    salon_env: Dict[str, Any],
    owner_user: AuthenticatedUser,
) -> None:
    service: SalonWorkflowService = salon_env["service"]
    onboarding_repo: InMemoryOnboardingRepository = salon_env["onboarding_repo"]
    test_org_id: UUID = salon_env["org_id"]
    test_biz_id: UUID = salon_env["biz_id"]

    svc = await service.create_service(
        actor=owner_user,
        organization_id=test_org_id,
        business_id=test_biz_id,
        payload=SalonServiceCreateRequest(
            name="Keratin Treatment",
            duration_minutes=90,
            price=2000.0,
            is_active=True,
        ),
    )

    from app.modules.onboarding.service import OnboardingService

    onboarding_service = OnboardingService(repository=onboarding_repo)
    bundle = await onboarding_service.get_onboarding_bundle(
        actor=owner_user, organization_id=test_org_id
    )

    orchestrator = AgentOrchestrator(
        context_manager=ConversationContextManager(),
        rate_limiter=VoiceSessionRateLimiter(),
        salon_service=service,
    )

    # Execute get_salon_services tool
    res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id="session_test_salon_001",
        call_id="call_001",
        tool_name=AgentToolName.GET_SALON_SERVICES,
        arguments={"is_active": True},
        actor_user_id=owner_user.id,
    )
    assert res.status == "succeeded"
    assert res.output["count"] >= 1
    assert any(s["name"] == "Keratin Treatment" for s in res.output["services"])
