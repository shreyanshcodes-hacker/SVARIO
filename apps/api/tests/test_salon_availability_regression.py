"""Phase 4 — P0 Salon Availability Regression Tests (16 cases + full voice-tool pipeline)."""

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
from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.service import OrganizationService, get_organization_service
from app.modules.salons.repository import InMemorySalonRepository
from app.modules.salons.schemas import (
    SalonAppointmentCancelRequest,
    SalonAppointmentCreateRequest,
    SalonAvailabilityStatus,
    SalonServiceCreateRequest,
    SalonStaffCreateRequest,
    SalonStaffWorkingHoursItem,
)
from app.modules.salons.service import SalonWorkflowService
from app.modules.voice.public_access import PublicVoicePolicyRegistry
from app.modules.voice.rate_limit import VoiceSessionRateLimiter
from app.modules.voice.service import VoiceSessionService, get_voice_session_service

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"


def _make_jwt(priv: ec.EllipticCurvePrivateKey, user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "riya@test.local",
            "role": "authenticated",
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "user_metadata": {"full_name": "Riya", "email_verified": True},
        },
        priv,
        algorithm="ES256",
        headers={"kid": "avail-reg-key", "typ": "JWT"},
    )


def _build_env(*, seed_staff: bool = True) -> Tuple[TestClient, Dict[str, Any]]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-test-avail-reg",
        OPENAI_REALTIME_MODEL="gpt-realtime",
        OPENAI_REALTIME_VOICE="alloy",
        VOICE_SESSION_RATE_LIMIT_PER_MINUTE=60,
        VOICE_PUBLIC_TOKEN_SECRET="avail-reg-secret-2026",
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
        max_tool_calls_per_turn=40,
        salon_service=salon_svc,
    )
    session_id = f"sess_avail_{uuid4().hex[:8]}"

    async def _mock_mint(cfg: Settings, _payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": session_id,
            "model": cfg.openai_realtime_model,
            "client_secret": {
                "value": "ek_avail_ephemeral",
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
    owner_tok = _make_jwt(priv, uuid4())
    org_id = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_tok}"},
        json={"name": "Riya Women salon", "industry": "salon", "timezone": "IST"},
    ).json()["id"]
    biz_id = client.get(
        f"/api/v1/organizations/{org_id}/onboarding",
        headers={"Authorization": f"Bearer {owner_tok}"},
    ).json()["business_id"]

    actor = verifier.verify_token(owner_tok)
    haircut = asyncio.run(
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

    staff_a = None
    staff_b = None
    unassigned_staff = None
    inactive_staff = None
    if seed_staff:
        staff_a = asyncio.run(
            salon_svc.create_staff(
                actor=actor,
                organization_id=UUID(org_id),
                business_id=UUID(biz_id),
                payload=SalonStaffCreateRequest(full_name="Ananya Stylist", role_designation="Senior Stylist", is_active=True),
            )
        )
        staff_b = asyncio.run(
            salon_svc.create_staff(
                actor=actor,
                organization_id=UUID(org_id),
                business_id=UUID(biz_id),
                payload=SalonStaffCreateRequest(full_name="Kavya Stylist", role_designation="Stylist", is_active=True),
            )
        )
        unassigned_staff = asyncio.run(
            salon_svc.create_staff(
                actor=actor,
                organization_id=UUID(org_id),
                business_id=UUID(biz_id),
                payload=SalonStaffCreateRequest(full_name="Meera Nails", role_designation="Nail Artist", is_active=True),
            )
        )
        inactive_staff = asyncio.run(
            salon_svc.create_staff(
                actor=actor,
                organization_id=UUID(org_id),
                business_id=UUID(biz_id),
                payload=SalonStaffCreateRequest(full_name="Former Stylist", role_designation="Stylist", is_active=False),
            )
        )
        for st in (staff_a, staff_b, inactive_staff):
            asyncio.run(
                salon_svc.assign_staff_services(
                    actor=actor,
                    organization_id=UUID(org_id),
                    business_id=UUID(biz_id),
                    staff_id=st.id,
                    service_ids=[haircut.id],
                )
            )

    return client, {
        "owner_tok": owner_tok,
        "org_id": org_id,
        "biz_id": biz_id,
        "session_id": session_id,
        "actor": actor,
        "haircut": haircut,
        "staff_a": staff_a,
        "staff_b": staff_b,
        "unassigned_staff": unassigned_staff,
        "inactive_staff": inactive_staff,
        "salon_repo": salon_repo,
        "salon_svc": salon_svc,
    }


def _call_avail_tool(client: TestClient, env: Dict[str, Any], args: Dict[str, Any], call_id: str = "c_av"):
    return client.post(
        "/api/v1/voice/tools/execute",
        headers={"Authorization": f"Bearer {env['owner_tok']}"},
        json={
            "session_id": env["session_id"],
            "organization_id": env["org_id"],
            "business_id": env["biz_id"],
            "access_mode": "organization_member",
            "call_id": call_id,
            "tool_name": "check_salon_availability",
            "arguments": args,
        },
    )


def test_empty_appointments_nov25_1400_ist_and_voice_pipeline() -> None:
    """Cases 1, 2, 6, 7, 11, 12, 13, 16 + full voice-tool pipeline."""
    client, env = _build_env(seed_staff=True)
    svc_id = str(env["haircut"].id)

    # Wednesday, 25 Nov 2026 -> 2 PM / 2:00 PM / 14:00 all resolve to 14:00 in Asia/Kolkata
    for time_input in ("14:00", "2 PM", "2:00 PM"):
        resp = _call_avail_tool(client, env, {
            "service_id": svc_id,
            "requested_date": "2026-11-25",
            "requested_time": time_input,
        })
        assert resp.status_code == 200
        out = resp.json()["output"]
        assert out["availability_status"] == "AVAILABLE"
        assert out["requested_time"] == "14:00"
        assert out["requested_time_available"] is True
        assert out["timezone"] == "Asia/Kolkata"
        assert out["requested_date"] == "2026-11-25"
        assert out["total_slots_available"] > 0

        slot_1400 = [s for s in out["available_slots"] if s["start_time"] == "14:00"]
        assert len(slot_1400) == 2  # staff_a and staff_b only (unassigned & inactive excluded)
        returned_staff_ids = {s["staff_id"] for s in slot_1400}
        assert str(env["staff_a"].id) in returned_staff_ids
        assert str(env["staff_b"].id) in returned_staff_ids
        assert str(env["unassigned_staff"].id) not in returned_staff_ids
        assert str(env["inactive_staff"].id) not in returned_staff_ids

    # Case 16: Additional future open dates (26 Nov, 27 Nov 2026) generate real slots
    for future_date in ("2026-11-26", "2026-11-27"):
        r = _call_avail_tool(client, env, {"service_id": svc_id, "requested_date": future_date})
        assert r.json()["output"]["availability_status"] == "AVAILABLE"
        assert r.json()["output"]["total_slots_available"] > 0


def test_overlap_cancelled_other_staff_and_sunday_closure() -> None:
    """Cases 3, 4, 5, 10: Overlapping booking blocks slot, cancellation frees it, other staff unaffected, Sunday closed."""
    client, env = _build_env(seed_staff=True)
    svc_id = env["haircut"].id
    staff_a_id = env["staff_a"].id
    staff_b_id = env["staff_b"].id

    # Book staff_a at 14:00 on 2026-11-25
    appt = asyncio.run(
        env["salon_svc"].create_appointment(
            actor=env["actor"],
            organization_id=UUID(env["org_id"]),
            business_id=UUID(env["biz_id"]),
            payload=SalonAppointmentCreateRequest(
                service_id=svc_id,
                staff_id=staff_a_id,
                appointment_date=date(2026, 11, 25),
                start_time="14:00",
                customer_name="Existing Customer",
                customer_phone="+919876543210",
            ),
        )
    )

    # Case 3: staff_a at 14:00 is unavailable, but other slots remain open
    r_a = _call_avail_tool(client, env, {
        "service_id": str(svc_id),
        "staff_id": str(staff_a_id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    out_a = r_a.json()["output"]
    assert out_a["availability_status"] == "REQUESTED_TIME_UNAVAILABLE"
    assert out_a["requested_time_available"] is False
    assert out_a["total_slots_available"] > 0  # Alternatives exist!

    # Case 5: staff_b is NOT blocked by staff_a's appointment
    r_b = _call_avail_tool(client, env, {
        "service_id": str(svc_id),
        "staff_id": str(staff_b_id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    assert r_b.json()["output"]["availability_status"] == "AVAILABLE"
    assert r_b.json()["output"]["requested_time_available"] is True

    # Case 4: Cancel staff_a's appointment -> 14:00 becomes available again
    asyncio.run(
        env["salon_svc"].cancel_appointment(
            actor=env["actor"],
            organization_id=UUID(env["org_id"]),
            business_id=UUID(env["biz_id"]),
            appointment_id=appt.id,
            payload=SalonAppointmentCancelRequest(cancellation_reason="Customer rescheduled"),
        )
    )
    r_a_after = _call_avail_tool(client, env, {
        "service_id": str(svc_id),
        "staff_id": str(staff_a_id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    assert r_a_after.json()["output"]["availability_status"] == "AVAILABLE"
    assert r_a_after.json()["output"]["requested_time_available"] is True

    # Case 10: Sunday 2026-11-29 -> BUSINESS_CLOSED
    r_sun = _call_avail_tool(client, env, {
        "service_id": str(svc_id),
        "requested_date": "2026-11-29",
        "requested_time": "14:00",
    })
    out_sun = r_sun.json()["output"]
    assert out_sun["is_business_closed"] is True
    assert out_sun["availability_status"] == "BUSINESS_CLOSED"


def test_no_staff_missing_schedule_fully_booked_and_supabase_error() -> None:
    """Cases 8, 9, 14, 15: Explicit NO_QUALIFIED_STAFF, STAFF_SCHEDULE_MISSING, fully booked, and AVAILABILITY_DATA_ERROR."""
    # Case 8: No qualified staff -> NO_QUALIFIED_STAFF (never misleading fully-booked)
    client_no_staff, env_no_staff = _build_env(seed_staff=False)
    r_no_staff = _call_avail_tool(client_no_staff, env_no_staff, {
        "service_id": str(env_no_staff["haircut"].id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    out_ns = r_no_staff.json()["output"]
    assert out_ns["availability_status"] == SalonAvailabilityStatus.NO_QUALIFIED_STAFF.value
    assert out_ns["total_slots_available"] == 0
    assert "No active stylist" in (out_ns["status_reason"] or "")

    # Case 9: Missing working hours for Wednesday (weekday=3) -> STAFF_SCHEDULE_MISSING
    client, env = _build_env(seed_staff=True)
    # Remove Wednesday working hours from staff_a & staff_b in repository
    for st in (env["staff_a"], env["staff_b"]):
        env["salon_repo"]._working_hours[st.id] = [
            SalonStaffWorkingHoursItem(weekday=1, is_off=False, start_time="09:00", end_time="18:00")
        ]
    r_missing_wh = _call_avail_tool(client, env, {
        "service_id": str(env["haircut"].id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    out_mwh = r_missing_wh.json()["output"]
    assert out_mwh["availability_status"] == SalonAvailabilityStatus.STAFF_SCHEDULE_MISSING.value
    assert out_mwh["total_slots_available"] == 0

    # Case 15: Fully booked / staff off on Wednesday -> REQUESTED_TIME_UNAVAILABLE with truthful reason
    for st in (env["staff_a"], env["staff_b"]):
        env["salon_repo"]._working_hours[st.id] = [
            SalonStaffWorkingHoursItem(weekday=3, is_off=True, start_time=None, end_time=None)
        ]
    r_full = _call_avail_tool(client, env, {
        "service_id": str(env["haircut"].id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    assert r_full.json()["output"]["availability_status"] == "REQUESTED_TIME_UNAVAILABLE"
    assert r_full.json()["output"]["total_slots_available"] == 0

    # Case 14: Supabase error -> AVAILABILITY_DATA_ERROR (never empty successful availability)
    async def _db_down(*_args: Any, **_kwargs: Any):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase query timed out.",
        )

    env["salon_repo"].list_staff = _db_down
    r_err = _call_avail_tool(client, env, {
        "service_id": str(env["haircut"].id),
        "requested_date": "2026-11-25",
        "requested_time": "14:00",
    })
    assert r_err.status_code == 200
    assert r_err.json()["status"] == "error"
    assert r_err.json()["output"]["availability_status"] == "AVAILABILITY_DATA_ERROR"
