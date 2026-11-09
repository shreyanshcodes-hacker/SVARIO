"""Stage 3 Voice Session & Public Access Token routes (`POST /api/v1/voice/sessions`)."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from app.core.auth import (
    AuthenticatedUser,
    SupabaseJWTVerifier,
    bearer_scheme,
    get_current_user,
    get_jwt_verifier,
)
from app.modules.voice.schemas import (
    PublicVoiceTokenCreateRequest,
    PublicVoiceTokenResponse,
    VoiceSessionCreateRequest,
    VoiceSessionCreateResponse,
)
from app.modules.voice.service import VoiceSessionService, get_voice_session_service

router = APIRouter(prefix="/api/v1", tags=["Voice (Stage 3)"])


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    verifier: SupabaseJWTVerifier = Depends(get_jwt_verifier),
) -> Optional[AuthenticatedUser]:
    """Verify Bearer token when provided; return None when omitted."""
    if credentials is None or not credentials.credentials:
        return None
    if credentials.scheme.lower() != "bearer":
        return None
    cleaned = credentials.credentials.strip()
    if not cleaned:
        return None
    return verifier.verify_token(cleaned)


@router.post(
    "/voice/sessions",
    response_model=VoiceSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a short-lived OpenAI Realtime WebRTC voice session",
)
async def create_voice_session(
    payload: VoiceSessionCreateRequest,
    request: Request,
    actor: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    service: VoiceSessionService = Depends(get_voice_session_service),
) -> VoiceSessionCreateResponse:
    """Create a short-lived WebRTC session credential after verifying business authorization."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip() or "unknown"
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "unknown"

    return await service.create_voice_session(
        actor=actor,
        client_ip=client_ip,
        payload=payload,
    )


@router.post(
    "/organizations/{organization_id}/voice/public-token",
    response_model=PublicVoiceTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mint a deliberate short-lived public visitor voice access token (Owner/Admin only)",
)
async def create_public_voice_token(
    organization_id: UUID,
    payload: PublicVoiceTokenCreateRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    service: VoiceSessionService = Depends(get_voice_session_service),
) -> PublicVoiceTokenResponse:
    """Generate a signed public-business voice token bound to the organization's primary business."""
    return await service.mint_public_access_token(
        actor=actor,
        organization_id=organization_id,
        payload=payload,
    )
