"""Cryptographically-bound internal voice session actor helpers.

Prevents any caller from forging an internal voice actor merely by supplying
`issuer="https://svario.internal/auth/v1"`. Every internal voice actor created by
trusted backend code carries a process-scoped HMAC-SHA256 proof binding it to a
specific verified `(organization_id, business_id, industry, user_id)` tuple.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.modules.organizations.schemas import OrganizationIndustry

INTERNAL_VOICE_ISSUER = "https://svario.internal/auth/v1"

# Ephemeral per-process HMAC key — never persisted, never exposed outside backend RAM.
_INTERNAL_VOICE_HMAC_KEY: bytes = secrets.token_bytes(32)


def _compute_binding_signature(
    *,
    organization_id: UUID,
    business_id: UUID,
    industry: OrganizationIndustry,
    user_id: UUID,
) -> str:
    msg = f"{organization_id}:{business_id}:{industry.value}:{user_id}".encode("utf-8")
    return hmac.new(_INTERNAL_VOICE_HMAC_KEY, msg, hashlib.sha256).hexdigest()


def create_verified_internal_voice_actor(
    *,
    organization_id: UUID,
    business_id: UUID,
    industry: OrganizationIndustry,
    user_id: UUID,
    email: Optional[str] = None,
) -> AuthenticatedUser:
    """Create a backend-verified internal voice actor bound to one salon/business."""
    sig = _compute_binding_signature(
        organization_id=organization_id,
        business_id=business_id,
        industry=industry,
        user_id=user_id,
    )
    return AuthenticatedUser(
        id=user_id,
        email=email or "agent@svario.ai",
        issuer=INTERNAL_VOICE_ISSUER,
        audience="authenticated",
        # Never use a fake JWT string that could be mistaken for a Supabase user JWT
        raw_token="",
        app_metadata={
            "svario_internal_voice": True,
            "bound_organization_id": str(organization_id),
            "bound_business_id": str(business_id),
            "bound_industry": industry.value,
            "binding_sig": sig,
        },
    )


def verify_internal_voice_actor(
    actor: AuthenticatedUser,
    *,
    organization_id: UUID,
    business_id: UUID,
    expected_industry: Optional[OrganizationIndustry] = None,
) -> None:
    """Verify an internal voice actor's HMAC binding against the target tenant & industry.

    Raises HTTP 403 if the actor is forged, unbound, or bound to a different org/business/industry.
    """
    if actor.issuer != INTERNAL_VOICE_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: invalid internal voice issuer.",
        )

    meta = actor.app_metadata or {}
    if not meta.get("svario_internal_voice"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: missing internal voice session binding.",
        )

    bound_org = str(meta.get("bound_organization_id") or "")
    bound_biz = str(meta.get("bound_business_id") or "")
    bound_ind_raw = str(meta.get("bound_industry") or "")
    provided_sig = str(meta.get("binding_sig") or "")

    if bound_org != str(organization_id) or bound_biz != str(business_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: internal voice session is not authorized for this business.",
        )

    try:
        bound_ind = OrganizationIndustry(bound_ind_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: invalid internal voice session industry.",
        ) from exc

    if expected_industry is not None and bound_ind != expected_industry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: internal voice session is not authorized for '{expected_industry.value}' operations.",
        )

    expected_sig = _compute_binding_signature(
        organization_id=organization_id,
        business_id=business_id,
        industry=bound_ind,
        user_id=actor.id,
    )
    if not provided_sig or not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: internal voice session signature verification failed.",
        )
