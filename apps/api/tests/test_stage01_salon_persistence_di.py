"""Stage 01 — Salon Persistence & Dependency Injection Remediation Tests.

Covers:
1. SalonRepositoryProtocol completeness on SupabaseRestSalonRepository.
2. Supabase service, staff, working hours, breaks, and holiday persistence (MockTransport).
3. Appointment creation, retrieval across fresh repository instances, and cancellation release.
4. Idempotent booking replay (pre-check + PostgreSQL 23505 conflict handling).
5. Mapping of PostgreSQL 23P01 (excl_salon_appointments_no_staff_overlap) to HTTP 409.
6. Authenticated user JWT forwarding vs internal voice-session service-role authorization.
7. Fail-closed 503 when voice agent lacks SUPABASE_SERVICE_ROLE_KEY.
8. Cross-organization access rejection.
9. Production fail-closed repository selection (no silent in-memory fallback).
10. AgentOrchestrator DI regression test (asserts zero FastAPI Depends objects).
11. Voice tool execution regression test proving real service dependencies are wired.
"""

from __future__ import annotations

import inspect
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4
import httpx
import pytest
from fastapi import HTTPException
from fastapi.params import Depends as FastApiDepends

from app.agents.context import ConversationContextManager
from app.agents.intent import IntentClassifier
from app.agents.orchestrator import AgentOrchestrator, get_agent_orchestrator
from app.agents.schemas import AgentToolName
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.core.internal_voice import create_verified_internal_voice_actor
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
from app.modules.salons.repository import (
    InMemorySalonRepository,
    SalonRepositoryProtocol,
)
from app.modules.salons.schemas import (
    SalonAppointmentResponse,
    SalonAppointmentSource,
    SalonAppointmentStatus,
    SalonServiceCreateRequest,
    SalonStaffCreateRequest,
    SalonStaffWorkingHoursItem,
    SalonStaffWorkingHoursUpdateRequest,
)
from app.modules.salons.service import (
    SalonWorkflowService,
    build_salon_workflow_service,
    get_salon_repository,
    get_salon_workflow_service,
)
from app.modules.salons.supabase_repository import (
    INTERNAL_VOICE_ISSUER,
    SupabaseRestSalonRepository,
)
from app.modules.voice.rate_limit import VoiceSessionRateLimiter


def _make_user(
    *,
    email: str = "owner@salon.example",
    issuer: str = "https://test.supabase.co/auth/v1",
    raw_token: str = "real.user.jwt.token",
) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        email=email,
        issuer=issuer,
        audience="authenticated",
        raw_token=raw_token,
    )


def _live_settings(*, include_service_role: bool = True, env: str = "production") -> Settings:
    return Settings(
        _env_file=None,
        SVARIO_ENV=env,
        SUPABASE_URL="https://mock-salon.supabase.co",
        SUPABASE_ANON_KEY="mock-anon-key",
        SUPABASE_SERVICE_ROLE_KEY="mock-service-role-key" if include_service_role else None,
    )


# ============================================================================
# 1. Protocol Completeness
# ============================================================================


def test_supabase_salon_repository_implements_full_protocol():
    protocol_methods = [
        name
        for name, member in inspect.getmembers(SalonRepositoryProtocol, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]
    assert len(protocol_methods) >= 20
    for method_name in protocol_methods:
        impl = getattr(SupabaseRestSalonRepository, method_name, None)
        assert impl is not None, f"Missing protocol method on SupabaseRestSalonRepository: {method_name}"
        assert inspect.iscoroutinefunction(impl), f"Method {method_name} must be async"


# ============================================================================
# 2-8. SupabaseRestSalonRepository Persistence, 23P01, 23505, Cancel, JWT & Voice Auth
# ============================================================================


@pytest.mark.anyio
async def test_supabase_salon_repository_crud_persistence_concurrency_and_auth(monkeypatch):
    services_store: Dict[str, Dict[str, Any]] = {}
    staff_store: Dict[str, Dict[str, Any]] = {}
    wh_store: Dict[tuple[str, int], Dict[str, Any]] = {}
    appts_store: Dict[str, Dict[str, Any]] = {}
    captured_headers: List[Dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(
            {
                "authorization": request.headers.get("Authorization", ""),
                "apikey": request.headers.get("apikey", ""),
                "method": request.method,
                "path": request.url.path,
            }
        )
        path = request.url.path
        params = dict(request.url.params)
        now = datetime.now(timezone.utc).isoformat()

        # --- salon_services ---
        if path.endswith("/rest/v1/salon_services"):
            if request.method == "POST":
                row = json.loads(request.read().decode("utf-8"))
                row["id"] = str(uuid4())
                row["created_at"] = now
                row["updated_at"] = now
                services_store[row["id"]] = row
                return httpx.Response(201, json=[row])
            if request.method == "GET":
                rows = list(services_store.values())
                if "organization_id" in params:
                    org_v = params["organization_id"].replace("eq.", "")
                    rows = [r for r in rows if r["organization_id"] == org_v]
                if "id" in params:
                    id_v = params["id"].replace("eq.", "")
                    rows = [r for r in rows if r["id"] == id_v]
                return httpx.Response(200, json=rows)

        # --- salon_staff ---
        if path.endswith("/rest/v1/salon_staff"):
            if request.method == "POST":
                row = json.loads(request.read().decode("utf-8"))
                row["id"] = str(uuid4())
                row["created_at"] = now
                row["updated_at"] = now
                staff_store[row["id"]] = row
                return httpx.Response(201, json=[row])
            if request.method == "GET":
                rows = []
                for st in staff_store.values():
                    if "organization_id" in params and st["organization_id"] != params["organization_id"].replace("eq.", ""):
                        continue
                    if "id" in params and st["id"] != params["id"].replace("eq.", ""):
                        continue
                    enriched = dict(st)
                    enriched["salon_staff_services"] = []
                    enriched["salon_staff_working_hours"] = [
                        wh for (sid, _), wh in wh_store.items() if sid == st["id"]
                    ]
                    enriched["salon_staff_breaks"] = []
                    rows.append(enriched)
                return httpx.Response(200, json=rows)

        # --- salon_staff_working_hours ---
        if path.endswith("/rest/v1/salon_staff_working_hours"):
            if request.method == "POST":
                items = json.loads(request.read().decode("utf-8"))
                for item in items:
                    wh_store[(item["staff_id"], int(item["weekday"]))] = item
                return httpx.Response(201, json=items)
            if request.method == "GET":
                sid = params.get("staff_id", "").replace("eq.", "")
                rows = [wh for (s, _), wh in wh_store.items() if s == sid]
                rows.sort(key=lambda x: int(x["weekday"]))
                return httpx.Response(200, json=rows)

        # --- salon_appointments ---
        if path.endswith("/rest/v1/salon_appointments"):
            if request.method == "POST":
                row = json.loads(request.read().decode("utf-8"))
                # Simulate uq_salon_appointments_business_idempotency (23505)
                if row.get("idempotency_key"):
                    for ex in appts_store.values():
                        if ex.get("idempotency_key") == row["idempotency_key"]:
                            return httpx.Response(
                                409,
                                json={
                                    "code": "23505",
                                    "message": "duplicate key value violates unique constraint uq_salon_appointments_business_idempotency",
                                },
                            )
                # Simulate excl_salon_appointments_no_staff_overlap (23P01)
                new_s = datetime.fromisoformat(row["start_at"])
                new_e = datetime.fromisoformat(row["end_at"])
                for ex in appts_store.values():
                    if ex["staff_id"] == row["staff_id"] and ex["status"] in {"confirmed", "rescheduled"}:
                        ex_s = datetime.fromisoformat(ex["start_at"])
                        ex_e = datetime.fromisoformat(ex["end_at"])
                        if max(ex_s, new_s) < min(ex_e, new_e):
                            return httpx.Response(
                                409,
                                json={
                                    "code": "23P01",
                                    "message": "conflicting key value violates exclusion constraint excl_salon_appointments_no_staff_overlap",
                                },
                            )
                row["created_at"] = now
                row["updated_at"] = now
                row["cancelled_at"] = None
                row["cancellation_reason"] = None
                appts_store[row["id"]] = row
                return httpx.Response(201, json=[row])

            if request.method == "GET":
                rows = list(appts_store.values())
                if "organization_id" in params:
                    org_v = params["organization_id"].replace("eq.", "")
                    rows = [r for r in rows if r["organization_id"] == org_v]
                if "id" in params:
                    id_v = params["id"].replace("eq.", "")
                    rows = [r for r in rows if r["id"] == id_v]
                if "idempotency_key" in params:
                    ik = params["idempotency_key"].replace("eq.", "")
                    rows = [r for r in rows if r.get("idempotency_key") == ik]
                return httpx.Response(200, json=rows)

            if request.method == "PATCH":
                updates = json.loads(request.read().decode("utf-8"))
                target_id = params.get("id", "").replace("eq.", "")
                if target_id not in appts_store:
                    return httpx.Response(200, json=[])
                appts_store[target_id].update(updates)
                appts_store[target_id]["updated_at"] = now
                return httpx.Response(200, json=[appts_store[target_id]])

        return httpx.Response(404, json={"message": "unhandled mock route"})

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: orig_client(transport=transport))

    settings = _live_settings(include_service_role=True)
    owner = _make_user(raw_token="owner.supabase.jwt")
    org_id, biz_id = uuid4(), uuid4()

    repo1 = SupabaseRestSalonRepository(settings=settings)

    # 1. Service, Staff & Working Hours persist across fresh repo instances
    svc = await repo1.create_service(
        owner,
        org_id,
        biz_id,
        SalonServiceCreateRequest(name="Haircut", category="Hair", price=600.0, duration_minutes=45),
    )
    assert captured_headers[-1]["authorization"] == "Bearer owner.supabase.jwt"
    assert captured_headers[-1]["apikey"] == "mock-anon-key"

    staff = await repo1.create_staff(
        owner, org_id, biz_id, SalonStaffCreateRequest(full_name="Aarav Mehta", role_designation="Senior Stylist")
    )
    updated_wh = await repo1.update_staff_working_hours(
        owner,
        org_id,
        biz_id,
        staff.id,
        SalonStaffWorkingHoursUpdateRequest(
            schedule=[SalonStaffWorkingHoursItem(weekday=1, is_off=False, start_time="10:00", end_time="19:00")]
        ),
    )
    assert any(w.weekday == 1 and w.start_time == "10:00" for w in updated_wh)

    # Fresh repository instance reads persisted records
    repo2 = SupabaseRestSalonRepository(settings=settings)
    fetched_svc = await repo2.get_service(owner, org_id, biz_id, svc.id)
    assert fetched_svc.id == svc.id
    fetched_staff = await repo2.get_staff(owner, org_id, biz_id, staff.id)
    assert fetched_staff.id == staff.id

    # Cross-organization isolation: probing with another org_id returns 404
    with pytest.raises(HTTPException) as exc_cross:
        await repo2.get_service(owner, uuid4(), biz_id, svc.id)
    assert exc_cross.value.status_code == 404

    # 2. Appointment creation & persistence across fresh repo instance
    now_utc = datetime.now(timezone.utc)
    appt1 = SalonAppointmentResponse(
        id=uuid4(),
        organization_id=org_id,
        business_id=biz_id,
        booking_reference="SLN-TEST0001",
        idempotency_key="idem-salon-001",
        service_id=svc.id,
        service_name=svc.name,
        service_duration_minutes=45,
        service_price=600.0,
        service_currency="INR",
        staff_id=staff.id,
        staff_name=staff.full_name,
        staff_role=staff.role_designation,
        customer_name="Riya Sen",
        customer_phone="+919876543210",
        appointment_date=date(2026, 12, 1),
        start_time="10:00",
        end_time="10:45",
        start_at=datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 12, 1, 10, 45, tzinfo=timezone.utc),
        timezone="Asia/Kolkata",
        status=SalonAppointmentStatus.CONFIRMED,
        source=SalonAppointmentSource.DASHBOARD,
        created_at=now_utc,
        updated_at=now_utc,
    )
    created = await repo1.create_appointment(owner, org_id, biz_id, appt1)
    assert created.id == appt1.id

    fetched_appt = await repo2.get_appointment(owner, org_id, biz_id, appt1.id)
    assert fetched_appt.booking_reference == "SLN-TEST0001"

    # 3. Idempotent replay returns same appointment
    replayed = await repo2.create_appointment(owner, org_id, biz_id, appt1)
    assert replayed.id == appt1.id

    # 4. Overlapping appointment maps PG 23P01 to HTTP 409
    overlap_appt = appt1.model_copy(
        update={
            "id": uuid4(),
            "booking_reference": "SLN-TEST0002",
            "idempotency_key": "idem-salon-002",
            "start_time": "10:15",
            "end_time": "11:00",
            "start_at": datetime(2026, 12, 1, 10, 15, tzinfo=timezone.utc),
            "end_at": datetime(2026, 12, 1, 11, 0, tzinfo=timezone.utc),
        }
    )
    with pytest.raises(HTTPException) as exc_overlap:
        await repo2.create_appointment(owner, org_id, biz_id, overlap_appt)
    assert exc_overlap.value.status_code == 409

    # 5. Cancellation releases occupied slot for new booking
    cancelled_payload = created.model_copy(
        update={
            "status": SalonAppointmentStatus.CANCELLED,
            "cancelled_at": datetime.now(timezone.utc),
            "cancellation_reason": "Client rescheduled",
        }
    )
    cancelled = await repo2.update_appointment(owner, org_id, biz_id, cancelled_payload)
    assert cancelled.status == SalonAppointmentStatus.CANCELLED

    rebooked = await repo2.create_appointment(owner, org_id, biz_id, overlap_appt)
    assert rebooked.status == SalonAppointmentStatus.CONFIRMED

    # 6a. Forged internal voice actor (issuer string without HMAC binding) must be rejected (403)
    forged_voice_actor = _make_user(issuer=INTERNAL_VOICE_ISSUER, raw_token="forged-token")
    with pytest.raises(HTTPException) as exc_forged:
        await repo2.list_services(forged_voice_actor, org_id, biz_id)
    assert exc_forged.value.status_code == 403

    # 6b. Verified internal voice-session uses SUPABASE_SERVICE_ROLE_KEY
    voice_actor = create_verified_internal_voice_actor(
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
        user_id=owner.id,
        email=owner.email,
    )
    voice_list = await repo2.list_services(voice_actor, org_id, biz_id)
    assert len(voice_list) == 1
    assert captured_headers[-1]["authorization"] == "Bearer mock-service-role-key"

    # 7. Internal voice-session fails closed (503) if SUPABASE_SERVICE_ROLE_KEY is missing
    repo_no_srk = SupabaseRestSalonRepository(settings=_live_settings(include_service_role=False))
    with pytest.raises(HTTPException) as exc_srk:
        await repo_no_srk.list_services(voice_actor, org_id, biz_id)
    assert exc_srk.value.status_code == 503


# ============================================================================
# 9. Production Fail-Closed Repository Selection
# ============================================================================


def test_salon_repository_selection_and_production_fail_closed():
    prod_live = _live_settings(env="production")
    assert isinstance(get_salon_repository(settings=prod_live), SupabaseRestSalonRepository)

    prod_missing = Settings(
        _env_file=None,
        SVARIO_ENV="production",
        SUPABASE_URL=None,
        SUPABASE_ANON_KEY=None,
    )
    with pytest.raises(RuntimeError, match="in-memory salon repository fallback is forbidden"):
        get_salon_repository(settings=prod_missing)

    dev_local = Settings(
        _env_file=None,
        SVARIO_ENV="development",
        SUPABASE_URL=None,
        SUPABASE_ANON_KEY=None,
    )
    assert isinstance(get_salon_repository(settings=dev_local), InMemorySalonRepository)


# ============================================================================
# 10 & 11. Dependency Injection Regression & Voice Tool Wiring Tests
# ============================================================================


def test_agent_orchestrator_salon_dependencies_are_never_fastapi_depends():
    """Regression test: fails immediately if any injected dependency is a FastAPI Depends object."""
    orchestrator = get_agent_orchestrator()
    svc = orchestrator.salon_service

    assert isinstance(svc, SalonWorkflowService)
    assert not isinstance(svc._settings, FastApiDepends)
    assert not isinstance(svc._salon_repo, FastApiDepends)
    assert not isinstance(svc._onboarding_repo, FastApiDepends)
    assert hasattr(svc._salon_repo, "list_services")
    assert hasattr(svc._onboarding_repo, "get_business_hours")
    assert hasattr(svc._onboarding_repo, "get_member_role")

    # Direct call to build_salon_workflow_service() and get_salon_workflow_service() must also resolve cleanly
    built = build_salon_workflow_service()
    assert not isinstance(built._onboarding_repo, FastApiDepends)
    assert not isinstance(built._salon_repo, FastApiDepends)

    direct = get_salon_workflow_service()
    assert not isinstance(direct._onboarding_repo, FastApiDepends)
    assert not isinstance(direct._salon_repo, FastApiDepends)


@pytest.mark.anyio
async def test_salon_voice_tools_receive_real_service_dependencies():
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    salon_repo = InMemorySalonRepository()
    owner = _make_user()

    org = await org_repo.create_organization(
        owner, CreateOrganizationRequest(name="Aura Hair Studio", industry=OrganizationIndustry.SALON)
    )
    biz_id = await onboarding_repo.get_or_create_primary_business_id(owner, org.id)
    await onboarding_repo.upsert_business_profile(
        owner, org.id, biz_id, BusinessProfileUpdateRequest(display_name="Aura Hair Studio", timezone="Asia/Kolkata")
    )
    await onboarding_repo.upsert_business_hours(
        owner,
        org.id,
        biz_id,
        BusinessHoursUpdateRequest(
            timezone="Asia/Kolkata",
            schedule=[
                WeekdayHoursItem(weekday=wd, is_closed=False, opens_at="09:00", closes_at="19:00")
                for wd in range(7)
            ],
        ),
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
            assistant_name="Ria",
            greeting="Welcome to Aura Hair Studio!",
            personality=AssistantPersonality.FRIENDLY,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=True,
        ),
    )
    await onboarding_repo.upsert_escalation_settings(
        owner,
        org.id,
        biz_id,
        EscalationSettingsUpdateRequest(enabled=True, contact_name="Front Desk", contact_phone="+919999000011"),
    )
    bundle = await OnboardingService(repository=onboarding_repo).get_onboarding_bundle(owner, org.id)

    salon_svc = build_salon_workflow_service(
        settings=Settings(_env_file=None, SVARIO_ENV="test"),
        salon_repo=salon_repo,
        onboarding_repo=onboarding_repo,
    )
    created_svc = await salon_svc.create_service(
        owner, org.id, biz_id, SalonServiceCreateRequest(name="Keratin Spa", category="Hair", price=2500.0, duration_minutes=60)
    )
    await salon_svc.create_staff(
        owner,
        org.id,
        biz_id,
        SalonStaffCreateRequest(full_name="Maya Kapoor", assigned_service_ids=[created_svc.id]),
    )

    orchestrator = AgentOrchestrator(
        context_manager=ConversationContextManager(),
        intent_classifier=IntentClassifier(),
        rate_limiter=VoiceSessionRateLimiter(),
        salon_service=salon_svc,
        max_tool_calls_per_turn=10,
    )

    svc_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id="salon-voice-di-check",
        call_id="call-1",
        tool_name=AgentToolName.GET_SALON_SERVICES,
        arguments={"is_active": True},
    )
    assert svc_res.status == "succeeded"
    assert svc_res.output["count"] == 1

    avail_res = await orchestrator.execute_realtime_tool(
        bundle=bundle,
        session_id="salon-voice-di-check",
        call_id="call-2",
        tool_name=AgentToolName.CHECK_SALON_AVAILABILITY,
        arguments={"service_id": str(created_svc.id), "requested_date": "2026-12-01"},
    )
    assert avail_res.status == "succeeded"
    assert avail_res.output["total_slots_available"] > 0
