"""Tests for Stage 1 FastAPI JWT Authentication (ES256 asymmetric JWKS & edge cases)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict
from uuid import UUID, uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings
from app.main import create_app

TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_KID = "svario-test-es256-key-1"


@pytest.fixture(scope="module")
def es256_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    """Generate a fresh EC P-256 keypair for asymmetric ES256 JWT tests."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture
def auth_client(
    es256_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> TestClient:
    """Create a FastAPI TestClient wired with an asymmetric ES256 verifier."""
    _, public_key = es256_keypair
    settings = Settings(
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER=TEST_ISSUER,
        SUPABASE_JWT_AUDIENCE=TEST_AUDIENCE,
        SUPABASE_JWT_ALGORITHMS="ES256",
    )

    def key_resolver(_token: str, header: Dict[str, Any]) -> Any:
        if header.get("kid") != TEST_KID:
            raise jwt.InvalidTokenError("Unknown key ID")
        return public_key

    verifier = SupabaseJWTVerifier(settings=settings, key_resolver=key_resolver)
    app = create_app()
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    return TestClient(app)


def make_es256_token(
    private_key: ec.EllipticCurvePrivateKey,
    *,
    sub: str | None = None,
    email: str = "founder@svario.ai",
    role: str = "authenticated",
    iss: str = TEST_ISSUER,
    aud: str = TEST_AUDIENCE,
    expires_delta: timedelta = timedelta(minutes=15),
    kid: str = TEST_KID,
    full_name: str = "Aarav Mehta",
) -> str:
    """Create a signed ES256 JWT for testing."""
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "role": role,
        "email": email,
        "session_id": str(uuid4()),
        "user_metadata": {
            "full_name": full_name,
            "email_verified": True,
        },
    }
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(
        payload,
        private_key,
        algorithm="ES256",
        headers={"kid": kid, "typ": "JWT"},
    )


def test_missing_token_rejected_with_401(auth_client: TestClient) -> None:
    """Unauthenticated request to GET /api/v1/auth/me must return HTTP 401."""
    response = auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["status_code"] == 401


def test_invalid_signature_token_rejected_with_401(auth_client: TestClient) -> None:
    """Token signed by an untrusted private key must be rejected with HTTP 401."""
    rogue_private_key = ec.generate_private_key(ec.SECP256R1())
    forged_token = make_es256_token(rogue_private_key, sub=str(uuid4()))

    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert response.status_code == 401


def test_expired_token_rejected_with_401(
    auth_client: TestClient,
    es256_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    """Expired JWT must be rejected with HTTP 401."""
    private_key, _ = es256_keypair
    expired_token = make_es256_token(
        private_key,
        sub=str(uuid4()),
        expires_delta=timedelta(minutes=-10),
    )

    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["message"].lower()


def test_invalid_issuer_and_audience_rejected_with_401(
    auth_client: TestClient,
    es256_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    """Tokens with wrong issuer or wrong audience must be rejected with HTTP 401."""
    private_key, _ = es256_keypair

    wrong_iss_token = make_es256_token(
        private_key,
        sub=str(uuid4()),
        iss="https://evil-project.supabase.co/auth/v1",
    )
    resp_iss = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_iss_token}"},
    )
    assert resp_iss.status_code == 401

    wrong_aud_token = make_es256_token(
        private_key,
        sub=str(uuid4()),
        aud="anon",
    )
    resp_aud = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {wrong_aud_token}"},
    )
    assert resp_aud.status_code == 401


def test_disallowed_algorithm_rejected_with_401(auth_client: TestClient) -> None:
    """HS256 token must be rejected when server only allows asymmetric ES256."""
    hs256_token = jwt.encode(
        {
            "sub": str(uuid4()),
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=10)).timestamp()),
        },
        "some-symmetric-secret-at-least-32-bytes-long",
        algorithm="HS256",
    )
    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {hs256_token}"},
    )
    assert response.status_code == 401


def test_valid_asymmetric_token_accepted(
    auth_client: TestClient,
    es256_keypair: tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey],
) -> None:
    """Valid ES256 token returns HTTP 200 and verified user identity claims."""
    private_key, _ = es256_keypair
    expected_user_id = uuid4()
    valid_token = make_es256_token(
        private_key,
        sub=str(expected_user_id),
        email="owner@svario.ai",
        full_name="Dr. Priya Nair",
    )

    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert UUID(body["id"]) == expected_user_id
    assert body["email"] == "owner@svario.ai"
    assert body["full_name"] == "Dr. Priya Nair"
    assert body["role"] == "authenticated"
    assert body["email_verified"] is True
    assert body["issuer"] == TEST_ISSUER
    assert body["audience"] == TEST_AUDIENCE
