"""Stage 3 & Stage 4 Voice Session, Public Access Token, Tool Execution & Agent Turn routes."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from app.agents.schemas import (
    AgentTurnRequest,
    AgentTurnResponse,
    SessionConversationContext,
    VoiceToolExecutionRequest,
    VoiceToolExecutionResponse,
)
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

router = APIRouter(prefix="/api/v1", tags=["Voice & Agent (Stage 3–4)"])


def _extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


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
    return await service.create_voice_session(
        actor=actor,
        client_ip=_extract_client_ip(request),
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


@router.post(
    "/voice/tools/execute",
    response_model=VoiceToolExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and execute a Stage 4 Realtime agent tool call",
)
async def execute_voice_tool(
    payload: VoiceToolExecutionRequest,
    request: Request,
    actor: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    service: VoiceSessionService = Depends(get_voice_session_service),
) -> VoiceToolExecutionResponse:
    """Execute one of the 5 structured Stage 4 tools on behalf of an active voice session."""
    return await service.execute_voice_tool(
        actor=actor,
        client_ip=_extract_client_ip(request),
        payload=payload,
    )


@router.post(
    "/agent/turns",
    response_model=AgentTurnResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a full controlled Stage 4 conversational turn",
)
async def process_agent_turn(
    payload: AgentTurnRequest,
    request: Request,
    actor: Optional[AuthenticatedUser] = Depends(get_optional_current_user),
    service: VoiceSessionService = Depends(get_voice_session_service),
) -> AgentTurnResponse:
    """Run intent recognition, tool execution, safety checks, and response composition."""
    return await service.process_agent_turn(
        actor=actor,
        client_ip=_extract_client_ip(request),
        payload=payload,
    )


@router.get(
    "/voice/sessions/{session_id}/context",
    response_model=SessionConversationContext,
    status_code=status.HTTP_200_OK,
    summary="Inspect session-scoped conversation context (Organization member only)",
)
async def get_voice_session_context(
    session_id: str,
    organization_id: UUID = Query(..., description="Authorized organization UUID"),
    actor: AuthenticatedUser = Depends(get_current_user),
    service: VoiceSessionService = Depends(get_voice_session_service),
) -> SessionConversationContext:
    """Retrieve the current session-scoped conversation context for an authorized member."""
    return await service.get_session_context(
        actor=actor,
        session_id=session_id,
        organization_id=organization_id,
    )
