"""Stage 6 Remediation Verification Tests (P0–P2).

Covers:
- P0: Production repository selection, fail-closed startup/repo guard, SupabaseRestClinicRepository
      persistence across fresh service instances, 23P01 overlap conflict, 23505 idempotency replay.
- P1: Real IANA ZoneInfo loading (tzdata), DST transitions (EST -05:00 vs EDT -04:00), UTC storage.
- P2: Realtime tool filtering per industry (Salon vs Clinic) and cross-industry tool rejection.
- P2: Agent prompt consistency (no contradictory Stage 4 no-booking rule for Salon/Clinic).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4
import httpx
import pytest
from fastapi import HTTPException
from zoneinfo import ZoneInfo

from app.agents.context import ConversationContextManager
from app.agents.industries import get_industry_agent
from app.agents.instructions import (
    build_realtime_tool_definitions,
    build_stage4_agent_instructions,
)
from app.agents.intent import IntentClassifier
from app.agents.orchestrator import AgentOrchestrator
from app.agents.schemas import AgentToolName
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.main import create_app
from app.modules.clinics.repository import ClinicConflictError, InMemoryClinicRepository
from app.modules.clinics.schemas import (
    ClinicAppointmentCancelRequest,
    ClinicAppointmentCreateRequest,
    ClinicAppointmentRescheduleRequest,
    ClinicAppointmentSource,
    ClinicConsultationTypeCreateRequest,
    ClinicDoctorCreateRequest,
    ConsultationMode,
    DoctorWorkingHoursBulkRequest,
    DoctorWorkingHoursItem,
)
from app.modules.clinics.service import (
    ClinicWorkflowService,
    get_clinic_repository,
)
from app.modules.clinics.supabase_repository import (
    SupabaseRestClinicRepository,
    set_current_clinic_actor,
)
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    AssistantSettingsUpdateRequest,
    BusinessHoursUpdateRequest,
    BusinessLanguagesUpdateRequest,
    BusinessProfileUpdateRequest,
    EscalationSettingsUpdateRequest,
    LanguageCode,
    WeekdayHoursItem,
)
from app.modules.onboarding.service import OnboardingService
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationIndustry,
)
from app.modules.voice.rate_limit import VoiceSessionRateLimiter


def _make_user(email: str = "owner@clinic.example") -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        email=email,
        issuer="https://test.supabase.co/auth/v1",
        audience="authenticated",
        raw_token="test.user.jwt",
    )


async def _build_bundle(industry: OrganizationIndustry, tz: str = "America/New_York"):
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    owner = _make_user()
    org = await org_repo.create_organization(
        owner, CreateOrganizationRequest(name=f"Test {industry.value}", industry=industry)
    )
    biz_id = await onboarding_repo.get_or_create_primary_business_id(owner, org.id)
    await onboarding_repo.upsert_business_profile(
        owner,
        org.id,
        biz_id,
        BusinessProfileUpdateRequest(
            display_name=f"Test {industry.value.title()}",
            timezone=tz,
        ),
    )
    schedule = [
        WeekdayHoursItem(
            weekday=wd, is_closed=False, opens_at="08:00", closes_at="20:00", is_overnight=False
        )
        for wd in range(7)
    ]
    await onboarding_repo.upsert_business_hours(
        owner, org.id, biz_id, BusinessHoursUpdateRequest(timezone=tz, schedule=schedule)
    )
    await onboarding_repo.upsert_business_languages(
        owner,
        org.id,
        biz_id,
        BusinessLanguagesUpdateRequest(
            primary_language=LanguageCode.ENGLISH,
            supported_languages=[LanguageCode.ENGLISH, LanguageCode.HINDI],
        ),
    )
    await onboarding_repo.upsert_assistant_settings(
        owner,
        org.id,
        biz_id,
        AssistantSettingsUpdateRequest(
            assistant_name="Asha",
            greeting="Hello, welcome!",
            personality=AssistantPersonality.WARM,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=True,
        ),
    )
    await onboarding_repo.upsert_escalation_settings(
        owner,
        org.id,
        biz_id,
        EscalationSettingsUpdateRequest(
            enabled=True, contact_name="Desk", contact_phone="+15550009999"
        ),
    )
    bundle = await OnboardingService(repository=onboarding_repo).get_onboarding_bundle(owner, org.id)
    return org_repo, onboarding_repo, owner, org.id, biz_id, bundle


# ============================================================================
# P0: Repository Selection & Fail-Closed Production Guard
# ============================================================================


def test_production_selects_supabase_repository_and_fails_closed_without_config(monkeypatch):
    prod_live = Settings(
        _env_file=None,
        SVARIO_ENV="production",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="real-anon-key-value",
    )
    repo = get_clinic_repository(settings=prod_live)
    assert isinstance(repo, SupabaseRestClinicRepository)

    prod_missing = Settings(
        _env_file=None,
        SVARIO_ENV="production",
        SUPABASE_URL=None,
        SUPABASE_ANON_KEY=None,
    )
    with pytest.raises(RuntimeError, match="in-memory clinic repository fallback is forbidden"):
        get_clinic_repository(settings=prod_missing)

    # Startup validation in create_app() must also fail closed in production without Supabase
    monkeypatch.setattr("app.main.get_settings", lambda: prod_missing)
    with pytest.raises(RuntimeError, match="Startup aborted: SVARIO_ENV=production"):
        create_app()

    # Non-production without Supabase explicitly uses InMemoryClinicRepository
    dev_local = Settings(
        _env_file=None,
        SVARIO_ENV="development",
        SUPABASE_URL=None,
        SUPABASE_ANON_KEY=None,
    )
    assert isinstance(get_clinic_repository(settings=dev_local), InMemoryClinicRepository)


@pytest.mark.anyio
async def test_supabase_rest_clinic_repository_persistence_and_constraints(monkeypatch):
    """Verify SupabaseRestClinicRepository persists across fresh repo instances and maps 23P01/23505."""
    store: Dict[str, Dict[str, Any]] = {}
    forwarded_auth_headers: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        forwarded_auth_headers.append(request.headers.get("Authorization", ""))
        path = request.url.path
        if path.endswith("/rest/v1/clinic_appointments"):
            if request.method == "POST":
                body = request.read().decode("utf-8")
                import json

                row = json.loads(body)
                # Simulate PostgreSQL uq_clinic_appointments_business_idempotency (23505)
                if row.get("idempotency_key"):
                    for existing in store.values():
                        if existing.get("idempotency_key") == row["idempotency_key"]:
                            return httpx.Response(
                                409,
                                json={
                                    "code": "23505",
                                    "message": "duplicate key value violates unique constraint uq_clinic_appointments_business_idempotency",
                                },
                            )
                # Simulate PostgreSQL excl_clinic_appointments_no_doctor_overlap (23P01)
                new_s = datetime.fromisoformat(row["starts_at"])
                new_e = datetime.fromisoformat(row["ends_at"])
                for existing in store.values():
                    if existing["doctor_id"] == row["doctor_id"] and existing["status"] in {
                        "confirmed",
                        "rescheduled",
                    }:
                        ex_s = datetime.fromisoformat(existing["starts_at"])
                        ex_e = datetime.fromisoformat(existing["ends_at"])
                        if ex_s < new_e and new_s < ex_e:
                            return httpx.Response(
                                409,
                                json={
                                    "code": "23P01",
                                    "message": "conflicting key value violates exclusion constraint excl_clinic_appointments_no_doctor_overlap",
                                },
                            )
                now = datetime.now(timezone.utc).isoformat()
                row["created_at"] = now
                row["updated_at"] = now
                row["cancellation_reason"] = None
                row["cancelled_at"] = None
                store[row["id"]] = row
                return httpx.Response(201, json=[row])

            if request.method == "GET":
                params = dict(request.url.params)
                rows = list(store.values())
                if "id" in params:
                    target_id = params["id"].replace("eq.", "")
                    rows = [r for r in rows if r["id"] == target_id]
                if "idempotency_key" in params:
                    target_key = params["idempotency_key"].replace("eq.", "")
                    rows = [r for r in rows if r.get("idempotency_key") == target_key]
                return httpx.Response(200, json=rows)

            if request.method == "PATCH":
                import json

                updates = json.loads(request.read().decode("utf-8"))
                target_id = request.url.params.get("id", "").replace("eq.", "")
                if target_id not in store:
                    return httpx.Response(200, json=[])
                store[target_id].update(updates)
                store[target_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                return httpx.Response(200, json=[store[target_id]])

        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    orig_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: orig_async_client(transport=transport),
    )

    settings = Settings(
        _env_file=None,
        SVARIO_ENV="production",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_ANON_KEY="real-anon-key",
    )
    actor = _make_user()
    set_current_clinic_actor(actor)

    repo1 = SupabaseRestClinicRepository(settings=settings)
    org_id, biz_id, doc_id, ct_id = uuid4(), uuid4(), uuid4(), uuid4()
    start_dt = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 12, 1, 9, 30, tzinfo=timezone.utc)

    created = await repo1.create_appointment_atomic(
        organization_id=org_id,
        business_id=biz_id,
        payload=ClinicAppointmentCreateRequest(
            doctor_id=doc_id,
            consultation_type_id=ct_id,
            patient_display_name="Persistent Patient",
            patient_contact="+15551234567",
            starts_at=start_dt,
            idempotency_key="persist-key-1",
            source=ClinicAppointmentSource.API,
        ),
        ends_at=end_dt,
        tz_name="America/New_York",
        doctor_name="Dr. Persist",
        consultation_type_name="Consult",
    )
    assert created.status.value == "confirmed"
    assert forwarded_auth_headers[0] == "Bearer test.user.jwt"

    # Read from a brand-new repository instance (simulating restart / fresh worker)
    repo2 = SupabaseRestClinicRepository(settings=settings)
    fetched = await repo2.get_appointment(org_id, biz_id, created.id)
    assert fetched is not None
    assert fetched.id == created.id

    # Duplicate idempotency key replays existing appointment
    replayed = await repo2.create_appointment_atomic(
        organization_id=org_id,
        business_id=biz_id,
        payload=ClinicAppointmentCreateRequest(
            doctor_id=doc_id,
            consultation_type_id=ct_id,
            patient_display_name="Persistent Patient",
            patient_contact="+15551234567",
            starts_at=start_dt,
            idempotency_key="persist-key-1",
            source=ClinicAppointmentSource.API,
        ),
        ends_at=end_dt,
        tz_name="America/New_York",
        doctor_name="Dr. Persist",
        consultation_type_name="Consult",
    )
    assert replayed.id == created.id

    # Overlapping slot raises ClinicConflictError (mapped from PG 23P01)
    with pytest.raises(ClinicConflictError):
        await repo2.create_appointment_atomic(
            organization_id=org_id,
            business_id=biz_id,
            payload=ClinicAppointmentCreateRequest(
                doctor_id=doc_id,
                consultation_type_id=ct_id,
                patient_display_name="Overlap Patient",
                patient_contact="+15559876543",
                starts_at=datetime(2026, 12, 1, 9, 15, tzinfo=timezone.utc),
                idempotency_key="persist-key-2",
                source=ClinicAppointmentSource.API,
            ),
            ends_at=datetime(2026, 12, 1, 9, 45, tzinfo=timezone.utc),
            tz_name="America/New_York",
            doctor_name="Dr. Persist",
            consultation_type_name="Consult",
        )

    # Cancel persists across fresh instance
    cancelled = await repo2.cancel_appointment_atomic(
        organization_id=org_id,
        business_id=biz_id,
        appointment_id=created.id,
        reason="Verified cancel",
    )
    assert cancelled.status.value == "cancelled"
    repo3 = SupabaseRestClinicRepository(settings=settings)
    fetched_cancelled = await repo3.get_appointment(org_id, biz_id, created.id)
    assert fetched_cancelled is not None
    assert fetched_cancelled.status.value == "cancelled"


# ============================================================================
# P1: IANA Timezone & DST Reliability
# ============================================================================


@pytest.mark.anyio
async def test_iana_timezone_and_dst_transitions():
    # Verify real tzdata-backed IANA ZoneInfo loads without error
    ny = ZoneInfo("America/New_York")
    kolkata = ZoneInfo("Asia/Kolkata")
    assert datetime(2026, 1, 15, 9, 0, tzinfo=ny).utcoffset().total_seconds() == -5 * 3600  # EST
    assert datetime(2026, 7, 15, 9, 0, tzinfo=ny).utcoffset().total_seconds() == -4 * 3600  # EDT
    assert datetime(2026, 7, 15, 9, 0, tzinfo=kolkata).utcoffset().total_seconds() == 5.5 * 3600

    # Verify ClinicWorkflowService availability respects DST in America/New_York
    org_repo, onboarding_repo, owner, org_id, biz_id, _ = await _build_bundle(
        OrganizationIndustry.CLINIC, tz="America/New_York"
    )
    svc = ClinicWorkflowService(
        clinic_repo=InMemoryClinicRepository(),
        org_repo=org_repo,
        onboarding_repo=onboarding_repo,
    )
    ct = await svc.create_consultation_type(
        owner,
        org_id,
        biz_id,
        ClinicConsultationTypeCreateRequest(
            name="DST Consult", duration_minutes=30, consultation_mode=ConsultationMode.IN_PERSON
        ),
    )
    doc = await svc.create_doctor(
        owner,
        org_id,
        biz_id,
        ClinicDoctorCreateRequest(display_name="Dr. DST", consultation_type_ids=[ct.id]),
    )
    # Configure Thursday (weekday 4) & Wednesday (weekday 3) 09:00-10:00
    await svc.upsert_doctor_working_hours(
        owner,
        org_id,
        biz_id,
        doc.id,
        DoctorWorkingHoursBulkRequest(
            items=[
                DoctorWorkingHoursItem(
                    day_of_week=4, start_time=time(9, 0), end_time=time(10, 0), is_active=True
                ),
                DoctorWorkingHoursItem(
                    day_of_week=3, start_time=time(9, 0), end_time=time(10, 0), is_active=True
                ),
            ]
        ),
    )

    winter_avail = await svc.get_availability(
        owner, org_id, biz_id, consultation_type_id=ct.id, target_date=date(2026, 1, 15)  # Thu EST
    )
    summer_avail = await svc.get_availability(
        owner, org_id, biz_id, consultation_type_id=ct.id, target_date=date(2026, 7, 15)  # Wed EDT
    )
    assert len(winter_avail.slots) == 2
    assert len(summer_avail.slots) == 2
    assert winter_avail.slots[0].starts_at.isoformat().endswith("-05:00")
    assert summer_avail.slots[0].starts_at.isoformat().endswith("-04:00")

    # Simultaneous reschedule concurrency test
    a1 = await svc.create_appointment(
        owner,
        org_id,
        biz_id,
        ClinicAppointmentCreateRequest(
            doctor_id=doc.id,
            consultation_type_id=ct.id,
            patient_display_name="Patient One",
            patient_contact="+15551110001",
            starts_at=winter_avail.slots[0].starts_at,
        ),
    )
    a2 = await svc.create_appointment(
        owner,
        org_id,
        biz_id,
        ClinicAppointmentCreateRequest(
            doctor_id=doc.id,
            consultation_type_id=ct.id,
            patient_display_name="Patient Two",
            patient_contact="+15551110002",
            starts_at=winter_avail.slots[1].starts_at,
        ),
    )
    # Rescheduling a1 & a2 simultaneously onto summer slot 0 -> exactly 1 succeeds, 1 fails with 409
    res = await asyncio.gather(
        svc.reschedule_appointment(
            owner,
            org_id,
            biz_id,
            a1.id,
            ClinicAppointmentRescheduleRequest(new_starts_at=summer_avail.slots[0].starts_at),
        ),
        svc.reschedule_appointment(
            owner,
            org_id,
            biz_id,
            a2.id,
            ClinicAppointmentRescheduleRequest(new_starts_at=summer_avail.slots[0].starts_at),
        ),
        return_exceptions=True,
    )
    ok = [r for r in res if not isinstance(r, Exception)]
    errs = [r for r in res if isinstance(r, HTTPException) and r.status_code == 409]
    assert len(ok) == 1
    assert len(errs) == 1


# ============================================================================
# P2: Realtime Tool Filtering & Agent Prompt Consistency
# ============================================================================


@pytest.mark.anyio
async def test_realtime_tool_filtering_and_prompt_consistency():
    salon_agent = get_industry_agent(OrganizationIndustry.SALON)
    clinic_agent = get_industry_agent(OrganizationIndustry.CLINIC)

    salon_tools = build_realtime_tool_definitions(allowed_tools=salon_agent.allowed_tools)
    clinic_tools = build_realtime_tool_definitions(allowed_tools=clinic_agent.allowed_tools)

    salon_names = {t["name"] for t in salon_tools}
    clinic_names = {t["name"] for t in clinic_tools}

    assert "create_salon_appointment" in salon_names
    assert "create_clinic_appointment" not in salon_names
    assert not any("clinic" in n for n in salon_names)

    assert "create_clinic_appointment" in clinic_names
    assert "create_salon_appointment" not in clinic_names
    assert not any("salon" in n for n in clinic_names)

    # Disallowed cross-industry tool call rejected by orchestrator
    _, _, _, _, _, clinic_bundle = await _build_bundle(OrganizationIndustry.CLINIC)
    _, _, _, _, _, salon_bundle = await _build_bundle(OrganizationIndustry.SALON)
    _, _, _, _, _, hospital_bundle = await _build_bundle(OrganizationIndustry.HOSPITAL)

    orchestrator = AgentOrchestrator(
        context_manager=ConversationContextManager(),
        intent_classifier=IntentClassifier(),
        rate_limiter=VoiceSessionRateLimiter(),
    )
    cross_res = await orchestrator.execute_realtime_tool(
        bundle=clinic_bundle,
        session_id="cross-industry-test",
        call_id="call-x",
        tool_name=AgentToolName.GET_SALON_SERVICES,
        arguments={},
    )
    assert cross_res.status == "rejected"
    assert cross_res.output["error"] == "tool_not_permitted"

    # Prompt consistency checks
    clinic_prompt = build_stage4_agent_instructions(clinic_bundle)
    salon_prompt = build_stage4_agent_instructions(salon_bundle)
    hospital_prompt = build_stage4_agent_instructions(hospital_bundle)

    assert "does NOT create or modify appointments in Stage 4" not in clinic_prompt
    assert "does NOT create or modify appointments in Stage 4" not in salon_prompt
    assert "Backend-Confirmed Scheduling Boundary" in clinic_prompt
    assert "Backend-Confirmed Scheduling Boundary" in salon_prompt
    assert "NEVER provide medical diagnosis" in clinic_prompt
    assert "Pre-Booking Industry Boundary" in hospital_prompt
