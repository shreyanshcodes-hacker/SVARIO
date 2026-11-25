"""Security Remediation Stage 1 Tests — H1 (Production HMAC Secret) & H2 (CORS Hardening)."""

from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import ALLOWED_CORS_HEADERS, create_app
from app.modules.voice.public_access import (
    FALLBACK_DEV_HMAC_KEY,
    _resolve_signing_secret,
    mint_public_voice_token,
    verify_public_voice_token,
)

VALID_PROD_SECRET = "prod-svario-public-voice-hmac-secret-9f8e7d6c5b4a3210"
LIVE_SUPABASE_URL = "https://prod-project.supabase.co"
LIVE_SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.live-anon-key"


def _make_prod_settings(**overrides: object) -> Settings:
    base = {
        "SVARIO_ENV": "production",
        "SUPABASE_URL": LIVE_SUPABASE_URL,
        "SUPABASE_ANON_KEY": LIVE_SUPABASE_ANON,
        "CORS_ORIGINS": "https://app.svario.ai,https://www.svario.ai",
        "VOICE_PUBLIC_TOKEN_SECRET": VALID_PROD_SECRET,
        "UPSTASH_REDIS_REST_URL": "https://test-upstash.upstash.io",
        "UPSTASH_REDIS_REST_TOKEN": "test-upstash-rest-token-stage1",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


# =============================================================================
# PART A — H1: Production HMAC Secret Enforcement
# =============================================================================


def test_h1_production_accepts_valid_dedicated_secret_and_verifies_tokens() -> None:
    settings = _make_prod_settings(SVARIO_ENV="  Production ")
    assert settings.is_production is True

    app = create_app(settings=settings)
    assert app is not None
    assert _resolve_signing_secret(settings) == VALID_PROD_SECRET.encode("utf-8")

    org_id = uuid4()
    biz_id = uuid4()
    token, _, _ = mint_public_voice_token(
        settings=settings,
        organization_id=org_id,
        business_id=biz_id,
        ttl_seconds=120,
    )
    claims = verify_public_voice_token(
        settings=settings,
        token=token,
        expected_organization_id=org_id,
        expected_business_id=biz_id,
    )
    assert claims.organization_id == org_id
    assert claims.business_id == biz_id


@pytest.mark.parametrize(
    "bad_secret",
    [
        None,
        "",
        "   \t\n  ",
        FALLBACK_DEV_HMAC_KEY,
        "my-placeholder-secret-value-that-is-very-long-123456",
        "your-super-secret-voice-token-key-here-1234567890",
        "too-short-secret-12345",
    ],
)
def test_h1_production_rejects_missing_weak_placeholder_or_fallback_secret(
    bad_secret: object,
) -> None:
    settings = _make_prod_settings(VOICE_PUBLIC_TOKEN_SECRET=bad_secret)

    with pytest.raises(RuntimeError) as startup_exc:
        create_app(settings=settings)
    if isinstance(bad_secret, str) and bad_secret.strip():
        assert bad_secret.strip() not in str(startup_exc.value)

    with pytest.raises(RuntimeError) as resolver_exc:
        _resolve_signing_secret(settings)
    if isinstance(bad_secret, str) and bad_secret.strip():
        assert bad_secret.strip() not in str(resolver_exc.value)


def test_h1_production_never_falls_back_to_supabase_jwt_secret() -> None:
    settings = _make_prod_settings(
        VOICE_PUBLIC_TOKEN_SECRET=None,
        SUPABASE_JWT_SECRET="super-long-supabase-jwt-secret-that-must-not-be-used-for-public-voice",
    )
    with pytest.raises(RuntimeError):
        create_app(settings=settings)
    with pytest.raises(RuntimeError):
        _resolve_signing_secret(settings)


def test_h1_development_preserves_fallback_behavior() -> None:
    dev_default = Settings(
        SVARIO_ENV="development",
        VOICE_PUBLIC_TOKEN_SECRET=None,
        SUPABASE_JWT_SECRET=None,
    )
    assert dev_default.is_production is False
    assert _resolve_signing_secret(dev_default) == FALLBACK_DEV_HMAC_KEY.encode("utf-8")

    dev_jwt = Settings(
        SVARIO_ENV="development",
        VOICE_PUBLIC_TOKEN_SECRET=None,
        SUPABASE_JWT_SECRET="dev-jwt-secret-fallback",
    )
    assert _resolve_signing_secret(dev_jwt) == b"dev-jwt-secret-fallback"


def test_h1_rejects_tampered_token_payload_and_invalid_signature() -> None:
    settings = _make_prod_settings()
    org_id = uuid4()
    biz_id = uuid4()
    token, _, _ = mint_public_voice_token(
        settings=settings,
        organization_id=org_id,
        business_id=biz_id,
    )
    prefix, payload_b64, sig_b64 = token.split(".")

    # Tamper signature
    bad_sig = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
    with pytest.raises(HTTPException) as sig_exc:
        verify_public_voice_token(
            settings=settings,
            token=f"{prefix}.{payload_b64}.{bad_sig}",
            expected_organization_id=org_id,
            expected_business_id=biz_id,
        )
    assert sig_exc.value.status_code == 403

    # Tamper payload
    bad_payload = ("A" if payload_b64[0] != "A" else "B") + payload_b64[1:]
    with pytest.raises(HTTPException) as payload_exc:
        verify_public_voice_token(
            settings=settings,
            token=f"{prefix}.{bad_payload}.{sig_b64}",
            expected_organization_id=org_id,
            expected_business_id=biz_id,
        )
    assert payload_exc.value.status_code == 403


# =============================================================================
# PART B — H2: Production CORS Hardening
# =============================================================================


def test_h2_production_allows_approved_origin_and_blocks_unapproved_and_localhost() -> None:
    settings = _make_prod_settings(
        CORS_ORIGINS="https://app.svario.ai, https://www.svario.ai, *",
    )
    client = TestClient(create_app(settings=settings))

    # Approved production frontend origin
    res_ok = client.get("/health", headers={"Origin": "https://app.svario.ai"})
    assert res_ok.status_code == 200
    assert res_ok.headers.get("access-control-allow-origin") == "https://app.svario.ai"
    assert res_ok.headers.get("access-control-allow-credentials") == "true"

    # Unapproved origin must not receive ACAO
    res_evil = client.get("/health", headers={"Origin": "https://evil.example"})
    assert res_evil.status_code == 200
    assert "access-control-allow-origin" not in res_evil.headers

    # Localhost must be rejected in production
    res_local = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert res_local.status_code == 200
    assert "access-control-allow-origin" not in res_local.headers

    # Wildcard must never be reflected with credentials
    res_other = client.get("/health", headers={"Origin": "https://random.example"})
    assert res_other.headers.get("access-control-allow-origin") != "*"


def test_h2_development_preserves_localhost_cors() -> None:
    dev_settings = Settings(SVARIO_ENV="development")
    client = TestClient(create_app(settings=dev_settings))

    for local_origin in ("http://localhost:3000", "http://127.0.0.1:5173"):
        res = client.get("/health", headers={"Origin": local_origin})
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == local_origin
        assert res.headers.get("access-control-allow-credentials") == "true"


def test_h2_preflight_options_enforces_explicit_allowlisted_headers() -> None:
    settings = _make_prod_settings()
    client = TestClient(create_app(settings=settings))

    # Approved preflight headers
    preflight_ok = client.options(
        "/api/v1/public/websites/riya-salon/voice/sessions",
        headers={
            "Origin": "https://app.svario.ai",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type, Accept, X-Webhook-Secret",
        },
    )
    assert preflight_ok.status_code == 200
    assert preflight_ok.headers.get("access-control-allow-origin") == "https://app.svario.ai"
    allowed_hdrs = {
        h.strip().lower()
        for h in preflight_ok.headers.get("access-control-allow-headers", "").split(",")
        if h.strip()
    }
    for expected in ALLOWED_CORS_HEADERS:
        assert expected.lower() in allowed_hdrs

    # Disallowed header must be rejected by CORSMiddleware
    preflight_bad = client.options(
        "/api/v1/public/websites/riya-salon/voice/sessions",
        headers={
            "Origin": "https://app.svario.ai",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Disallowed-Header",
        },
    )
    assert preflight_bad.status_code == 400

    # Localhost preflight in production must be rejected
    preflight_local = client.options(
        "/api/v1/public/websites/riya-salon/voice/sessions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert preflight_local.status_code == 400
