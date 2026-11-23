"""Stage 01B — Integration Security & Salon Repository Hardening Tests.

All HTTP tests use deterministic httpx.MockTransport (explicitly NOT live Supabase).
Covers:
1. SupabaseRestOnboardingRepository internal voice auth, JWT forwarding, 403/503 fail-closed.
2. SalonWorkflowService industry validation (salon vs clinic, non-member, wrong-business voice).
3. assign_staff_services pre-validation preventing cross-tenant destructive DELETE.
4. Empty update_service payload short-circuiting without PATCH.
5. _salon_service_cache safe SHA-256 fingerprint invalidation on credential rotation.
6. Concurrent 23505 idempotency race replay.
7. Breaks, holidays, update/delete staff & service, bounded pagination, and model-supplied org_id rejection.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4
import httpx
import pytest
from fastapi import HTTPException

from app.agents.context import ConversationContextManager
from app.agents.intent import IntentClassifier
from app.agents.orchestrator import AgentOrchestrator
from app.agents.schemas import AgentToolName
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.core.internal_voice import (
    INTERNAL_VOICE_ISSUER,
    create_verified_internal_voice_actor,
)
from app.modules.onboarding.repository import (
    InMemoryOnboardingRepository,
    SupabaseRestOnboardingRepository,
)
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
from app.modules.salons.repository import InMemorySalonRepository
from app.modules.salons.schemas import (
    SalonAppointmentResponse,
    SalonAppointmentSource,
    SalonAppointmentStatus,
    SalonHolidayCreateRequest,
    SalonServiceCreateRequest,
    SalonServiceUpdateRequest,
    SalonStaffBreakCreateRequest,
    SalonStaffUpdateRequest,
)
from app.modules.salons.service import (
    SalonWorkflowService,
    _salon_service_cache,
    build_salon_workflow_service,
    clear_salon_service_cache,
)
from app.modules.salons.supabase_repository import SupabaseRestSalonRepository
from app.modules.voice.rate_limit import VoiceSessionRateLimiter


def _make_user(email: str = "owner@salon.example", raw_token: str = "user.jwt.abc") -> AuthenticatedUser:
    return AuthenticatedUser(
        id=uuid4(),
        email=email,
        issuer="https://test.supabase.co/auth/v1",
        audience="authenticated",
        raw_token=raw_token,
    )


def _live_settings(*, srk: str | None = "srk-v1", url: str = "https://salon.supabase.co") -> Settings:
    return Settings(
        _env_file=None,
        SVARIO_ENV="production",
        SUPABASE_URL=url,
        SUPABASE_ANON_KEY="anon-v1",
        SUPABASE_SERVICE_ROLE_KEY=srk,
    )


# ============================================================================
# 1. SupabaseRestOnboardingRepository Internal Voice Auth & JWT Forwarding
# ============================================================================


@pytest.mark.anyio
async def test_onboarding_repo_internal_voice_auth_and_jwt_forwarding(monkeypatch):
    seen_headers: List[Dict[str, str]] = []
    now = datetime.now(timezone.utc).isoformat()
    org_id, biz_id = uuid4(), uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(
            {
                "auth": request.headers.get("Authorization", ""),
                "apikey": request.headers.get("apikey", ""),
                "path": request.url.path,
            }
        )
        if request.url.path.endswith("/rest/v1/business_profiles"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(uuid4()),
                        "organization_id": str(org_id),
                        "business_id": str(biz_id),
                        "display_name": "Glow Salon",
                        "timezone": "Asia/Kolkata",
                        "created_at": now,
                        "updated_at": now,
                    }
                ],
            )
        if request.url.path.endswith("/rest/v1/business_hours"):
            return httpx.Response(
                200,
                json=[
                    {
                        "weekday": wd,
                        "is_closed": False,
                        "opens_at": "09:00:00",
                        "closes_at": "19:00:00",
                        "is_overnight": False,
                    }
                    for wd in range(7)
                ],
            )
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: orig(transport=transport))

    repo = SupabaseRestOnboardingRepository(settings=_live_settings(srk="srk-secret-1"))

    # A. Normal authenticated user JWT forwarding unchanged
    user = _make_user(raw_token="real.user.jwt")
    hours = await repo.get_business_hours(user, org_id, biz_id)
    assert hours.timezone == "Asia/Kolkata"
    assert seen_headers[-1]["auth"] == "Bearer real.user.jwt"
    assert seen_headers[-1]["apikey"] == "anon-v1"

    # B. Verified internal voice actor succeeds on get_business_hours using service-role key
    voice_actor = create_verified_internal_voice_actor(
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
        user_id=user.id,
    )
    assert voice_actor.raw_token == ""  # Never a fake JWT
    hours_voice = await repo.get_business_hours(voice_actor, org_id, biz_id)
    assert len(hours_voice.schedule) == 7
    assert seen_headers[-1]["auth"] == "Bearer srk-secret-1"

    # C. Internal voice actor bound to a DIFFERENT business is rejected (403)
    with pytest.raises(HTTPException) as exc_wrong_biz:
        await repo.get_business_hours(voice_actor, org_id, uuid4())
    assert exc_wrong_biz.value.status_code == 403

    # D. Forged internal voice actor (no HMAC signature) is rejected (403)
    forged = AuthenticatedUser(
        id=user.id,
        email="x@y.z",
        issuer=INTERNAL_VOICE_ISSUER,
        audience="authenticated",
        raw_token="session-voice-agent-token",
    )
    with pytest.raises(HTTPException) as exc_forged:
        await repo.get_business_hours(forged, org_id, biz_id)
    assert exc_forged.value.status_code == 403

    # E. Internal voice actor is blocked from non-whitelisted onboarding writes (403)
    with pytest.raises(HTTPException) as exc_write:
        await repo.upsert_business_hours(
            voice_actor,
            org_id,
            biz_id,
            BusinessHoursUpdateRequest(
                timezone="UTC",
                schedule=[WeekdayHoursItem(weekday=wd, is_closed=True) for wd in range(7)],
            ),
        )
    assert exc_write.value.status_code == 403

    # F. Missing SUPABASE_SERVICE_ROLE_KEY fails closed with 503
    repo_no_srk = SupabaseRestOnboardingRepository(settings=_live_settings(srk=None))
    with pytest.raises(HTTPException) as exc_503:
        await repo_no_srk.get_business_hours(voice_actor, org_id, biz_id)
    assert exc_503.value.status_code == 503


# ============================================================================
# 2. Salon Industry Validation & Internal Voice Binding
# ============================================================================


@pytest.mark.anyio
async def test_salon_service_enforces_industry_membership_and_voice_binding():
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    salon_repo = InMemorySalonRepository()
    owner = _make_user("owner@svario.example")
    outsider = _make_user("outsider@svario.example")

    salon_org = await org_repo.create_organization(
        owner, CreateOrganizationRequest(name="Velvet Salon", industry=OrganizationIndustry.SALON)
    )
    salon_biz = await onboarding_repo.get_or_create_primary_business_id(owner, salon_org.id)

    clinic_org = await org_repo.create_organization(
        owner, CreateOrganizationRequest(name="Care Clinic", industry=OrganizationIndustry.CLINIC)
    )
    clinic_biz = await onboarding_repo.get_or_create_primary_business_id(owner, clinic_org.id)

    svc = SalonWorkflowService(
        settings=Settings(_env_file=None, SVARIO_ENV="test"),
        salon_repo=salon_repo,
        onboarding_repo=onboarding_repo,
    )

    # 1. Valid salon org succeeds
    created = await svc.create_service(
        owner,
        salon_org.id,
        salon_biz,
        SalonServiceCreateRequest(name="Blowout", category="Hair", price=700.0, duration_minutes=30),
    )
    assert created.name == "Blowout"

    # 2. Clinic org attempting salon operation -> 400
    with pytest.raises(HTTPException) as exc_clinic:
        await svc.list_services(owner, clinic_org.id, clinic_biz)
    assert exc_clinic.value.status_code == 400

    # 3. Non-member user -> 403
    with pytest.raises(HTTPException) as exc_outsider:
        await svc.list_services(outsider, salon_org.id, salon_biz)
    assert exc_outsider.value.status_code == 403

    # 4. Internal voice actor bound to clinic org -> 403 on salon ops
    clinic_voice = create_verified_internal_voice_actor(
        organization_id=clinic_org.id,
        business_id=clinic_biz,
        industry=OrganizationIndustry.CLINIC,
        user_id=owner.id,
    )
    with pytest.raises(HTTPException) as exc_voice_ind:
        await svc.list_services(clinic_voice, clinic_org.id, clinic_biz)
    assert exc_voice_ind.value.status_code == 403

    # 5. Internal voice actor bound to wrong salon business -> 403
    salon_voice = create_verified_internal_voice_actor(
        organization_id=salon_org.id,
        business_id=salon_biz,
        industry=OrganizationIndustry.SALON,
        user_id=owner.id,
    )
    with pytest.raises(HTTPException) as exc_wrong_biz:
        await svc.list_services(salon_voice, salon_org.id, uuid4())
    assert exc_wrong_biz.value.status_code == 403

    # 6. Valid salon voice actor can read services but cannot create services (403)
    svcs = await svc.list_services(salon_voice, salon_org.id, salon_biz)
    assert len(svcs) == 1
    with pytest.raises(HTTPException) as exc_voice_admin:
        await svc.create_service(
            salon_voice,
            salon_org.id,
            salon_biz,
            SalonServiceCreateRequest(name="Hack", category="Hair", price=100.0, duration_minutes=30),
        )
    assert exc_voice_admin.value.status_code == 403


# ============================================================================
# 3-7. Repository Hardening: assign_staff_services, empty update_service,
#      23505 race replay, breaks, holidays, pagination, cache fingerprinting
# ============================================================================


@pytest.mark.anyio
async def test_repository_hardening_assign_empty_patch_23505_race_breaks_holidays_and_pagination(
    monkeypatch,
):
    org_id, biz_id = uuid4(), uuid4()
    staff_id = uuid4()
    valid_svc_id = uuid4()
    foreign_svc_id = uuid4()
    now = datetime.now(timezone.utc).isoformat()

    methods_called: List[tuple[str, str, Dict[str, str]]] = []
    breaks_store: Dict[str, Dict[str, Any]] = {}
    holidays_store: Dict[str, Dict[str, Any]] = {}
    appts_store: Dict[str, Dict[str, Any]] = {}
    race_idem_get_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        methods_called.append((request.method, request.url.path, params))
        path = request.url.path

        if path.endswith("/rest/v1/salon_services"):
            if request.method == "GET":
                if "id" in params and params["id"].startswith("in.("):
                    # Only valid_svc_id belongs to this salon; foreign_svc_id does not
                    if str(valid_svc_id) in params["id"]:
                        return httpx.Response(200, json=[{"id": str(valid_svc_id)}])
                    return httpx.Response(200, json=[])
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": str(valid_svc_id),
                            "organization_id": str(org_id),
                            "business_id": str(biz_id),
                            "name": "Haircut",
                            "description": None,
                            "category": "Hair",
                            "price": 500.0,
                            "currency": "INR",
                            "duration_minutes": 30,
                            "is_active": True,
                            "created_at": now,
                            "updated_at": now,
                        }
                    ],
                )
            if request.method == "DELETE":
                return httpx.Response(200, json=[{"id": str(valid_svc_id)}])

        if path.endswith("/rest/v1/salon_staff"):
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": str(staff_id),
                            "organization_id": str(org_id),
                            "business_id": str(biz_id),
                            "full_name": "Neha",
                            "role_designation": "Stylist",
                            "email": None,
                            "phone": None,
                            "bio": None,
                            "is_active": True,
                            "salon_staff_services": [],
                            "salon_staff_working_hours": [],
                            "salon_staff_breaks": [],
                            "created_at": now,
                            "updated_at": now,
                        }
                    ],
                )
            if request.method in {"PATCH", "DELETE"}:
                return httpx.Response(200, json=[{"id": str(staff_id)}])

        if path.endswith("/rest/v1/salon_staff_breaks"):
            if request.method == "POST":
                row = json.loads(request.read().decode("utf-8"))
                row["id"] = str(uuid4())
                row["created_at"] = now
                breaks_store[row["id"]] = row
                return httpx.Response(201, json=[row])
            if request.method == "GET":
                return httpx.Response(200, json=list(breaks_store.values()))
            if request.method == "DELETE":
                bid = params["id"].replace("eq.", "")
                removed = breaks_store.pop(bid, None)
                return httpx.Response(200, json=[removed] if removed else [])

        if path.endswith("/rest/v1/salon_holidays"):
            if request.method == "POST":
                row = json.loads(request.read().decode("utf-8"))
                row["id"] = str(uuid4())
                row["created_at"] = now
                holidays_store[row["id"]] = row
                return httpx.Response(201, json=[row])
            if request.method == "GET":
                return httpx.Response(200, json=list(holidays_store.values()))
            if request.method == "DELETE":
                hid = params["id"].replace("eq.", "")
                removed = holidays_store.pop(hid, None)
                return httpx.Response(200, json=[removed] if removed else [])

        if path.endswith("/rest/v1/salon_appointments"):
            if request.method == "GET":
                if "idempotency_key" in params:
                    race_idem_get_calls["count"] += 1
                    # First pre-check returns empty (simulating concurrent race); second replay returns stored row
                    if race_idem_get_calls["count"] == 1:
                        return httpx.Response(200, json=[])
                    return httpx.Response(200, json=list(appts_store.values()))
                return httpx.Response(200, json=list(appts_store.values()))
            if request.method == "POST":
                row = json.loads(request.read().decode("utf-8"))
                row["created_at"] = now
                row["updated_at"] = now
                row["cancelled_at"] = None
                row["cancellation_reason"] = None
                # Store the row as if a concurrent worker won, and return 409 23505
                appts_store[row["id"]] = row
                return httpx.Response(
                    409,
                    json={
                        "code": "23505",
                        "message": "duplicate key value violates unique constraint uq_salon_appointments_business_idempotency",
                    },
                )

        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: orig(transport=transport))

    repo = SupabaseRestSalonRepository(settings=_live_settings())
    owner = _make_user()

    # 1. assign_staff_services with cross-tenant foreign_svc_id rejects BEFORE any DELETE
    with pytest.raises(HTTPException) as exc_assign:
        await repo.assign_staff_services(owner, org_id, biz_id, staff_id, [valid_svc_id, foreign_svc_id])
    assert exc_assign.value.status_code == 400
    assert not any(m == "DELETE" and p.endswith("/salon_staff_services") for m, p, _ in methods_called)

    # 2. Empty update_service payload short-circuits to GET (no PATCH issued)
    methods_called.clear()
    svc_res = await repo.update_service(owner, org_id, biz_id, valid_svc_id, SalonServiceUpdateRequest())
    assert svc_res.id == valid_svc_id
    assert all(m != "PATCH" for m, _, _ in methods_called)

    # 3. Breaks CRUD
    br = await repo.add_staff_break(
        owner,
        org_id,
        biz_id,
        staff_id,
        SalonStaffBreakCreateRequest(weekday=1, label="Lunch", start_time="13:00", end_time="14:00"),
    )
    assert len(await repo.list_staff_breaks(owner, org_id, biz_id, staff_id)) == 1
    await repo.delete_staff_break(owner, org_id, biz_id, staff_id, br.id)
    assert len(await repo.list_staff_breaks(owner, org_id, biz_id, staff_id)) == 0

    # 4. Holidays CRUD + bounded pagination
    hol = await repo.create_holiday(
        owner,
        org_id,
        biz_id,
        SalonHolidayCreateRequest(holiday_date=date(2026, 12, 25), title="Christmas", is_closed_all_day=True),
    )
    hols = await repo.list_holidays(owner, org_id, biz_id, limit=9999, offset=-5)
    assert len(hols) == 1
    assert methods_called[-1][2]["limit"] == "500"  # clamped to MAX_PAGE_LIMIT
    assert methods_called[-1][2]["offset"] == "0"
    await repo.delete_holiday(owner, org_id, biz_id, hol.id)

    # 5. list_staff, update_staff, delete_staff, delete_service, list_appointments
    assert len(await repo.list_staff(owner, org_id, biz_id, limit=50, offset=0)) == 1
    await repo.update_staff(owner, org_id, biz_id, staff_id, SalonStaffUpdateRequest(role_designation="Lead Stylist"))
    await repo.delete_staff(owner, org_id, biz_id, staff_id)
    await repo.delete_service(owner, org_id, biz_id, valid_svc_id)

    # 6. Concurrent 23505 idempotency race replay
    now_dt = datetime.now(timezone.utc)
    race_appt = SalonAppointmentResponse(
        id=uuid4(),
        organization_id=org_id,
        business_id=biz_id,
        booking_reference="SLN-RACE001",
        idempotency_key="race-idem-key",
        service_id=valid_svc_id,
        service_name="Haircut",
        service_duration_minutes=30,
        service_price=500.0,
        service_currency="INR",
        staff_id=staff_id,
        staff_name="Neha",
        staff_role="Stylist",
        customer_name="Karan",
        customer_phone="+919876500000",
        appointment_date=date(2026, 12, 2),
        start_time="11:00",
        end_time="11:30",
        start_at=datetime(2026, 12, 2, 11, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 12, 2, 11, 30, tzinfo=timezone.utc),
        timezone="Asia/Kolkata",
        status=SalonAppointmentStatus.CONFIRMED,
        source=SalonAppointmentSource.API,
        created_at=now_dt,
        updated_at=now_dt,
    )
    replayed = await repo.create_appointment(owner, org_id, biz_id, race_appt)
    assert replayed.id == race_appt.id
    assert len(await repo.list_appointments(owner, org_id, biz_id, limit=25, offset=0)) == 1


def test_salon_service_cache_invalidates_on_credential_rotation_without_storing_raw_secrets():
    clear_salon_service_cache()
    s1 = _live_settings(srk="super-secret-key-v1")
    s2 = _live_settings(srk="super-secret-key-v2")

    svc1 = build_salon_workflow_service(settings=s1)
    svc1_again = build_salon_workflow_service(settings=s1)
    svc2 = build_salon_workflow_service(settings=s2)

    assert svc1 is svc1_again
    assert svc1 is not svc2
    # Ensure raw secret never appears in cache keys
    for key in _salon_service_cache.keys():
        assert "super-secret-key" not in str(key)


@pytest.mark.anyio
async def test_orchestrator_rejects_malicious_model_supplied_tenant_ids_for_salon():
    org_repo = InMemoryOrganizationRepository()
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    owner = _make_user()
    org = await org_repo.create_organization(
        owner, CreateOrganizationRequest(name="Safe Salon", industry=OrganizationIndustry.SALON)
    )
    biz_id = await onboarding_repo.get_or_create_primary_business_id(owner, org.id)
    await onboarding_repo.upsert_business_profile(
        owner, org.id, biz_id, BusinessProfileUpdateRequest(display_name="Safe Salon", timezone="Asia/Kolkata")
    )
    await onboarding_repo.upsert_business_hours(
        owner,
        org.id,
        biz_id,
        BusinessHoursUpdateRequest(
            timezone="Asia/Kolkata",
            schedule=[WeekdayHoursItem(weekday=wd, is_closed=False, opens_at="09:00", closes_at="19:00") for wd in range(7)],
        ),
    )
    await onboarding_repo.upsert_business_languages(
        owner,
        org.id,
        biz_id,
        BusinessLanguagesUpdateRequest(primary_language=LanguageCode.ENGLISH, supported_languages=[LanguageCode.ENGLISH]),
    )
    await onboarding_repo.upsert_assistant_settings(
        owner,
        org.id,
        biz_id,
        AssistantSettingsUpdateRequest(
            assistant_name="Ria",
            greeting="Hello!",
            personality=AssistantPersonality.FRIENDLY,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=True,
        ),
    )
    await onboarding_repo.upsert_escalation_settings(
        owner,
        org.id,
        biz_id,
        EscalationSettingsUpdateRequest(enabled=True, contact_name="Desk", contact_phone="+919999111122"),
    )
    bundle = await OnboardingService(repository=onboarding_repo).get_onboarding_bundle(owner, org.id)

    orch = AgentOrchestrator(
        context_manager=ConversationContextManager(),
        intent_classifier=IntentClassifier(),
        rate_limiter=VoiceSessionRateLimiter(),
        salon_service=build_salon_workflow_service(
            settings=Settings(_env_file=None, SVARIO_ENV="test"),
            salon_repo=InMemorySalonRepository(),
            onboarding_repo=onboarding_repo,
        ),
    )
    res = await orch.execute_realtime_tool(
        bundle=bundle,
        session_id="malicious-id-test",
        call_id="call-spoof",
        tool_name=AgentToolName.GET_SALON_SERVICES,
        arguments={"organization_id": str(uuid4())},
    )
    assert res.status == "rejected"
