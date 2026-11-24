"""Phase 5 — Comprehensive Salon Voice Booking Audit & Verification Tests (18 cases)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Tuple
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.agents.orchestrator import AgentOrchestrator
from app.core.auth import AuthenticatedUser, SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.service import OrganizationService, get_organization_service
from app.modules.salons.repository import InMemorySalonRepository
from app.modules.salons.schemas import (
    SalonServiceCreateRequest,
    SalonStaffCreateRequest,
    normalize_time_string,
)
from app.modules.salons.service import SalonWorkflowService
from app.modules.voice.public_access import PublicVoicePolicyRegistry
from app.modules.voice.rate_limit import VoiceSessionRateLimiter
from app.modules.voice.service import VoiceSessionService, get_voice_session_service

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


def _make_jwt(priv: ec.EllipticCurvePrivateKey, user_id: UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "role": "authenticated",
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "user_metadata": {"full_name": "Riya", "email_verified": True},
        },
        priv,
        algorithm="ES256",
        headers={"kid": "audit-key", "typ": "JWT"},
    )


def _next_workday() -> str:
    d = date.today() + timedelta(days=1)
    while d.weekday() == 6:  # Sunday closed by default
        d += timedelta(days=1)
    return d.isoformat()


def _setup_env() -> Tuple[TestClient, Dict[str, Any]]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-test-audit-key",
        OPENAI_REALTIME_MODEL="gpt-realtime",
        OPENAI_REALTIME_VOICE="alloy",
        VOICE_SESSION_RATE_LIMIT_PER_MINUTE=60,
        VOICE_PUBLIC_TOKEN_SECRET="audit-secret-key-2026",
    )
    verifier = SupabaseJWTVerifier(settings=settings, key_resolver=lambda _t, _h: pub)
    org_repo = InMemoryOrganizationRepository()
    org_svc = OrganizationService(repository=org_repo)
    ob_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    ob_svc = OnboardingService(repository=ob_repo)
    salon_repo = InMemorySalonRepository()
    salon_svc = SalonWorkflowService(
        settings=settings,
        salon_repo=salon_repo,
        onboarding_repo=ob_repo,
    )
    orchestrator = AgentOrchestrator(
        rate_limiter=VoiceSessionRateLimiter(window_seconds=60),
        max_tool_calls_per_turn=30,
        salon_service=salon_svc,
    )

    session_id = f"sess_audit_{uuid4().hex[:8]}"

    async def _mock_mint(cfg: Settings, _payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": session_id,
            "model": cfg.openai_realtime_model,
            "client_secret": {
                "value": "ek_audit_ephemeral",
                "expires_at": int((datetime.now(timezone.utc) + timedelta(seconds=120)).timestamp()),
            },
        }

    voice_svc = VoiceSessionService(
        settings=settings,
        onboarding_service=ob_svc,
        rate_limiter=VoiceSessionRateLimiter(window_seconds=60),
        public_registry=PublicVoicePolicyRegistry(),
        upstream_mint=_mock_mint,
        orchestrator=orchestrator,
    )

    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_svc
    app.dependency_overrides[get_onboarding_service] = lambda: ob_svc
    app.dependency_overrides[get_voice_session_service] = lambda: voice_svc

    client = TestClient(app)
    owner_tok = _make_jwt(priv, uuid4(), "riya@example.com")
    intruder_tok = _make_jwt(priv, uuid4(), "intruder@example.com")

    org_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_tok}"},
        json={"name": "Riya Women salon", "industry": "salon", "timezone": "IST"},
    )
    assert org_resp.status_code == 201
    org_id = org_resp.json()["id"]
    biz_id = client.get(
        f"/api/v1/organizations/{org_id}/onboarding",
        headers={"Authorization": f"Bearer {owner_tok}"},
    ).json()["business_id"]

    actor = verifier.verify_token(owner_tok)
    active_svc = asyncio.run(
        salon_svc.create_service(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            payload=SalonServiceCreateRequest(
                name="Basic Haircut",
                category="Hair",
                price=299.0,
                currency="INR",
                duration_minutes=30,
                is_active=True,
            ),
        )
    )
    inactive_svc = asyncio.run(
        salon_svc.create_service(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            payload=SalonServiceCreateRequest(
                name="Discontinued Spa",
                category="Hair",
                price=999.0,
                currency="INR",
                duration_minutes=60,
                is_active=False,
            ),
        )
    )
    qualified_staff = asyncio.run(
        salon_svc.create_staff(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            payload=SalonStaffCreateRequest(
                full_name="Meera Stylist",
                role_designation="Senior Stylist",
                is_active=True,
            ),
        )
    )
    unassigned_staff = asyncio.run(
        salon_svc.create_staff(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            payload=SalonStaffCreateRequest(
                full_name="Neha Nails",
                role_designation="Nail Technician",
                is_active=True,
            ),
        )
    )
    inactive_staff = asyncio.run(
        salon_svc.create_staff(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            payload=SalonStaffCreateRequest(
                full_name="Former Stylist",
                role_designation="Stylist",
                is_active=False,
            ),
        )
    )
    asyncio.run(
        salon_svc.assign_staff_services(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            staff_id=qualified_staff.id,
            service_ids=[active_svc.id],
        )
    )
    asyncio.run(
        salon_svc.assign_staff_services(
            actor=actor,
            organization_id=UUID(org_id),
            business_id=UUID(biz_id),
            staff_id=inactive_staff.id,
            service_ids=[active_svc.id],
        )
    )

    return client, {
        "owner_tok": owner_tok,
        "intruder_tok": intruder_tok,
        "org_id": org_id,
        "biz_id": biz_id,
        "session_id": session_id,
        "active_svc": active_svc,
        "inactive_svc": inactive_svc,
        "qualified_staff": qualified_staff,
        "unassigned_staff": unassigned_staff,
        "inactive_staff": inactive_staff,
        "salon_repo": salon_repo,
        "salon_svc": salon_svc,
        "actor": actor,
    }


def _exec_tool(
    client: TestClient,
    env: Dict[str, Any],
    tool_name: str,
    arguments: Dict[str, Any],
    *,
    call_id: str = "call_test_1",
    token: str | None = None,
):
    return client.post(
        "/api/v1/voice/tools/execute",
        headers={"Authorization": f"Bearer {token or env['owner_tok']}"},
        json={
            "session_id": env["session_id"],
            "organization_id": env["org_id"],
            "business_id": env["biz_id"],
            "access_mode": "organization_member",
            "call_id": call_id,
            "tool_name": tool_name,
            "arguments": arguments,
        },
    )


def test_time_normalization_supports_24h_and_12h_and_rejects_invalid() -> None:
    """Case 6: Time normalization handles canonical HH:MM, single-digit H:MM, AM/PM, and rejects invalid times."""
    assert normalize_time_string("09:00") == "09:00"
    assert normalize_time_string("9:00") == "09:00"
    assert normalize_time_string("16:00:00") == "16:00"
    assert normalize_time_string("4 PM") == "16:00"
    assert normalize_time_string("4:00 PM") == "16:00"
    assert normalize_time_string("9:30 am") == "09:30"
    assert normalize_time_string("12:00 PM") == "12:00"
    assert normalize_time_string("12:00 AM") == "00:00"

    for bad in ("25:00", "13:00 PM", "0:00 AM", "16:60", "not-a-time"):
        try:
            normalize_time_string(bad)
            assert False, f"Expected ValueError for {bad}"
        except ValueError:
            pass


def test_salon_booking_validation_and_edge_cases() -> None:
    """Cases 1-13 & 16-18: Full booking lifecycle, validation, staff rules, idempotency, RLS, and no false confirmation."""
    client, env = _setup_env()
    d = _next_workday()
    svc_id = str(env["active_svc"].id)
    staff_id = str(env["qualified_staff"].id)

    # Case 2: Missing customer name
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "appointment_date": d, "start_time": "10:00", "customer_phone": "+919876543210"
    }, call_id="c_missing_name")
    assert r.json()["status"] == "rejected" and r.json()["call_id"] == "c_missing_name"

    # Case 3: Missing customer phone
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "appointment_date": d, "start_time": "10:00", "customer_name": "Test Caller"
    }, call_id="c_missing_phone")
    assert r.json()["status"] == "rejected"

    # Case 4: Invalid service UUID
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": "Basic Haircut", "appointment_date": d, "start_time": "10:00",
        "customer_name": "Test Caller", "customer_phone": "+919876543210"
    })
    assert r.json()["status"] == "rejected"

    # Case 5: Invalid date
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "appointment_date": "tomorrow", "start_time": "10:00",
        "customer_name": "Test Caller", "customer_phone": "+919876543210"
    })
    assert r.json()["status"] == "rejected"

    # Case 6: Invalid time format
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "appointment_date": d, "start_time": "25:99",
        "customer_name": "Test Caller", "customer_phone": "+919876543210"
    })
    assert r.json()["status"] == "rejected"

    # Case 9: Staff not assigned to service
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "staff_id": str(env["unassigned_staff"].id),
        "appointment_date": d, "start_time": "10:00",
        "customer_name": "Test Caller", "customer_phone": "+919876543210"
    })
    assert r.json()["status"] == "rejected" and r.json()["output"]["error"] == "http_400"

    # Case 10: Inactive service
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": str(env["inactive_svc"].id), "appointment_date": d, "start_time": "10:00",
        "customer_name": "Test Caller", "customer_phone": "+919876543210"
    })
    assert r.json()["status"] == "rejected" and r.json()["output"]["error"] == "http_400"

    # Case 11: Inactive staff
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "staff_id": str(env["inactive_staff"].id),
        "appointment_date": d, "start_time": "10:00",
        "customer_name": "Test Caller", "customer_phone": "+919876543210"
    })
    assert r.json()["status"] == "rejected" and r.json()["output"]["error"] == "http_400"

    # Case 1 & 7: Valid slot with automatic staff assignment + AM/PM time normalization ("10:00 AM") + IST->Asia/Kolkata
    r = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "appointment_date": d, "start_time": "10:00 AM",
        "customer_name": "Auto Staff Caller", "customer_phone": "+919876543210",
        "idempotency_key": "idem-auto-1000"
    }, call_id="c_auto_ok")
    body = r.json()
    assert body["status"] == "succeeded"
    assert body["call_id"] == "c_auto_ok"
    assert body["output"]["booking_confirmed"] is True
    assert body["output"]["start_time"] == "10:00"
    assert body["output"]["timezone"] == "Asia/Kolkata"
    ref_auto = body["output"]["booking_reference"]

    # Case 13: Duplicate idempotency retry returns original booking
    r_dup = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "appointment_date": d, "start_time": "10:00",
        "customer_name": "Auto Staff Caller", "customer_phone": "+919876543210",
        "idempotency_key": "idem-auto-1000"
    }, call_id="c_auto_dup")
    assert r_dup.json()["status"] == "succeeded"
    assert r_dup.json()["output"]["booking_reference"] == ref_auto

    # Case 12: Slot no longer available (conflict)
    r_conflict = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "staff_id": staff_id, "appointment_date": d, "start_time": "10:00",
        "customer_name": "Second Caller", "customer_phone": "+919811112222"
    }, call_id="c_conflict")
    assert r_conflict.json()["status"] == "rejected"
    assert r_conflict.json()["output"]["error"] == "http_409"

    # Case 8: Valid slot with explicitly selected staff ("4:00 PM" -> "16:00")
    r_explicit = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "staff_id": staff_id, "appointment_date": d, "start_time": "4:00 PM",
        "customer_name": "Explicit Staff Caller", "customer_phone": "+919876543211"
    }, call_id="c_explicit_ok")
    assert r_explicit.json()["status"] == "succeeded"
    assert r_explicit.json()["output"]["start_time"] == "16:00"
    assert r_explicit.json()["output"]["staff_name"] == "Meera Stylist"

    # Case 16: RLS / cross-tenant authorization rejection -> 403
    r_forbidden = _exec_tool(
        client, env, "create_salon_appointment",
        {"service_id": svc_id, "appointment_date": d, "start_time": "11:00",
         "customer_name": "Intruder", "customer_phone": "+919800000000"},
        token=env["intruder_tok"],
    )
    assert r_forbidden.status_code == 403

    # Case 18: No false booking confirmation from unconfirmed booking intent turn
    turn_resp = client.post(
        "/api/v1/agent/turns",
        headers={"Authorization": f"Bearer {env['owner_tok']}"},
        json={
            "session_id": env["session_id"],
            "organization_id": env["org_id"],
            "business_id": env["biz_id"],
            "access_mode": "organization_member",
            "user_input": "Book me a Basic Haircut tomorrow at 2 PM",
        },
    )
    assert turn_resp.status_code == 200
    assert turn_resp.json()["booking_created"] is False


def test_simultaneous_booking_conflict_and_supabase_insert_failure() -> None:
    """Cases 14, 15, 17: Concurrent booking double-book protection & backend insert failure surfaced cleanly."""
    client, env = _setup_env()
    d = _next_workday()
    svc_id = str(env["active_svc"].id)
    staff_id = str(env["qualified_staff"].id)

    # Case 14: Two simultaneous attempts for the same staff/time
    async def _run_concurrent():
        from app.modules.salons.schemas import SalonAppointmentCreateRequest
        req1 = SalonAppointmentCreateRequest(
            service_id=UUID(svc_id), staff_id=UUID(staff_id),
            appointment_date=date.fromisoformat(d), start_time="14:00",
            customer_name="Caller One", customer_phone="+919876543210",
        )
        req2 = SalonAppointmentCreateRequest(
            service_id=UUID(svc_id), staff_id=UUID(staff_id),
            appointment_date=date.fromisoformat(d), start_time="14:00",
            customer_name="Caller Two", customer_phone="+919876543219",
        )
        return await asyncio.gather(
            env["salon_svc"].create_appointment(
                actor=env["actor"], organization_id=UUID(env["org_id"]),
                business_id=UUID(env["biz_id"]), payload=req1,
            ),
            env["salon_svc"].create_appointment(
                actor=env["actor"], organization_id=UUID(env["org_id"]),
                business_id=UUID(env["biz_id"]), payload=req2,
            ),
            return_exceptions=True,
        )

    results = asyncio.run(_run_concurrent())
    successes = [x for x in results if not isinstance(x, Exception)]
    conflicts = [x for x in results if isinstance(x, HTTPException) and x.status_code == 409]
    assert len(successes) == 1
    assert len(conflicts) == 1

    # Case 15 & 17: Simulated Supabase insert failure -> status="error", call_id preserved, no fake confirmation
    async def _boom(*_args: Any, **_kwargs: Any):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase insert failed due to upstream database error.",
        )

    env["salon_repo"].create_appointment = _boom
    r_fail = _exec_tool(client, env, "create_salon_appointment", {
        "service_id": svc_id, "staff_id": staff_id, "appointment_date": d, "start_time": "15:00",
        "customer_name": "Error Test", "customer_phone": "+919876543215",
    }, call_id="c_db_fail")
    fail_body = r_fail.json()
    assert r_fail.status_code == 200
    assert fail_body["call_id"] == "c_db_fail"
    assert fail_body["status"] == "error"
    assert "Do not claim the action succeeded" in fail_body["output"]["message"]
    assert fail_body["output"].get("booking_confirmed") is not True
