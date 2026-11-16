"""Stage 6 Clinic Workflow Module — Comprehensive Backend, Security & AI Tool Tests."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Tuple
from uuid import UUID, uuid4
import pytest
from fastapi.testclient import TestClient
from app.agents.context import ConversationContextManager
from app.agents.intent import IntentClassifier
from app.agents.orchestrator import AgentOrchestrator
from app.agents.schemas import AgentIntent, AgentToolName, SafetyFlag
from app.core.auth import AuthenticatedUser, get_current_user
from app.main import app
from app.modules.clinics.repository import InMemoryClinicRepository
from app.modules.clinics.service import ClinicWorkflowService, get_clinic_workflow_service
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_repository
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    AssistantSettingsUpdateRequest,
    BusinessHoursUpdateRequest,
    BusinessLanguagesUpdateRequest,
    BusinessProfileUpdateRequest,
    EscalationSettingsUpdateRequest,
    LanguageCode,
    OnboardingBundleResponse,
    WeekdayHoursItem,
)
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.service import get_organization_repository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationIndustry,
    OrganizationRole,
)
from app.modules.voice.rate_limit import VoiceSessionRateLimiter


def _make_user(user_id: UUID, email: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user_id,
        email=email,
        issuer="https://test.supabase.co/auth/v1",
        audience="authenticated",
        raw_token="mock.jwt.token",
    )


async def _seed_clinic_env(
    org_repo: InMemoryOrganizationRepository,
    onboarding_repo: InMemoryOnboardingRepository,
    owner: AuthenticatedUser,
    *,
    industry: OrganizationIndustry = OrganizationIndustry.CLINIC,
    tz: str = "Asia/Kolkata",
) -> Tuple[UUID, UUID, OnboardingBundleResponse]:
    org = await org_repo.create_organization(
        owner,
        CreateOrganizationRequest(
            name="Apex Care Clinic" if industry == OrganizationIndustry.CLINIC else "Luxe Salon",
            industry=industry,
        ),
    )
    business_id = await onboarding_repo.get_or_create_primary_business_id(owner, org.id)

    await onboarding_repo.upsert_business_profile(
        owner,
        org.id,
        business_id,
        BusinessProfileUpdateRequest(
            display_name="Apex Care Clinic",
            description="Multi-speciality outpatient clinic",
            phone="+91-9876500001",
            email="desk@apexcare.example",
            address="10 Health Avenue",
            city="Bengaluru",
            state="KA",
            country="India",
            timezone=tz,
        ),
    )
    schedule = [
        WeekdayHoursItem(
            weekday=wd,
            is_closed=False,
            opens_at="08:00",
            closes_at="20:00",
            is_overnight=False,
        )
        for wd in range(7)
    ]
    await onboarding_repo.upsert_business_hours(
        owner, org.id, business_id, BusinessHoursUpdateRequest(timezone=tz, schedule=schedule)
    )
    await onboarding_repo.upsert_business_languages(
        owner,
        org.id,
        business_id,
        BusinessLanguagesUpdateRequest(
            primary_language=LanguageCode.ENGLISH,
            supported_languages=[LanguageCode.ENGLISH, LanguageCode.HINDI, LanguageCode.HINGLISH],
        ),
    )
    await onboarding_repo.upsert_assistant_settings(
        owner,
        org.id,
        business_id,
        AssistantSettingsUpdateRequest(
            assistant_name="Asha",
            greeting="Welcome to Apex Care Clinic.",
            personality=AssistantPersonality.WARM,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=True,
        ),
    )
    await onboarding_repo.upsert_escalation_settings(
        owner,
        org.id,
        business_id,
        EscalationSettingsUpdateRequest(
            enabled=True,
            contact_name="Nurse Priya",
            contact_phone="+91-9876500099",
            contact_email="nurse@apexcare.example",
            escalation_instructions="Escalate clinical questions immediately.",
        ),
    )
    updated_bundle = await OnboardingService(repository=onboarding_repo).get_onboarding_bundle(
        owner, org.id
    )
    return org.id, business_id, updated_bundle


@pytest.fixture
def clinic_test_context():
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    clinic_repo = InMemoryClinicRepository()
    clinic_service = ClinicWorkflowService(
        clinic_repo=clinic_repo,
        org_repo=org_repo,
        onboarding_repo=onboarding_repo,
    )

    owner_user = _make_user(uuid4(), "owner@apexcare.example")
    other_user = _make_user(uuid4(), "intruder@other.example")
    current_actor = {"user": owner_user}

    app.dependency_overrides[get_organization_repository] = lambda: org_repo
    app.dependency_overrides[get_onboarding_repository] = lambda: onboarding_repo
    app.dependency_overrides[get_clinic_workflow_service] = lambda: clinic_service
    app.dependency_overrides[get_current_user] = lambda: current_actor["user"]

    client = TestClient(app)
    yield client, org_repo, onboarding_repo, clinic_service, owner_user, other_user, current_actor
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_clinic_crud_mappings_schedules_and_availability(clinic_test_context):
    client, org_repo, onboarding_repo, clinic_service, owner, _, _ = clinic_test_context
    org_id, biz_id, _ = await _seed_clinic_env(org_repo, onboarding_repo, owner)
    base = f"/api/v1/organizations/{org_id}/clinics/{biz_id}"

    # 1. Department CRUD
    dept_resp = client.post(
        f"{base}/departments",
        json={"name": "General Medicine", "description": "Primary outpatient care"},
    )
    assert dept_resp.status_code == 201
    dept_id = dept_resp.json()["id"]

    # Duplicate department name -> 409
    dup_dept = client.post(f"{base}/departments", json={"name": "General Medicine"})
    assert dup_dept.status_code == 409

    # 2. Speciality CRUD
    spec_resp = client.post(
        f"{base}/specialities",
        json={"name": "Internal Medicine", "description": "Adult health"},
    )
    assert spec_resp.status_code == 201
    spec_id = spec_resp.json()["id"]

    # 3. Consultation Type CRUD & duration validation
    bad_ct = client.post(
        f"{base}/consultation-types",
        json={"name": "Too Short", "duration_minutes": 2, "consultation_mode": "in_person"},
    )
    assert bad_ct.status_code == 422

    ct_resp = client.post(
        f"{base}/consultation-types",
        json={
            "name": "Standard Consultation",
            "duration_minutes": 30,
            "consultation_mode": "in_person",
            "fee_amount": "800.00",
            "currency_code": "INR",
        },
    )
    assert ct_resp.status_code == 201
    ct_id = ct_resp.json()["id"]

    # 4. Doctor CRUD & mappings
    doc_resp = client.post(
        f"{base}/doctors",
        json={
            "display_name": "Dr. Meera Nair",
            "professional_title": "MD, General Physician",
            "languages": ["en", "hi"],
            "department_ids": [dept_id],
            "speciality_ids": [spec_id],
            "consultation_type_ids": [ct_id],
        },
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    # 5. Working hours (Monday = Svario weekday 1), break, and unavailability
    target_monday = date(2026, 11, 23)  # Monday
    wh_resp = client.put(
        f"{base}/doctors/{doc_id}/working-hours",
        json={
            "items": [
                {
                    "day_of_week": 1,
                    "start_time": "09:00:00",
                    "end_time": "12:00:00",
                    "is_active": True,
                }
            ]
        },
    )
    assert wh_resp.status_code == 200

    # Break 10:00 - 10:30
    br_resp = client.post(
        f"{base}/doctors/{doc_id}/breaks",
        json={
            "day_of_week": 1,
            "break_start": "10:00:00",
            "break_end": "10:30:00",
            "reason": "Tea break",
        },
    )
    assert br_resp.status_code == 201

    # Unavailability 11:30 - 12:00 IST (+05:30)
    unavail_resp = client.post(
        f"{base}/doctors/{doc_id}/unavailability",
        json={
            "starts_at": "2026-11-23T11:30:00+05:30",
            "ends_at": "2026-11-23T12:00:00+05:30",
            "reason": "Admin meeting",
        },
    )
    assert unavail_resp.status_code == 201

    # 6. Availability check: 09:00-12:00 in 30m slots = 6 slots, minus 10:00-10:30 break & 11:30-12:00 unavail = 4 slots
    avail_resp = client.get(
        f"{base}/availability",
        params={"consultation_type_id": ct_id, "target_date": target_monday.isoformat()},
    )
    assert avail_resp.status_code == 200
    slots = avail_resp.json()["slots"]
    assert len(slots) == 4
    slot_starts = [s["starts_at"] for s in slots]
    assert any("09:00:00" in s for s in slot_starts)
    assert any("09:30:00" in s for s in slot_starts)
    assert not any("10:00:00" in s for s in slot_starts)
    assert any("10:30:00" in s for s in slot_starts)
    assert any("11:00:00" in s for s in slot_starts)
    assert not any("11:30:00" in s for s in slot_starts)


@pytest.mark.anyio
async def test_clinic_appointment_booking_idempotency_concurrency_reschedule_cancel(
    clinic_test_context,
):
    client, org_repo, onboarding_repo, clinic_service, owner, _, _ = clinic_test_context
    org_id, biz_id, _ = await _seed_clinic_env(org_repo, onboarding_repo, owner)
    base = f"/api/v1/organizations/{org_id}/clinics/{biz_id}"

    ct_id = client.post(
        f"{base}/consultation-types",
        json={"name": "Follow-up", "duration_minutes": 30, "consultation_mode": "online"},
    ).json()["id"]
    doc_id = client.post(
        f"{base}/doctors",
        json={"display_name": "Dr. Arjun Rao", "consultation_type_ids": [ct_id]},
    ).json()["id"]
    client.put(
        f"{base}/doctors/{doc_id}/working-hours",
        json={
            "items": [
                {"day_of_week": 2, "start_time": "09:00:00", "end_time": "13:00:00", "is_active": True}
            ]
        },
    )

    slot_start = "2026-11-24T09:00:00+05:30"  # Tuesday
    # 1. Patient data minimization: extra medical fields must be rejected (422)
    bad_booking = client.post(
        f"{base}/appointments",
        json={
            "doctor_id": doc_id,
            "consultation_type_id": ct_id,
            "patient_display_name": "Rohan Sharma",
            "patient_contact": "+919999888877",
            "starts_at": slot_start,
            "symptoms": "fever and cough",
        },
    )
    assert bad_booking.status_code == 422

    # 2. Idempotent booking
    payload = {
        "doctor_id": doc_id,
        "consultation_type_id": ct_id,
        "patient_display_name": "Rohan Sharma",
        "patient_contact": "+919999888877",
        "starts_at": slot_start,
        "idempotency_key": "idem-clinic-001",
    }
    r1 = client.post(f"{base}/appointments", json=payload)
    r2 = client.post(f"{base}/appointments", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    appt_id = r1.json()["id"]

    # 3. Double-booking attempt on same slot without same idempotency key -> 409 Conflict
    r_conflict = client.post(
        f"{base}/appointments",
        json={
            "doctor_id": doc_id,
            "consultation_type_id": ct_id,
            "patient_display_name": "Priya Verma",
            "patient_contact": "+919999888866",
            "starts_at": slot_start,
            "idempotency_key": "idem-clinic-002",
        },
    )
    assert r_conflict.status_code == 409

    # 4. Concurrent booking attempts for 10:00 slot -> exactly 1 succeeds, 1 fails with 409
    from app.modules.clinics.schemas import ClinicAppointmentCreateRequest

    async def book_10am(name: str, key: str):
        return await clinic_service.create_appointment(
            owner,
            org_id,
            biz_id,
            ClinicAppointmentCreateRequest(
                doctor_id=UUID(doc_id),
                consultation_type_id=UUID(ct_id),
                patient_display_name=name,
                patient_contact="+919876543210",
                starts_at=datetime.fromisoformat("2026-11-24T10:00:00+05:30"),
                idempotency_key=key,
            ),
        )

    results = await asyncio.gather(
        book_10am("Caller A", "race-1"),
        book_10am("Caller B", "race-2"),
        return_exceptions=True,
    )
    successes = [res for res in results if not isinstance(res, Exception)]
    failures = [res for res in results if isinstance(res, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1

    # 5. Reschedule first appointment to 11:00
    resched = client.post(
        f"{base}/appointments/{appt_id}/reschedule",
        json={"new_starts_at": "2026-11-24T11:00:00+05:30"},
    )
    assert resched.status_code == 200
    assert resched.json()["status"] == "rescheduled"

    # 6. Cancel appointment (idempotent)
    cancel_1 = client.post(
        f"{base}/appointments/{appt_id}/cancel",
        json={"reason": "Patient requested"},
    )
    cancel_2 = client.post(
        f"{base}/appointments/{appt_id}/cancel",
        json={"reason": "Patient requested"},
    )
    assert cancel_1.status_code == 200
    assert cancel_1.json()["status"] == "cancelled"
    assert cancel_2.status_code == 200
    assert cancel_2.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_clinic_cross_tenant_isolation_and_industry_guard(clinic_test_context):
    client, org_repo, onboarding_repo, _, owner, other_user, current_actor = clinic_test_context
    org_id, biz_id, _ = await _seed_clinic_env(org_repo, onboarding_repo, owner)
    salon_org_id, salon_biz_id, _ = await _seed_clinic_env(
        org_repo, onboarding_repo, owner, industry=OrganizationIndustry.SALON
    )

    # Salon org cannot access clinic routes
    wrong_industry = client.get(
        f"/api/v1/organizations/{salon_org_id}/clinics/{salon_biz_id}/departments"
    )
    assert wrong_industry.status_code == 400

    # Unrelated user cannot read or mutate clinic org
    current_actor["user"] = other_user
    cross_read = client.get(f"/api/v1/organizations/{org_id}/clinics/{biz_id}/departments")
    assert cross_read.status_code == 404
    cross_write = client.post(
        f"/api/v1/organizations/{org_id}/clinics/{biz_id}/departments",
        json={"name": "Unauthorized Dept"},
    )
    assert cross_write.status_code == 404


@pytest.mark.anyio
async def test_clinic_ai_tools_safety_verification_and_emergency(clinic_test_context):
    client, org_repo, onboarding_repo, clinic_service, owner, _, _ = clinic_test_context
    org_id, biz_id, bundle = await _seed_clinic_env(org_repo, onboarding_repo, owner)
    base = f"/api/v1/organizations/{org_id}/clinics/{biz_id}"

    # Seed clinic data
    dept_id = client.post(f"{base}/departments", json={"name": "Dermatology"}).json()["id"]
    spec_id = client.post(f"{base}/specialities", json={"name": "Skin Care"}).json()["id"]
    ct_id = client.post(
        f"{base}/consultation-types",
        json={"name": "Skin Consultation", "duration_minutes": 30, "consultation_mode": "in_person"},
    ).json()["id"]
    doc_id = client.post(
        f"{base}/doctors",
        json={
            "display_name": "Dr. Kavita Iyer",
            "department_ids": [dept_id],
            "speciality_ids": [spec_id],
            "consultation_type_ids": [ct_id],
        },
    ).json()["id"]
    client.put(
        f"{base}/doctors/{doc_id}/working-hours",
        json={
            "items": [
                {"day_of_week": 3, "start_time": "09:00:00", "end_time": "12:00:00", "is_active": True}
            ]
        },
    )

    ctx_mgr = ConversationContextManager()
    orchestrator = AgentOrchestrator(
        context_manager=ctx_mgr,
        intent_classifier=IntentClassifier(),
        rate_limiter=VoiceSessionRateLimiter(),
        clinic_service=clinic_service,
        max_tool_calls_per_turn=15,
    )
    session_id = "voice-clinic-session-1"

    # 1. Reject model-supplied organization_id
    spoof_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-spoof",
        tool_name=AgentToolName.GET_CLINIC_DOCTORS,
        arguments={"organization_id": str(uuid4())},
    )
    assert spoof_res.status == "rejected"

    # 2. Discovery tools succeed
    info_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-info",
        tool_name=AgentToolName.GET_CLINIC_INFORMATION,
        arguments={},
    )
    assert info_res.status == "succeeded"
    assert info_res.output["clinic_name"] == "Apex Care Clinic"

    depts_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-depts",
        tool_name=AgentToolName.GET_CLINIC_DEPARTMENTS,
        arguments={},
    )
    assert depts_res.status == "succeeded"
    assert depts_res.output["total_count"] == 1

    # 3. Check availability for Wednesday 2026-11-25
    avail_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-avail",
        tool_name=AgentToolName.CHECK_CLINIC_AVAILABILITY,
        arguments={"consultation_type_id": ct_id, "target_date": "2026-11-25"},
    )
    assert avail_res.status == "succeeded", avail_res.output
    assert avail_res.output["total_slots"] == 6

    # 4. Book appointment via AI tool
    book_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-book",
        tool_name=AgentToolName.CREATE_CLINIC_APPOINTMENT,
        arguments={
            "doctor_id": doc_id,
            "consultation_type_id": ct_id,
            "patient_display_name": "Ananya Das",
            "patient_contact": "+919811112222",
            "starts_at": "2026-11-25T09:00:00+05:30",
        },
    )
    assert book_res.status == "succeeded"
    assert book_res.output["booked"] is True
    booking_ref = book_res.output["booking_reference"]
    assert booking_ref.startswith("CLN-")

    # 5. Patient verification failure on reschedule must fail without leaking details
    bad_resched = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-bad-resched",
        tool_name=AgentToolName.RESCHEDULE_CLINIC_APPOINTMENT,
        arguments={
            "booking_reference": booking_ref,
            "patient_contact_verification": "0000",
            "new_starts_at": "2026-11-25T10:00:00+05:30",
        },
    )
    assert bad_resched.status == "succeeded"
    assert bad_resched.output["rescheduled"] is False

    # 6. Verified reschedule succeeds
    good_resched = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-good-resched",
        tool_name=AgentToolName.RESCHEDULE_CLINIC_APPOINTMENT,
        arguments={
            "booking_reference": booking_ref,
            "patient_contact_verification": "2222",
            "new_starts_at": "2026-11-25T10:00:00+05:30",
        },
    )
    assert good_resched.output["rescheduled"] is True

    # 7. Verified cancel succeeds
    good_cancel = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-cancel",
        tool_name=AgentToolName.CANCEL_CLINIC_APPOINTMENT,
        arguments={
            "booking_reference": booking_ref,
            "patient_contact_verification": "2222",
            "reason": "Schedule changed",
        },
    )
    assert good_cancel.output["cancelled"] is True

    # 8. Clinic escalation tool triggers escalation_triggered
    esc_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id=session_id,
        call_id="call-esc",
        tool_name=AgentToolName.REQUEST_CLINIC_HUMAN_ESCALATION,
        arguments={
            "reason": "Caller asked about medication side effects",
            "summary": "Patient asked clinical question; transferred to nurse.",
            "urgency": "clinical_staff",
        },
    )
    assert esc_res.status == "succeeded"
    assert esc_res.escalation_triggered is True
    assert esc_res.escalation_reference.startswith("ESC-")

    # 9. Emergency intent must immediately trigger emergency guidance and NOT create booking
    emerg_turn = await orchestrator.process_turn(
        bundle=bundle,
        session_id="voice-clinic-emerg",
        user_input="I have severe chest pain and cannot breathe, book me an appointment!",
    )
    assert emerg_turn.intent_result.intent == AgentIntent.EMERGENCY_INTENT
    assert emerg_turn.emergency_guidance_issued is True
    assert emerg_turn.booking_created is False
    assert SafetyFlag.MEDICAL_EMERGENCY_DETECTED in emerg_turn.intent_result.safety_flags
