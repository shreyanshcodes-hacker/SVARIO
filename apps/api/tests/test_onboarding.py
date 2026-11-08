"""Tests for Stage 2 Industry Selection & Business Onboarding API & RBAC."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.service import (
    OrganizationService,
    get_organization_service,
)

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_KID = "svario-stage2-test-key"


@pytest.fixture
def stage2_env() -> tuple[TestClient, ec.EllipticCurvePrivateKey]:
    """Provide an isolated FastAPI TestClient wired with Stage 1 + Stage 2 repositories."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
    )

    verifier = SupabaseJWTVerifier(
        settings=settings,
        key_resolver=lambda _tok, _hdr: public_key,
    )
    org_repo = InMemoryOrganizationRepository()
    org_service = OrganizationService(repository=org_repo)
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    onboarding_service = OnboardingService(repository=onboarding_repo)

    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_service
    app.dependency_overrides[get_onboarding_service] = lambda: onboarding_service

    return TestClient(app), private_key


def make_token(
    private_key: ec.EllipticCurvePrivateKey,
    user_id: UUID,
    email: str = "founder@svario.ai",
    full_name: str = "Operator",
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": "authenticated",
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
        "user_metadata": {"full_name": full_name, "email_verified": True},
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": TEST_KID, "typ": "JWT"},
    )


def create_test_org(
    client: TestClient, token: str, name: str = "Aura Clinic", industry: str = "clinic"
) -> str:
    resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "industry": industry, "timezone": "Asia/Kolkata"},
    )
    assert resp.status_code == 201
    return str(resp.json()["id"])


def test_business_profile_create_update_and_validation(
    stage2_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Owner/admin can update business profile; invalid email/phone/website are rejected."""
    client, key = stage2_env
    owner_token = make_token(key, uuid4())
    org_id = create_test_org(client, owner_token, "Serenity Salon", "salon")

    # Valid business profile update
    valid_resp = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "display_name": "Serenity Hair & Spa Studio",
            "description": "Boutique luxury hair and skin care studio.",
            "phone": "+91 98765 43210",
            "email": "concierge@serenitysalon.in",
            "website": "https://serenitysalon.in",
            "address": "42 Linking Road",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
            "postal_code": "400050",
            "timezone": "Asia/Kolkata",
        },
    )
    assert valid_resp.status_code == 200
    profile = valid_resp.json()
    assert profile["display_name"] == "Serenity Hair & Spa Studio"
    assert profile["city"] == "Mumbai"
    assert profile["website"] == "https://serenitysalon.in"

    # Invalid email rejected with 422
    bad_email = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "display_name": "Serenity Hair & Spa Studio",
            "email": "not-an-email",
            "timezone": "Asia/Kolkata",
        },
    )
    assert bad_email.status_code == 422

    # Invalid URL rejected with 422
    bad_url = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "display_name": "Serenity Hair & Spa Studio",
            "website": "ftp://invalid-scheme.com",
            "timezone": "Asia/Kolkata",
        },
    )
    assert bad_url.status_code == 422


def test_business_hours_validation_and_overnight_support(
    stage2_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Weekly hours validate closed days, normal hours, overnight shifts, and reject bad ranges."""
    client, key = stage2_env
    owner_token = make_token(key, uuid4())
    org_id = create_test_org(client, owner_token, "City General Hospital", "hospital")

    valid_schedule: List[Dict[str, Any]] = [
        {"weekday": 0, "is_closed": True, "opens_at": None, "closes_at": None, "is_overnight": False},
        {"weekday": 1, "is_closed": False, "opens_at": "08:00", "closes_at": "20:00", "is_overnight": False},
        {"weekday": 2, "is_closed": False, "opens_at": "08:00", "closes_at": "20:00", "is_overnight": False},
        {"weekday": 3, "is_closed": False, "opens_at": "08:00", "closes_at": "20:00", "is_overnight": False},
        {"weekday": 4, "is_closed": False, "opens_at": "08:00", "closes_at": "20:00", "is_overnight": False},
        {"weekday": 5, "is_closed": False, "opens_at": "20:00", "closes_at": "06:00", "is_overnight": True},
        {"weekday": 6, "is_closed": False, "opens_at": "09:00", "closes_at": "15:00", "is_overnight": False},
    ]

    ok_resp = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/hours",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"timezone": "Asia/Kolkata", "schedule": valid_schedule},
    )
    assert ok_resp.status_code == 200
    saved = ok_resp.json()
    assert saved["schedule"][0]["is_closed"] is True
    assert saved["schedule"][5]["is_overnight"] is True
    assert saved["schedule"][5]["opens_at"] == "20:00"
    assert saved["schedule"][5]["closes_at"] == "06:00"

    # Invalid range: opens_at > closes_at when is_overnight is False -> 422
    invalid_schedule = list(valid_schedule)
    invalid_schedule[1] = {
        "weekday": 1,
        "is_closed": False,
        "opens_at": "19:00",
        "closes_at": "09:00",
        "is_overnight": False,
    }
    bad_resp = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/hours",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"timezone": "Asia/Kolkata", "schedule": invalid_schedule},
    )
    assert bad_resp.status_code == 422


def test_languages_and_assistant_settings_persistence(
    stage2_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Languages (en, hi, hinglish) and assistant settings persist accurately."""
    client, key = stage2_env
    owner_token = make_token(key, uuid4())
    org_id = create_test_org(client, owner_token, "Apex Clinic", "clinic")

    lang_resp = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/languages",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "primary_language": "en",
            "supported_languages": ["en", "hi", "hinglish"],
        },
    )
    assert lang_resp.status_code == 200
    lang_data = lang_resp.json()
    assert lang_data["primary_language"] == "en"
    assert lang_data["supported_languages"] == ["en", "hi", "hinglish"]

    asst_resp = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/assistant",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "assistant_name": "Aarohi Clinical Desk",
            "greeting": "Namaste! Welcome to Apex Clinic reception. How can I assist you?",
            "personality": "warm",
            "response_style": "concise",
            "enabled": True,
        },
    )
    assert asst_resp.status_code == 200
    asst_data = asst_resp.json()
    assert asst_data["assistant_name"] == "Aarohi Clinical Desk"
    assert asst_data["personality"] == "warm"
    assert asst_data["response_style"] == "concise"
    assert asst_data["enabled"] is True


def test_faq_crud_and_sorting(
    stage2_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """FAQ items can be created, edited, toggled active/inactive, sorted, and deleted."""
    client, key = stage2_env
    owner_token = make_token(key, uuid4())
    org_id = create_test_org(client, owner_token, "Velvet Salon", "salon")

    faq1 = client.post(
        f"/api/v1/organizations/{org_id}/onboarding/faqs",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "question": "Where are you located?",
            "answer": "We are on 2nd Avenue near Metro Station.",
            "category": "location",
            "is_active": True,
            "sort_order": 20,
        },
    )
    assert faq1.status_code == 201
    faq1_id = faq1.json()["id"]

    faq2 = client.post(
        f"/api/v1/organizations/{org_id}/onboarding/faqs",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "question": "What are your opening hours?",
            "answer": "Monday through Saturday from 9 AM to 8 PM.",
            "category": "hours",
            "is_active": True,
            "sort_order": 10,
        },
    )
    assert faq2.status_code == 201
    faq2_id = faq2.json()["id"]

    # List FAQs -> sorted by sort_order ASC (faq2 first, faq1 second)
    listed = client.get(
        f"/api/v1/organizations/{org_id}/onboarding/faqs",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert listed.status_code == 200
    items = listed.json()
    assert [item["id"] for item in items] == [faq2_id, faq1_id]

    # Edit & deactivate faq1
    updated = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/faqs/{faq1_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"is_active": False, "answer": "Updated address: 5th Block Koramangala."},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert "Koramangala" in updated.json()["answer"]

    # Delete faq2
    deleted = client.delete(
        f"/api/v1/organizations/{org_id}/onboarding/faqs/{faq2_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert deleted.status_code == 204

    remaining = client.get(
        f"/api/v1/organizations/{org_id}/onboarding/faqs",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == faq1_id


def test_escalation_settings_and_onboarding_progress_persistence(
    stage2_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Escalation settings validate contact requirements and onboarding progress persists."""
    client, key = stage2_env
    owner_token = make_token(key, uuid4())
    org_id = create_test_org(client, owner_token, "Sunrise Hospital", "hospital")

    # Enabling escalation without contact_name / contact_phone fails with 422
    bad_esc = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/escalation",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"enabled": True, "preferred_method": "phone"},
    )
    assert bad_esc.status_code == 422

    # Valid escalation settings
    ok_esc = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/escalation",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "enabled": True,
            "contact_name": "Duty Switchboard Supervisor",
            "contact_phone": "+91 22 4000 9911",
            "contact_email": "switchboard@sunrisehospital.org",
            "preferred_method": "either",
            "escalation_instructions": "Direct emergency callers immediately to casualty desk.",
        },
    )
    assert ok_esc.status_code == 200
    assert ok_esc.json()["contact_name"] == "Duty Switchboard Supervisor"

    # Save progress & mark completed
    prog_resp = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/progress",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "current_step": "review",
            "completed_steps": [
                "industry",
                "profile",
                "hours",
                "languages",
                "assistant",
                "faqs",
                "escalation",
                "review",
            ],
            "is_completed": True,
        },
    )
    assert prog_resp.status_code == 200
    prog_data = prog_resp.json()
    assert prog_data["is_completed"] is True
    assert prog_data["completed_at"] is not None

    # Fetch full bundle and verify healthcare safeguards
    bundle_resp = client.get(
        f"/api/v1/organizations/{org_id}/onboarding",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert bundle_resp.status_code == 200
    bundle = bundle_resp.json()
    assert bundle["healthcare_safeguards"]["applies_to_healthcare"] is True
    assert bundle["healthcare_safeguards"]["administrative_only"] is True
    assert bundle["progress"]["is_completed"] is True


def test_non_member_and_staff_role_restrictions_enforced(
    stage2_env: tuple[TestClient, ec.EllipticCurvePrivateKey],
) -> None:
    """Non-members receive 403 on all endpoints; staff can read but cannot mutate onboarding."""
    client, key = stage2_env
    owner_id = uuid4()
    staff_id = uuid4()
    outsider_id = uuid4()

    owner_token = make_token(key, owner_id, email="owner@clinic.org")
    staff_token = make_token(key, staff_id, email="staff@clinic.org")
    outsider_token = make_token(key, outsider_id, email="outsider@other.org")

    org_id = create_test_org(client, owner_token, "Prime Care Clinic", "clinic")

    # Add staff member
    add_resp = client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": str(staff_id), "role": "staff"},
    )
    assert add_resp.status_code == 201

    # Non-member cannot read or update onboarding (403 Forbidden)
    assert (
        client.get(
            f"/api/v1/organizations/{org_id}/onboarding",
            headers={"Authorization": f"Bearer {outsider_token}"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/organizations/{org_id}/onboarding/industry",
            headers={"Authorization": f"Bearer {outsider_token}"},
            json={"industry": "salon"},
        ).status_code
        == 403
    )

    # Staff member CAN read onboarding bundle (200 OK)
    staff_get = client.get(
        f"/api/v1/organizations/{org_id}/onboarding",
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert staff_get.status_code == 200

    # Staff member CANNOT change organization industry (403 Forbidden)
    staff_ind = client.put(
        f"/api/v1/organizations/{org_id}/onboarding/industry",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"industry": "salon"},
    )
    assert staff_ind.status_code == 403

    # Staff member CANNOT update profile, hours, assistant, escalation, or FAQs (403 Forbidden)
    assert (
        client.put(
            f"/api/v1/organizations/{org_id}/onboarding/profile",
            headers={"Authorization": f"Bearer {staff_token}"},
            json={"display_name": "Unauthorized Rename", "timezone": "UTC"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/organizations/{org_id}/onboarding/faqs",
            headers={"Authorization": f"Bearer {staff_token}"},
            json={"question": "Can staff add FAQ?", "answer": "No", "category": "general"},
        ).status_code
        == 403
    )
