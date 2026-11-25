"""Focused regression tests for Salon Brand Asset Upload (valid, invalid MIME, oversized, unauthorized, and Supabase error surfacing)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.core.auth import AuthenticatedUser, SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings, get_settings
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import OrganizationIndustry, OrganizationRole
from app.modules.organizations.service import OrganizationService, get_organization_service
from app.modules.websites.repository import (
    InMemoryBookingWebsiteRepository,
    SupabaseRestBookingWebsiteRepository,
)
from app.modules.websites.service import (
    BookingWebsiteService,
    MAX_BRAND_ASSET_BYTES,
    PublicWebsiteRateLimiter,
    get_booking_website_service,
)


def _build_upload_test_app() -> tuple[TestClient, str, str, str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    issuer = "https://test-project.supabase.co/auth/v1"
    audience = "authenticated"

    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=issuer,
        SUPABASE_JWT_AUDIENCE=audience,
        SUPABASE_JWT_ALGORITHMS="ES256",
    )
    verifier = SupabaseJWTVerifier(settings=settings, key_resolver=lambda _t, _h: public_key)
    org_repo = InMemoryOrganizationRepository()
    org_service = OrganizationService(repository=org_repo)
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    onboarding_service = OnboardingService(repository=onboarding_repo)
    website_repo = InMemoryBookingWebsiteRepository()
    website_service = BookingWebsiteService(
        settings=settings,
        onboarding_service=onboarding_service,
        website_repo=website_repo,
        rate_limiter=PublicWebsiteRateLimiter(max_requests=100, window_seconds=60),
    )

    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_service
    app.dependency_overrides[get_onboarding_service] = lambda: onboarding_service
    app.dependency_overrides[get_booking_website_service] = lambda: website_service
    client = TestClient(app)

    def _mint_jwt(uid: str, email: str) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": uid,
                "email": email,
                "role": "authenticated",
                "iss": issuer,
                "aud": audience,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=30)).timestamp()),
                "user_metadata": {"full_name": email, "email_verified": True},
            },
            private_key,
            algorithm="ES256",
            headers={"kid": "k1", "typ": "JWT"},
        )

    owner_jwt = _mint_jwt(str(uuid4()), "owner@svario.ai")
    outsider_jwt = _mint_jwt(str(uuid4()), "outsider@svario.ai")
    staff_uid = uuid4()
    staff_jwt = _mint_jwt(str(staff_uid), "staff@svario.ai")

    org_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_jwt}"},
        json={"name": "Upload Test Salon", "industry": OrganizationIndustry.SALON.value},
    )
    assert org_resp.status_code == 201
    org_id = org_resp.json()["id"]

    # Add non-admin staff member directly to org_repo to test RBAC
    org_repo._members.setdefault(org_id, {})  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/organizations/{org_id}/members",
        headers={"Authorization": f"Bearer {owner_jwt}"},
        json={"user_id": str(staff_uid), "role": OrganizationRole.STAFF.value},
    )

    return client, org_id, owner_jwt, staff_jwt, outsider_jwt


def test_brand_asset_upload_success_invalid_oversized_and_unauthorized() -> None:
    client, org_id, owner_jwt, staff_jwt, outsider_jwt = _build_upload_test_app()
    url = f"/api/v1/organizations/{org_id}/booking-website/assets/logo"
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128

    # 1. Successful PNG upload by owner
    ok = client.post(
        url,
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/png"},
        content=png_bytes,
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["asset_type"] == "logo"
    assert body["storage_path"].startswith(f"{org_id}/")
    assert body["public_url"]

    # 2. Unsupported file type (SVG) rejected with 400
    svg = client.post(
        url,
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/svg+xml"},
        content=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
    )
    assert svg.status_code == 400
    assert "PNG, JPEG, or WEBP" in svg.json()["message"]

    # 3. Spoofed magic bytes rejected with 400
    spoof = client.post(
        url,
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/png"},
        content=b"not-a-real-png",
    )
    assert spoof.status_code == 400

    # 4. Oversized file (> 2 MB) rejected with 413
    oversized = client.post(
        url,
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/png"},
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_BRAND_ASSET_BYTES,
    )
    assert oversized.status_code == 413

    # 5. Unauthenticated request rejected with 401
    unauth = client.post(url, headers={"Content-Type": "image/png"}, content=png_bytes)
    assert unauth.status_code == 401

    # 6. Outsider organisation access rejected with 403
    outsider = client.post(
        url,
        headers={"Authorization": f"Bearer {outsider_jwt}", "Content-Type": "image/png"},
        content=png_bytes,
    )
    assert outsider.status_code == 403

    # 7. Non-admin staff member rejected with 403
    staff = client.post(
        url,
        headers={"Authorization": f"Bearer {staff_jwt}", "Content-Type": "image/png"},
        content=png_bytes,
    )
    assert staff.status_code == 403


@pytest.mark.asyncio
async def test_supabase_storage_error_includes_descriptive_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_ANON_KEY="test-anon-key",
    )
    repo = SupabaseRestBookingWebsiteRepository(settings=settings)
    actor = AuthenticatedUser(
        id=uuid4(),
        issuer="https://test-project.supabase.co/auth/v1",
        audience="authenticated",
        raw_token="fake-jwt",
    )

    class _MockAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "_MockAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                400,
                json={"statusCode": "403", "error": "Unauthorized", "message": "new row violates row-level security policy"},
            )

    monkeypatch.setattr("app.modules.websites.repository.httpx.AsyncClient", _MockAsyncClient)

    with pytest.raises(HTTPException) as exc:
        await repo.upload_brand_asset(
            actor=actor,
            organization_id=uuid4(),
            business_id=uuid4(),
            storage_path="org/biz/logo-1234567890ab.png",
            content_type="image/png",
            data=b"\x89PNG\r\n\x1a\n",
        )
    assert exc.value.status_code == 502
    assert "Brand asset upload failed (HTTP 400): new row violates row-level security policy." == exc.value.detail
