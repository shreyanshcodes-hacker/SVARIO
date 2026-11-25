"""Security Remediation Stage 2 Tests — M1 (Trusted Proxy IP) & M2 (Bounded Asset Uploads)."""

from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.client_ip import resolve_client_ip
from app.core.config import Settings, get_settings
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.organizations.service import OrganizationService, get_organization_service
from app.modules.voice.public_access import PublicVoicePolicyRegistry, mint_public_voice_token
from app.modules.voice.rate_limit import VoiceSessionRateLimiter
from app.modules.voice.service import VoiceSessionService, get_voice_session_service
from app.modules.websites.repository import InMemoryBookingWebsiteRepository
from app.modules.websites.service import (
    BookingWebsiteService,
    MAX_BRAND_ASSET_BYTES,
    PublicWebsiteRateLimiter,
    get_booking_website_service,
)
from app.routes.websites import read_bounded_body


def _make_request(
    *,
    client_host: Optional[str] = "198.51.100.10",
    headers: Optional[List[Tuple[bytes, bytes]]] = None,
) -> Request:
    scope: Dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }
    if client_host is not None:
        scope["client"] = (client_host, 12345)
    return Request(scope)


# =============================================================================
# PART A — M1: Trusted Proxy IP Extraction & Rate Limiter Integration
# =============================================================================


def test_m1_trusted_proxies_config_validation() -> None:
    ok = Settings(TRUSTED_PROXIES="10.0.0.1, 172.16.0.0/12, ::1, fd00::/8")
    assert len(ok.trusted_proxy_networks) == 4

    with pytest.raises(ValueError):
        Settings(TRUSTED_PROXIES="10.0.0.1, not-an-ip-or-cidr")


def test_m1_direct_and_untrusted_peer_ignore_xff() -> None:
    settings = Settings(TRUSTED_PROXIES="10.0.0.0/8")

    # Direct request without XFF
    req_direct = _make_request(client_host="203.0.113.5")
    assert resolve_client_ip(req_direct, settings) == "203.0.113.5"

    # Untrusted peer spoofing XFF must be ignored
    req_spoof = _make_request(
        client_host="203.0.113.5",
        headers=[(b"x-forwarded-for", b"198.51.100.99, 10.0.0.2")],
    )
    assert resolve_client_ip(req_spoof, settings) == "203.0.113.5"


def test_m1_trusted_proxy_single_hop_multihop_ipv6_and_spoofed_leftmost() -> None:
    settings = Settings(TRUSTED_PROXIES="10.0.0.0/8, 172.16.0.1, fd00::/8")

    # Single forwarded IPv4
    req_v4 = _make_request(
        client_host="10.1.2.3",
        headers=[(b"x-forwarded-for", b"198.51.100.42")],
    )
    assert resolve_client_ip(req_v4, settings) == "198.51.100.42"

    # Single forwarded IPv6
    req_v6 = _make_request(
        client_host="fd00::10",
        headers=[(b"x-forwarded-for", b"2001:db8::1")],
    )
    assert resolve_client_ip(req_v6, settings) == "2001:db8::1"

    # Multi-hop chain with trusted proxies on the right
    req_chain = _make_request(
        client_host="10.0.0.5",
        headers=[(b"x-forwarded-for", b"198.51.100.77, 172.16.0.1, 10.0.0.2")],
    )
    assert resolve_client_ip(req_chain, settings) == "198.51.100.77"

    # Spoofed leftmost values ignored when right-to-left walk finds first untrusted hop
    req_spoof_left = _make_request(
        client_host="10.0.0.5",
        headers=[(b"x-forwarded-for", b"garbage-spoof, 1.1.1.1, 198.51.100.88, 10.0.0.9")],
    )
    assert resolve_client_ip(req_spoof_left, settings) == "198.51.100.88"


def test_m1_malformed_empty_and_missing_client_fail_safely() -> None:
    settings = Settings(TRUSTED_PROXIES="10.0.0.0/8")

    # Missing client
    req_missing = _make_request(client_host=None)
    assert resolve_client_ip(req_missing, settings) == "unknown"

    # Empty XFF from trusted proxy falls back to immediate peer
    req_empty = _make_request(
        client_host="10.0.0.5",
        headers=[(b"x-forwarded-for", b"   ")],
    )
    assert resolve_client_ip(req_empty, settings) == "10.0.0.5"

    # Malformed IP at first untrusted hop falls back to immediate peer
    req_bad_hop = _make_request(
        client_host="10.0.0.5",
        headers=[(b"x-forwarded-for", b"not-an-ip, 10.0.0.2")],
    )
    assert resolve_client_ip(req_bad_hop, settings) == "10.0.0.5"

    # All hops trusted falls back to immediate peer
    req_all_trusted = _make_request(
        client_host="10.0.0.5",
        headers=[(b"x-forwarded-for", b"10.0.0.1, 10.0.0.2")],
    )
    assert resolve_client_ip(req_all_trusted, settings) == "10.0.0.5"


def _build_m1_m2_test_app(
    *,
    trusted_proxies: str = "",
    public_rate_limit: int = 2,
    voice_rate_limit: int = 2,
) -> tuple[TestClient, str, str, InMemoryBookingWebsiteRepository]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    issuer = "https://test-project.supabase.co/auth/v1"
    audience = "authenticated"

    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=issuer,
        SUPABASE_JWT_AUDIENCE=audience,
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-proj-test-key-m1-m2-123456",
        VOICE_SESSION_RATE_LIMIT_PER_MINUTE=voice_rate_limit,
        VOICE_PUBLIC_TOKEN_SECRET="stage2-security-test-hmac-secret-1234567890",
        TRUSTED_PROXIES=trusted_proxies,
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
        rate_limiter=PublicWebsiteRateLimiter(max_requests=public_rate_limit, window_seconds=60),
    )

    async def _mock_mint(_cfg: Settings, _payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"value": "ek_test", "expires_at": int((datetime.now(timezone.utc) + timedelta(minutes=2)).timestamp())}

    voice_service = VoiceSessionService(
        settings=settings,
        onboarding_service=onboarding_service,
        rate_limiter=VoiceSessionRateLimiter(window_seconds=60),
        public_registry=PublicVoicePolicyRegistry(),
        upstream_mint=_mock_mint,
    )

    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_service
    app.dependency_overrides[get_onboarding_service] = lambda: onboarding_service
    app.dependency_overrides[get_booking_website_service] = lambda: website_service
    app.dependency_overrides[get_voice_session_service] = lambda: voice_service

    client = TestClient(app)

    owner_id = uuid4()
    now = datetime.now(timezone.utc)
    owner_jwt = jwt.encode(
        {
            "sub": str(owner_id),
            "email": "owner@svario.ai",
            "role": "authenticated",
            "iss": issuer,
            "aud": audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "user_metadata": {"full_name": "Salon Owner", "email_verified": True},
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "k1", "typ": "JWT"},
    )

    org_resp = client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_jwt}"},
        json={"name": "M1 M2 Salon", "industry": OrganizationIndustry.SALON.value},
    )
    assert org_resp.status_code == 201
    org_id = org_resp.json()["id"]

    # Complete minimal profile + hours + publish website
    client.put(
        f"/api/v1/organizations/{org_id}/onboarding/profile",
        headers={"Authorization": f"Bearer {owner_jwt}"},
        json={"display_name": "M1 M2 Salon", "phone": "+919876543210", "timezone": "Asia/Kolkata"},
    )
    client.put(
        f"/api/v1/organizations/{org_id}/onboarding/hours",
        headers={"Authorization": f"Bearer {owner_jwt}"},
        json={
            "timezone": "Asia/Kolkata",
            "schedule": [
                {"weekday": 1, "is_closed": False, "opens_at": "10:00", "closes_at": "20:00", "is_overnight": False}
            ],
        },
    )
    cfg = client.get(
        f"/api/v1/organizations/{org_id}/booking-website",
        headers={"Authorization": f"Bearer {owner_jwt}"},
    ).json()
    slug = cfg["slug"]
    pub = client.post(
        f"/api/v1/organizations/{org_id}/booking-website/publish",
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert pub.status_code == 200

    return client, owner_jwt, org_id, website_repo


def test_m1_rotating_xff_cannot_bypass_public_website_or_voice_rate_limits() -> None:
    client, owner_jwt, org_id, _ = _build_m1_m2_test_app(
        trusted_proxies="",
        public_rate_limit=2,
        voice_rate_limit=2,
    )

    # Public website endpoint: rotating XFF must still hit 429 on 3rd request
    cfg = client.get(
        f"/api/v1/organizations/{org_id}/booking-website",
        headers={"Authorization": f"Bearer {owner_jwt}"},
    ).json()
    slug = cfg["slug"]

    r1 = client.get(f"/api/v1/public/websites/{slug}", headers={"X-Forwarded-For": "198.51.100.1"})
    r2 = client.get(f"/api/v1/public/websites/{slug}", headers={"X-Forwarded-For": "198.51.100.2"})
    r3 = client.get(f"/api/v1/public/websites/{slug}", headers={"X-Forwarded-For": "198.51.100.3"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429

    # Voice session endpoint: rotating XFF must still hit 429 on 3rd request
    v1 = client.post(
        "/api/v1/voice/sessions",
        headers={"Authorization": f"Bearer {owner_jwt}", "X-Forwarded-For": "203.0.113.1"},
        json={"organization_id": org_id},
    )
    v2 = client.post(
        "/api/v1/voice/sessions",
        headers={"Authorization": f"Bearer {owner_jwt}", "X-Forwarded-For": "203.0.113.2"},
        json={"organization_id": org_id},
    )
    v3 = client.post(
        "/api/v1/voice/sessions",
        headers={"Authorization": f"Bearer {owner_jwt}", "X-Forwarded-For": "203.0.113.3"},
        json={"organization_id": org_id},
    )
    assert v1.status_code == 201
    assert v2.status_code == 201
    assert v3.status_code == 429


# =============================================================================
# PART B — M2: Bounded Asset Uploads
# =============================================================================


class _CountingStreamRequest:
    """Minimal Request stand-in to prove early termination without buffering oversized streams."""

    def __init__(self, chunks: List[bytes], content_length: Optional[str] = None) -> None:
        self._chunks = chunks
        self.chunks_read = 0
        self.bytes_read = 0
        self.headers: Dict[str, str] = {}
        if content_length is not None:
            self.headers["content-length"] = content_length

    async def stream(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            self.chunks_read += 1
            self.bytes_read += len(chunk)
            yield chunk


@pytest.mark.asyncio
async def test_m2_read_bounded_body_stops_immediately_without_buffering_oversized() -> None:
    # 1. Advertised Content-Length > 2 MB fails before reading any stream chunk
    req_cl = _CountingStreamRequest(
        chunks=[b"x" * 1024],
        content_length=str(MAX_BRAND_ASSET_BYTES + 1),
    )
    with pytest.raises(HTTPException) as exc_cl:
        await read_bounded_body(req_cl)  # type: ignore[arg-type]
    assert exc_cl.value.status_code == 413
    assert req_cl.chunks_read == 0
    assert req_cl.bytes_read == 0

    # 2. Missing Content-Length with 100 x 64 KiB chunks (6.4 MB) stops at chunk 33 (just over 2 MB)
    chunk_64k = b"a" * (64 * 1024)
    req_chunked = _CountingStreamRequest(chunks=[chunk_64k] * 100, content_length=None)
    with pytest.raises(HTTPException) as exc_chunked:
        await read_bounded_body(req_chunked)  # type: ignore[arg-type]
    assert exc_chunked.value.status_code == 413
    assert req_chunked.chunks_read == 33  # 32 * 64 KiB == 2 MiB; 33rd chunk triggers immediate 413
    assert req_chunked.chunks_read < 100

    # 3. Falsified small Content-Length with oversized stream still aborts at 413
    req_falsified = _CountingStreamRequest(chunks=[chunk_64k] * 40, content_length="1024")
    with pytest.raises(HTTPException) as exc_falsified:
        await read_bounded_body(req_falsified)  # type: ignore[arg-type]
    assert exc_falsified.value.status_code == 413
    assert req_falsified.chunks_read == 33


def test_m2_endpoint_upload_exact_2mb_and_oversized_413_no_storage_write() -> None:
    client, owner_jwt, org_id, website_repo = _build_m1_m2_test_app()
    png_header = b"\x89PNG\r\n\x1a\n"

    # Valid upload below 2 MB
    small_png = png_header + b"\x00" * 128
    res_small = client.post(
        f"/api/v1/organizations/{org_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/png"},
        content=small_png,
    )
    assert res_small.status_code == 201
    initial_asset_count = len(website_repo._assets)

    # Upload at exactly 2 MB succeeds
    exact_2mb_png = png_header + b"\x00" * (MAX_BRAND_ASSET_BYTES - len(png_header))
    assert len(exact_2mb_png) == MAX_BRAND_ASSET_BYTES
    res_exact = client.post(
        f"/api/v1/organizations/{org_id}/booking-website/assets/cover",
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/png"},
        content=exact_2mb_png,
    )
    assert res_exact.status_code == 201
    assert len(website_repo._assets) == initial_asset_count + 1

    # Oversized upload (2 MB + 1 byte) returns 413 and does NOT write to storage
    oversized_png = png_header + b"\x00" * (MAX_BRAND_ASSET_BYTES + 1 - len(png_header))
    res_over = client.post(
        f"/api/v1/organizations/{org_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/png"},
        content=oversized_png,
    )
    assert res_over.status_code == 413
    assert len(website_repo._assets) == initial_asset_count + 1

    # Invalid MIME and magic bytes still rejected with 400
    res_bad_mime = client.post(
        f"/api/v1/organizations/{org_id}/booking-website/assets/logo",
        headers={"Authorization": f"Bearer {owner_jwt}", "Content-Type": "image/svg+xml"},
        content=b"<svg/>",
    )
    assert res_bad_mime.status_code == 400
