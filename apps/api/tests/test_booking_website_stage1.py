"""Stage 1 Tests — White-Label Booking Website Dashboard Foundation (Auth, Slug, Branding, Assets, Cross-Tenant)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.service import OrganizationService, get_organization_service
from app.modules.websites.repository import InMemoryBookingWebsiteRepository
from app.modules.websites.service import BookingWebsiteService, get_booking_website_service

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
            "user_metadata": {"full_name": "Salon Owner", "email_verified": True},
        },
        priv,
        algorithm="ES256",
        headers={"kid": "web-s1-key", "typ": "JWT"},
    )


def _build_env() -> Tuple[TestClient, ec.EllipticCurvePrivateKey]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-test-web-s1",
    )
    verifier = SupabaseJWTVerifier(settings=settings, key_resolver=lambda _t, _h: pub)
    org_repo = InMemoryOrganizationRepository()
    org_svc = OrganizationService(repository=org_repo)
    ob_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    ob_svc = OnboardingService(repository=ob_repo)
    web_repo = InMemoryBookingWebsiteRepository()
    web_svc = BookingWebsiteService(
        settings=settings,
        onboarding_service=ob_svc,
        website_repo=web_repo,
    )

    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_svc
    app.dependency_overrides[get_onboarding_service] = lambda: ob_svc
    app.dependency_overrides[get_booking_website_service] = lambda: web_svc
    return TestClient(app), priv


def test_booking_website_auth_cross_tenant_and_industry_guard() -> None:
    """Only authorized salon members can read/edit; cross-tenant and clinic orgs are rejected."""
    client, priv = _build_env()
    owner_a = _make_jwt(priv, uuid4(), "owner-a@svario.ai")
    owner_b = _make_jwt(priv, uuid4(), "owner-b@svario.ai")

    salon_a = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"name": "Royal Beauty Studio", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]
    clinic_b = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_b}"},
        json={"name": "Care Clinic", "industry": "clinic", "timezone": "Asia/Kolkata"},
    ).json()["id"]

    # Unauthenticated -> 401
    assert client.get(f"/api/v1/organizations/{salon_a}/booking-website").status_code == 401

    # Cross-tenant intruder -> 403
    assert (
        client.get(
            f"/api/v1/organizations/{salon_a}/booking-website",
            headers={"Authorization": f"Bearer {owner_b}"},
        ).status_code
        == 403
    )

    # Clinic organization -> 400 (salon only)
    assert (
        client.get(
            f"/api/v1/organizations/{clinic_b}/booking-website",
            headers={"Authorization": f"Bearer {owner_b}"},
        ).status_code
        == 400
    )


def test_slug_normalization_reserved_protection_and_uniqueness() -> None:
    """Slug normalization, reserved route rejection, and cross-tenant uniqueness work."""
    client, priv = _build_env()
    owner_a = _make_jwt(priv, uuid4(), "a@svario.ai")
    owner_b = _make_jwt(priv, uuid4(), "b@svario.ai")

    salon_a = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"name": "Royal Beauty Studio", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]
    salon_b = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_b}"},
        json={"name": "Glow And Shine", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]

    # Reserved slug rejected
    res_reserved = client.get(
        f"/api/v1/organizations/{salon_a}/booking-website/slug-availability?slug=dashboard",
        headers={"Authorization": f"Bearer {owner_a}"},
    )
    assert res_reserved.status_code == 200
    assert res_reserved.json()["available"] is False
    assert "reserved" in res_reserved.json()["reason"].lower()

    # Valid normalized slug saved by Salon A
    save_a = client.put(
        f"/api/v1/organizations/{salon_a}/booking-website",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"slug": "  Royal Beauty Studio!! "},
    )
    assert save_a.status_code == 200
    assert save_a.json()["slug"] == "royal-beauty-studio"

    # Salon B cannot claim Salon A's slug
    check_b = client.get(
        f"/api/v1/organizations/{salon_b}/booking-website/slug-availability?slug=royal-beauty-studio",
        headers={"Authorization": f"Bearer {owner_b}"},
    )
    assert check_b.json()["available"] is False

    conflict_b = client.put(
        f"/api/v1/organizations/{salon_b}/booking-website",
        headers={"Authorization": f"Bearer {owner_b}"},
        json={"slug": "royal-beauty-studio"},
    )
    assert conflict_b.status_code == 409


def test_branding_validation_asset_upload_and_stage1_publish_guard() -> None:
    """Branding rejects CSS/HTML injection, validates PNG logo uploads, and guards Stage 1 publishing."""
    client, priv = _build_env()
    owner = _make_jwt(priv, uuid4(), "owner@svario.ai")

    salon_id = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner}"},
        json={"name": "Elite Hair Lounge", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]

    # Invalid hex color / CSS injection -> 422
    bad_color = client.put(
        f"/api/v1/organizations/{salon_id}/booking-website",
        headers={"Authorization": f"Bearer {owner}"},
        json={"primary_color": "red; background:url(javascript:alert(1))"},
    )
    assert bad_color.status_code == 422

    # HTML tag injection -> 422
    bad_html = client.put(
        f"/api/v1/organizations/{salon_id}/booking-website",
        headers={"Authorization": f"Bearer {owner}"},
        json={"headline": "<script>alert(1)</script>"},
    )
    assert bad_html.status_code == 422

    # Valid draft save succeeds
    good_save = client.put(
        f"/api/v1/organizations/{salon_id}/booking-website",
        headers={"Authorization": f"Bearer {owner}"},
        json={
            "headline": "Luxury Hair & Spa Lounge",
            "primary_color": "#7657F6",
            "theme": "light",
            "font_family": "playfair_display",
            "button_style": "pill",
        },
    )
    assert good_save.status_code == 200
    body = good_save.json()
    assert body["status"] == "draft"
    assert body["public_url_path"] is None
    assert body["publish_readiness"]["public_engine_ready"] is False
    assert body["publish_readiness"]["can_publish"] is False

    # Valid PNG upload succeeds; spoofed magic bytes rejected
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    ok_upload = client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner}", "Content-Type": "image/png"},
        content=png_bytes,
    )
    assert ok_upload.status_code == 201
    assert ok_upload.json()["asset_type"] == "logo"

    bad_upload = client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner}", "Content-Type": "image/png"},
        content=b"<svg onload=alert(1)>",
    )
    assert bad_upload.status_code == 400

    # Complete required contact info, then verify publish is safely guarded in Stage 1 (409)
    client.put(
        f"/api/v1/organizations/{salon_id}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner}"},
        json={
            "display_name": "Elite Hair Lounge",
            "phone": "+919876543210",
            "timezone": "Asia/Kolkata",
        },
    )
    pub_resp = client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/publish",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert pub_resp.status_code == 409
    assert "Stage 2" in pub_resp.json()["message"]
