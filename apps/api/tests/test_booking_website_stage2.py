"""Stage 2 Tests — Dynamic Public Booking Website Engine, 8 Templates, Publish/Unpublish & Tenant Security."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
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
from app.modules.salons.repository import InMemorySalonRepository
from app.modules.salons.schemas import SalonServiceResponse
from app.modules.websites.repository import (
    InMemoryBookingWebsiteRepository,
    is_valid_brand_asset_path,
)
from app.modules.websites.schemas import BookingWebsiteTemplateId
from app.modules.websites.service import (
    BookingWebsiteService,
    PublicWebsiteRateLimiter,
    get_booking_website_service,
)

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"

APPROVED_TEMPLATE_IDS = [
    "luxe_studio",
    "minimal_elegance",
    "blush_beauty",
    "noir_salon",
    "organic_glow",
    "urban_chic",
    "editorial_pro",
    "classic_beauty",
]


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
        headers={"kid": "web-s2-key", "typ": "JWT"},
    )


def _build_env() -> Tuple[TestClient, ec.EllipticCurvePrivateKey, InMemorySalonRepository]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-test-web-s2",
    )
    verifier = SupabaseJWTVerifier(settings=settings, key_resolver=lambda _t, _h: pub)
    org_repo = InMemoryOrganizationRepository()
    org_svc = OrganizationService(repository=org_repo)
    ob_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    ob_svc = OnboardingService(repository=ob_repo)
    salon_repo = InMemorySalonRepository()
    web_repo = InMemoryBookingWebsiteRepository()
    web_svc = BookingWebsiteService(
        settings=settings,
        onboarding_service=ob_svc,
        website_repo=web_repo,
        salon_repo=salon_repo,
        rate_limiter=PublicWebsiteRateLimiter(max_requests=200, window_seconds=60),
    )

    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_svc
    app.dependency_overrides[get_onboarding_service] = lambda: ob_svc
    app.dependency_overrides[get_booking_website_service] = lambda: web_svc
    return TestClient(app), priv, salon_repo


def test_template_validation_and_persistence_without_resetting_branding() -> None:
    """All 8 approved templates persist cleanly; invalid template IDs are rejected (422)."""
    client, priv, _ = _build_env()
    owner = _make_jwt(priv, uuid4(), "owner@svario.ai")

    salon_id = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner}"},
        json={"name": "Royal Beauty Studio", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]

    # Invalid template ID -> 422
    bad_tpl = client.put(
        f"/api/v1/organizations/{salon_id}/booking-website",
        headers={"Authorization": f"Bearer {owner}"},
        json={"template_id": "../../etc/passwd"},
    )
    assert bad_tpl.status_code == 422

    # Save branding + logo first
    client.put(
        f"/api/v1/organizations/{salon_id}/booking-website",
        headers={"Authorization": f"Bearer {owner}"},
        json={
            "slug": "royal-beauty-studio",
            "headline": "Timeless Salon Craft",
            "tagline": "Luxury hair and botanical skincare.",
            "primary_color": "#C9A24B",
        },
    )
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    up = client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner}", "Content-Type": "image/png"},
        content=png_bytes,
    )
    assert up.status_code == 201

    # Switch across all 8 approved templates and confirm branding & logo survive intact
    assert [t.value for t in BookingWebsiteTemplateId] == APPROVED_TEMPLATE_IDS
    for tpl_id in APPROVED_TEMPLATE_IDS:
        res = client.put(
            f"/api/v1/organizations/{salon_id}/booking-website",
            headers={"Authorization": f"Bearer {owner}"},
            json={"template_id": tpl_id},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["template_id"] == tpl_id
        assert body["slug"] == "royal-beauty-studio"
        assert body["headline"] == "Timeless Salon Craft"
        assert body["primary_color"] == "#C9A24B"
        assert body["logo_path"] is not None


def test_public_slug_resolution_publish_unpublish_and_zero_private_leakage() -> None:
    """Draft slugs return 404; published slugs return allowlisted fields only; unpublish revokes access immediately."""
    client, priv, salon_repo = _build_env()
    owner_a = _make_jwt(priv, uuid4(), "owner-a@svario.ai")
    intruder_b = _make_jwt(priv, uuid4(), "intruder-b@svario.ai")

    salon_id = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"name": "Riya Women Salon", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]

    # Fetch onboarding bundle to get business_id and seed an active + inactive service
    bundle = client.get(
        f"/api/v1/organizations/{salon_id}/onboarding",
        headers={"Authorization": f"Bearer {owner_a}"},
    ).json()
    business_id = UUID(bundle["business_id"])
    now = datetime.now(timezone.utc)
    active_svc = SalonServiceResponse(
        id=uuid4(),
        organization_id=UUID(salon_id),
        business_id=business_id,
        name="Basic Haircut",
        category="Hair",
        description="Precision cut & blow dry",
        duration_minutes=30,
        price=299.0,
        currency="INR",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    inactive_svc = SalonServiceResponse(
        id=uuid4(),
        organization_id=UUID(salon_id),
        business_id=business_id,
        name="Internal Secret Treatment",
        category="Private",
        description="Should never be public",
        duration_minutes=60,
        price=999.0,
        currency="INR",
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    salon_repo._services[active_svc.id] = active_svc
    salon_repo._services[inactive_svc.id] = inactive_svc

    # Update profile + draft website + upload logo
    client.put(
        f"/api/v1/organizations/{salon_id}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={
            "display_name": "Riya Women Salon",
            "description": "Modern women's beauty studio",
            "phone": "+919876543210",
            "email": "hello@riyasalon.example",
            "city": "Mumbai",
            "timezone": "Asia/Kolkata",
        },
    )
    client.put(
        f"/api/v1/organizations/{salon_id}/booking-website",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={
            "slug": "riya-women-salon",
            "template_id": "blush_beauty",
            "headline": "Effortless Beauty, Personalized",
        },
    )
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x01" * 48
    client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner_a}", "Content-Type": "image/png"},
        content=png_bytes,
    )

    # 1. While DRAFT -> public route & public asset return 404
    assert client.get("/api/v1/public/websites/riya-women-salon").status_code == 404
    assert client.get("/api/v1/public/websites/riya-women-salon/assets/logo").status_code == 404

    # 2. Unknown & reserved slugs -> 404
    assert client.get("/api/v1/public/websites/does-not-exist").status_code == 404
    assert client.get("/api/v1/public/websites/dashboard").status_code == 404

    # 3. Cross-tenant intruder cannot publish -> 403
    assert (
        client.post(
            f"/api/v1/organizations/{salon_id}/booking-website/publish",
            headers={"Authorization": f"Bearer {intruder_b}"},
        ).status_code
        == 403
    )

    # 4. Owner publishes -> 200
    pub = client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/publish",
        headers={"Authorization": f"Bearer {owner_a}"},
    )
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
    assert pub.json()["published_at"] is not None

    # 5. Public endpoint now returns strictly allowlisted salon data
    public_resp = client.get("/api/v1/public/websites/riya-women-salon")
    assert public_resp.status_code == 200
    data = public_resp.json()
    assert data["slug"] == "riya-women-salon"
    assert data["template_id"] == "blush_beauty"
    assert data["business"]["display_name"] == "Riya Women Salon"
    assert data["logo_url"] == "/api/v1/public/websites/riya-women-salon/assets/logo"

    # Only ACTIVE services returned (never inactive)
    svc_names = [s["name"] for s in data["services"]]
    assert svc_names == ["Basic Haircut"]

    # Zero private/internal fields leaked
    forbidden_keys = {
        "organization_id",
        "business_id",
        "logo_path",
        "cover_image_path",
        "members",
        "customers",
        "appointments",
        "staff",
        "system_prompt",
        "escalation",
    }
    assert forbidden_keys.isdisjoint(set(data.keys()))

    # Public logo proxy serves PNG bytes cleanly with nosniff and no-store headers
    logo_resp = client.get("/api/v1/public/websites/riya-women-salon/assets/logo")
    assert logo_resp.status_code == 200
    assert logo_resp.headers["content-type"].startswith("image/png")
    assert logo_resp.headers["x-content-type-options"] == "nosniff"
    assert logo_resp.headers["cache-control"] == "no-store"
    assert logo_resp.content == png_bytes

    # 6. Owner unpublishes -> immediate 404 on public page & public asset, while data is preserved
    unpub = client.post(
        f"/api/v1/organizations/{salon_id}/booking-website/unpublish",
        headers={"Authorization": f"Bearer {owner_a}"},
    )
    assert unpub.status_code == 200
    assert unpub.json()["status"] == "draft"
    assert unpub.json()["logo_path"] is not None  # asset preserved

    assert client.get("/api/v1/public/websites/riya-women-salon").status_code == 404
    assert client.get("/api/v1/public/websites/riya-women-salon/assets/logo").status_code == 404


def test_asset_path_validation_cross_tenant_denial_and_missing_assistant_resilience() -> None:
    """Reject traversal/nested/cross-tenant asset paths and survive missing assistant_settings."""
    org_a, biz_a = uuid4(), uuid4()
    org_b, biz_b = uuid4(), uuid4()

    valid_logo = f"{org_a}/{biz_a}/logo-0123456789ab.png"
    valid_cover = f"{org_a}/{biz_a}/cover-abcdef012345.webp"
    assert is_valid_brand_asset_path(valid_logo, asset_type="logo", organization_id=org_a, business_id=biz_a)
    assert is_valid_brand_asset_path(valid_cover, asset_type="cover", organization_id=org_a, business_id=biz_a)

    # Reject wrong asset type, cross-tenant prefix, traversal, nested folders, or bad extension
    assert not is_valid_brand_asset_path(valid_logo, asset_type="cover", organization_id=org_a, business_id=biz_a)
    assert not is_valid_brand_asset_path(valid_logo, asset_type="logo", organization_id=org_b, business_id=biz_b)
    assert not is_valid_brand_asset_path(f"{org_a}/{biz_a}/../{biz_b}/logo-0123456789ab.png")
    assert not is_valid_brand_asset_path(f"{org_a}/{biz_a}/nested/logo-0123456789ab.png")
    assert not is_valid_brand_asset_path(f"{org_a}/{biz_a}/logo-0123456789ab.svg")

    # End-to-end: missing assistant_settings row must not crash public resolver,
    # and a cross-tenant logo_path injected into storage must return 404 via proxy.
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-test-web-s2-hardening",
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
        rate_limiter=PublicWebsiteRateLimiter(max_requests=200, window_seconds=60),
    )
    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_svc
    app.dependency_overrides[get_onboarding_service] = lambda: ob_svc
    app.dependency_overrides[get_booking_website_service] = lambda: web_svc
    client = TestClient(app)

    owner_a = _make_jwt(priv, uuid4(), "owner-a2@svario.ai")
    owner_b = _make_jwt(priv, uuid4(), "owner-b2@svario.ai")

    salon_a = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"name": "Aura Hair Studio", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]
    salon_b = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_b}"},
        json={"name": "Velvet Salon", "industry": "salon", "timezone": "Asia/Kolkata"},
    ).json()["id"]

    bundle_a = client.get(
        f"/api/v1/organizations/{salon_a}/onboarding",
        headers={"Authorization": f"Bearer {owner_a}"},
    ).json()
    biz_a_id = UUID(bundle_a["business_id"])

    client.put(
        f"/api/v1/organizations/{salon_a}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"display_name": "Aura Hair Studio", "phone": "+919999988888", "timezone": "Asia/Kolkata"},
    )
    client.put(
        f"/api/v1/organizations/{salon_a}/booking-website",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={"slug": "aura-hair-studio", "template_id": "editorial_pro"},
    )
    client.post(
        f"/api/v1/organizations/{salon_a}/booking-website/publish",
        headers={"Authorization": f"Bearer {owner_a}"},
    )

    # Remove assistant_settings row completely -> public website must still return 200
    ob_repo._assistant.pop(biz_a_id, None)
    resp = client.get("/api/v1/public/websites/aura-hair-studio")
    assert resp.status_code == 200
    assert resp.json()["receptionist"]["enabled"] is False
    assert resp.json()["receptionist"]["assistant_name"] is None

    # Inject a cross-tenant path into salon A's record -> proxy must deny with 404
    foreign_path = f"{salon_b}/{uuid4()}/logo-abcdef012345.png"
    web_repo._assets[foreign_path] = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    web_repo._records_by_business[biz_a_id]["logo_path"] = foreign_path
    assert client.get("/api/v1/public/websites/aura-hair-studio/assets/logo").status_code == 404

    # Cross-tenant slug check against salon A's org endpoint is forbidden (403)
    assert (
        client.get(
            f"/api/v1/organizations/{salon_a}/booking-website/slug-availability?slug=aura-hair-studio",
            headers={"Authorization": f"Bearer {owner_b}"},
        ).status_code
        == 403
    )


def test_stage2_migration_sql_security_invariants() -> None:
    """Verify hardened Stage 2 SQL enforces zero anon Storage policies, strict search_path, and safe RPC grants."""
    sql_path = (
        Path(__file__).resolve().parents[3]
        / "supabase"
        / "migrations"
        / "20261124000009_stage8_booking_website_templates_and_public_rpc.sql"
    )
    sql = sql_path.read_text(encoding="utf-8")

    # 1. Zero anonymous SELECT policy on storage.objects
    assert "CREATE POLICY salon_brand_assets_select_published_anon" not in sql
    assert "FOR SELECT TO anon" not in sql
    assert "DROP POLICY IF EXISTS salon_brand_assets_select_published_anon ON storage.objects;" in sql
    assert "DROP FUNCTION IF EXISTS public.is_published_brand_asset(TEXT);" in sql

    # 2. Public slug RPC returns booleans has_logo/has_cover, NEVER raw logo_path/cover_image_path
    assert "'has_logo', v_config.has_logo" in sql
    assert "'has_cover', v_config.has_cover" in sql
    assert "'logo_path', v_config.logo_path" not in sql
    assert "'cover_image_path', v_config.cover_image_path" not in sql

    # 3. PL/pgSQL unassigned RECORD bug fixed
    assert "v_assistant RECORD;" not in sql
    assert "v_assistant_enabled BOOLEAN := FALSE;" in sql

    # 4. Strict search_path = '' on all SECURITY DEFINER functions (never search_path = public)
    assert "SET search_path = public" not in sql
    assert sql.count("SECURITY DEFINER\nSET search_path = ''") == 3

    # 5. Slug exclusion checks caller org membership
    assert "public.is_org_member(b.organization_id)" in sql

    # 6. Service-role-only asset path resolver revokes PUBLIC, anon, authenticated
    assert "REVOKE ALL ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) FROM PUBLIC;" in sql
    assert "REVOKE ALL ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) FROM anon;" in sql
    assert "REVOKE ALL ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) FROM authenticated;" in sql
    assert "GRANT EXECUTE ON FUNCTION public.get_published_brand_asset_path(TEXT, TEXT) TO service_role;" in sql

    # 7. Strict regex asset-path CHECK constraint (not permissive LIKE)
    assert "chk_booking_website_configs_asset_paths" in sql
    assert "/logo-[0-9a-f]{12}\\.(png|jpg|webp)$" in sql
    assert "/cover-[0-9a-f]{12}\\.(png|jpg|webp)$" in sql

