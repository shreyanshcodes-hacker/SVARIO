"""Deliberate public-business voice access policy for Stage 3 (`public_visitor` mode).

Security Principle:
- Never treat a random `business_id` or `organization_id` UUID as proof of authorization.
- Public visitor voice sessions are permitted ONLY when:
  1. An organization `owner` or `admin` has explicitly enabled the voice assistant
     (`assistant.enabled == True`) and minted a signed `public_access_token`.
  2. The visitor presents a cryptographically valid, non-expired `public_access_token`
     whose signed claims match the requested `organization_id` and `business_id`.
  3. The business's voice assistant remains enabled at session creation time.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID
from fastapi import HTTPException, status
from app.core.config import Settings
from app.modules.onboarding.schemas import OnboardingBundleResponse

TOKEN_PREFIX = "svario_pub_v1"
FALLBACK_DEV_HMAC_KEY = "svario-stage3-dev-public-voice-hmac-key-do-not-use-in-prod"


@dataclass
class VerifiedPublicVoiceClaims:
    """Cryptographically verified claims from a public business voice token."""

    organization_id: UUID
    business_id: UUID
    issued_at: datetime
    expires_at: datetime


class PublicVoicePolicyRegistry:
    """Tracks verified business onboarding snapshots authorized for public voice sessions."""

    def __init__(self) -> None:
        self._authorized_bundles: Dict[Tuple[UUID, UUID], OnboardingBundleResponse] = {}

    def clear(self) -> None:
        self._authorized_bundles.clear()

    def register_bundle(self, bundle: OnboardingBundleResponse) -> None:
        """Record or refresh the latest verified business bundle for public access checks."""
        self._authorized_bundles[(bundle.organization.id, bundle.business_id)] = bundle

    def get_bundle(
        self, organization_id: UUID, business_id: UUID
    ) -> Optional[OnboardingBundleResponse]:
        return self._authorized_bundles.get((organization_id, business_id))


_public_policy_registry = PublicVoicePolicyRegistry()


def get_public_voice_policy_registry() -> PublicVoicePolicyRegistry:
    """Return shared public voice policy registry."""
    return _public_policy_registry


def _resolve_signing_secret(settings: Settings) -> bytes:
    configured = settings.voice_public_token_secret
    if (
        configured
        and configured.strip()
        and "placeholder" not in configured.lower()
        and not configured.strip().startswith("your-")
    ):
        return configured.strip().encode("utf-8")
    if settings.supabase_jwt_secret and settings.supabase_jwt_secret.strip():
        return settings.supabase_jwt_secret.strip().encode("utf-8")
    return FALLBACK_DEV_HMAC_KEY.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))


def mint_public_voice_token(
    *,
    settings: Settings,
    organization_id: UUID,
    business_id: UUID,
    ttl_seconds: Optional[int] = None,
) -> Tuple[str, datetime, int]:
    """Mint a short-lived HMAC-SHA256 signed public visitor voice token."""
    effective_ttl = ttl_seconds or settings.voice_public_token_ttl_seconds
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=effective_ttl)

    payload_dict = {
        "v": 1,
        "scope": "public_voice_session",
        "org_id": str(organization_id),
        "biz_id": str(business_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = _b64url_encode(payload_bytes)
    signing_input = f"{TOKEN_PREFIX}.{payload_b64}".encode("ascii")

    secret = _resolve_signing_secret(settings)
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    token = f"{TOKEN_PREFIX}.{payload_b64}.{sig_b64}"
    return token, expires_at, effective_ttl


def verify_public_voice_token(
    *,
    settings: Settings,
    token: Optional[str],
    expected_organization_id: UUID,
    expected_business_id: Optional[UUID],
) -> VerifiedPublicVoiceClaims:
    """Verify a public visitor voice token and enforce organization/business binding."""
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Public visitor voice sessions require a valid signed public_access_token. "
                "A business or organization UUID alone is never treated as proof of authorization."
            ),
        )

    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Malformed or unsupported public voice access token.",
        )

    _, payload_b64, sig_b64 = parts
    signing_input = f"{TOKEN_PREFIX}.{payload_b64}".encode("ascii")
    secret = _resolve_signing_secret(settings)
    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()

    try:
        provided_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid public voice access token signature encoding.",
        ) from exc

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid public voice access token signature.",
        )

    try:
        payload_raw = _b64url_decode(payload_b64)
        claims = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Corrupted public voice access token payload.",
        ) from exc

    if claims.get("scope") != "public_voice_session":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid public voice access token scope.",
        )

    now_ts = int(datetime.now(timezone.utc).timestamp())
    exp_ts = int(claims.get("exp", 0))
    iat_ts = int(claims.get("iat", 0))
    if exp_ts <= now_ts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public voice access token has expired.",
        )

    try:
        token_org_id = UUID(str(claims["org_id"]))
        token_biz_id = UUID(str(claims["biz_id"]))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid organization or business identifier in public token.",
        ) from exc

    if token_org_id != expected_organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public voice access token does not match the requested organization.",
        )

    if expected_business_id is not None and token_biz_id != expected_business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public voice access token does not match the requested business.",
        )

    return VerifiedPublicVoiceClaims(
        organization_id=token_org_id,
        business_id=token_biz_id,
        issued_at=datetime.fromtimestamp(iat_ts, tz=timezone.utc),
        expires_at=datetime.fromtimestamp(exp_ts, tz=timezone.utc),
    )
