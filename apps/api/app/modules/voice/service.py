"""Domain service for Stage 3 Shared Browser Voice Infrastructure (`POST /api/v1/voice/sessions`).

Security & Architecture Guarantees:
1. Validates request schema (`extra="forbid"` rejects browser-supplied system instructions).
2. Resolves intended business and enforces strict access policy:
   - `organization_member`: requires verified Supabase JWT and membership in `organization_id`.
   - `public_visitor`: requires a cryptographically valid, non-expired `public_access_token`
     minted for `(organization_id, business_id)` AND requires `assistant.enabled == True`.
3. Composes system instructions strictly on the server from verified Stage 2 business settings,
   including mandatory administrative-only healthcare guardrails for `clinic` and `hospital`.
4. Enforces per-caller sliding-window rate limiting (`429 Too Many Requests`).
5. Mints short-lived ephemeral OpenAI Realtime client credentials (`POST /v1/realtime/sessions`)
   using the backend-only `OPENAI_API_KEY`.
6. Never returns or logs the permanent `OPENAI_API_KEY` or raw session secrets.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, Dict, Optional
from uuid import UUID, uuid4
import httpx
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.schemas import OrganizationIndustry, OrganizationRole
from app.modules.voice.prompts import build_safe_realtime_instructions
from app.modules.voice.public_access import (
    PublicVoicePolicyRegistry,
    get_public_voice_policy_registry,
    mint_public_voice_token,
    verify_public_voice_token,
)
from app.modules.voice.rate_limit import VoiceSessionRateLimiter, get_voice_rate_limiter
from app.modules.voice.schemas import (
    EphemeralClientSecret,
    PublicVoiceTokenCreateRequest,
    PublicVoiceTokenResponse,
    SafeVoiceAssistantContext,
    VoiceAccessMode,
    VoiceSessionCapabilities,
    VoiceSessionCreateRequest,
    VoiceSessionCreateResponse,
)

RealtimeUpstreamCallable = Callable[
    [Settings, Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]
]


async def _default_openai_realtime_mint(
    settings: Settings, session_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Call OpenAI's official GA Realtime client_secrets endpoint to mint an ephemeral client token."""
    api_key = (settings.openai_api_key or "").strip()
    endpoint = f"{settings.effective_realtime_base_url}/realtime/client_secrets"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, headers=headers, json=session_payload)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach upstream voice provider to initialize Realtime session.",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Upstream voice provider rejected Realtime session initialization "
                f"(status {response.status_code})."
            ),
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream voice provider returned an invalid JSON payload.",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream voice provider returned an unexpected response structure.",
        )

    return data


def _extract_ephemeral_secret(
    upstream_data: Dict[str, Any],
    settings: Settings,
) -> TupleSecretResult:
    """Extract and validate the short-lived client secret from OpenAI's response."""
    raw_secret_obj = upstream_data.get("client_secret")
    ephemeral_value: Optional[str] = None
    raw_expires_at: Any = None

    if isinstance(upstream_data.get("value"), str) and upstream_data["value"].strip():
        ephemeral_value = upstream_data["value"].strip()
        raw_expires_at = upstream_data.get("expires_at")
    elif isinstance(raw_secret_obj, dict):
        val = raw_secret_obj.get("value")
        if isinstance(val, str) and val.strip():
            ephemeral_value = val.strip()
        raw_expires_at = raw_secret_obj.get("expires_at")
    elif isinstance(raw_secret_obj, str) and raw_secret_obj.strip():
        ephemeral_value = raw_secret_obj.strip()
        raw_expires_at = upstream_data.get("expires_at")

    if not ephemeral_value:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream voice provider response did not include an ephemeral client credential.",
        )

    # Security assertion: never allow the permanent API key to be returned as the client secret
    permanent_key = (settings.openai_api_key or "").strip()
    if permanent_key and ephemeral_value == permanent_key:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Security policy violation: upstream returned a non-ephemeral credential.",
        )

    now = datetime.now(timezone.utc)
    default_ttl = settings.openai_realtime_session_ttl_seconds
    expires_at = now + timedelta(seconds=default_ttl)

    if isinstance(raw_expires_at, (int, float)) and raw_expires_at > 0:
        candidate = datetime.fromtimestamp(float(raw_expires_at), tz=timezone.utc)
        if candidate > now:
            expires_at = candidate
    elif isinstance(raw_expires_at, str) and raw_expires_at.strip():
        try:
            candidate = datetime.fromisoformat(
                raw_expires_at.strip().replace("Z", "+00:00")
            )
            if candidate > now:
                expires_at = candidate
        except ValueError:
            pass

    ttl_seconds = max(1, int((expires_at - now).total_seconds()))
    nested_session = upstream_data.get("session")
    nested_id = (
        nested_session.get("id")
        if isinstance(nested_session, dict) and nested_session.get("id")
        else None
    )
    session_id = str(nested_id or upstream_data.get("id") or f"sess_{uuid4().hex[:16]}")

    return TupleSecretResult(
        session_id=session_id,
        secret=EphemeralClientSecret(
            value=ephemeral_value,
            expires_at=expires_at,
            ttl_seconds=ttl_seconds,
        ),
    )


class TupleSecretResult:
    """Internal container for parsed session ID and ephemeral credential."""

    def __init__(self, session_id: str, secret: EphemeralClientSecret) -> None:
        self.session_id = session_id
        self.secret = secret


class VoiceSessionService:
    """Orchestrates Stage 3 secure Realtime session creation and public access tokens."""

    def __init__(
        self,
        settings: Settings,
        onboarding_service: OnboardingService,
        rate_limiter: VoiceSessionRateLimiter,
        public_registry: PublicVoicePolicyRegistry,
        upstream_mint: RealtimeUpstreamCallable = _default_openai_realtime_mint,
    ) -> None:
        self._settings = settings
        self._onboarding_service = onboarding_service
        self._rate_limiter = rate_limiter
        self._public_registry = public_registry
        self._upstream_mint = upstream_mint

    async def mint_public_access_token(
        self,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: PublicVoiceTokenCreateRequest,
    ) -> PublicVoiceTokenResponse:
        """Mint a deliberate short-lived public visitor token (Owner/Admin only)."""
        bundle = await self._onboarding_service.get_onboarding_bundle(
            actor=actor, organization_id=organization_id
        )
        if bundle.organization.membership_role not in {
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions: only organization owners or admins may generate public voice access tokens.",
            )

        if not bundle.assistant.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enable the AI voice assistant in onboarding settings before generating a public visitor token.",
            )

        self._public_registry.register_bundle(bundle)
        token, expires_at, ttl_seconds = mint_public_voice_token(
            settings=self._settings,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            ttl_seconds=payload.ttl_seconds,
        )

        return PublicVoiceTokenResponse(
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            industry=bundle.organization.industry,
            public_access_token=token,
            expires_at=expires_at,
            ttl_seconds=ttl_seconds,
        )

    async def _resolve_authorized_bundle(
        self,
        *,
        actor: Optional[AuthenticatedUser],
        payload: VoiceSessionCreateRequest,
    ) -> OnboardingBundleResponse:
        """Resolve and authorize the target business bundle according to `access_mode`."""
        if payload.access_mode == VoiceAccessMode.ORGANIZATION_MEMBER:
            if actor is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication Bearer token is required for organization member voice sessions.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            bundle = await self._onboarding_service.get_onboarding_bundle(
                actor=actor, organization_id=payload.organization_id
            )
            if (
                payload.business_id is not None
                and payload.business_id != bundle.business_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: requested business_id does not belong to this organization.",
                )

            # Keep public registry synchronized with latest member-loaded state
            self._public_registry.register_bundle(bundle)
            return bundle

        # Deliberate public visitor mode (`access_mode == PUBLIC_VISITOR`)
        verified_claims = verify_public_voice_token(
            settings=self._settings,
            token=payload.public_access_token,
            expected_organization_id=payload.organization_id,
            expected_business_id=payload.business_id,
        )

        # If an authenticated member also passed their token, refresh the bundle first
        if actor is not None:
            try:
                member_bundle = await self._onboarding_service.get_onboarding_bundle(
                    actor=actor, organization_id=verified_claims.organization_id
                )
                self._public_registry.register_bundle(member_bundle)
            except HTTPException:
                pass

        bundle = self._public_registry.get_bundle(
            organization_id=verified_claims.organization_id,
            business_id=verified_claims.business_id,
        )
        if bundle is None or not bundle.assistant.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voice assistant is not enabled for public visitor access on this business.",
            )

        return bundle

    async def create_voice_session(
        self,
        *,
        actor: Optional[AuthenticatedUser],
        client_ip: str,
        payload: VoiceSessionCreateRequest,
    ) -> VoiceSessionCreateResponse:
        """Validate access, enforce rate limit, and create a short-lived Realtime session."""
        # 1. Resolve business & verify access policy FIRST
        bundle = await self._resolve_authorized_bundle(actor=actor, payload=payload)

        # 2. Enforce per-caller rate limit
        rate_key = (
            f"member:{actor.id}"
            if actor is not None
            else f"visitor:{client_ip}:{bundle.business_id}"
        )
        self._rate_limiter.check_and_record(
            actor_key=rate_key,
            max_requests_per_window=self._settings.voice_session_rate_limit_per_minute,
        )

        # 3. Verify backend OpenAI Realtime API key configuration
        if not self._settings.is_openai_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "OpenAI Realtime voice service is not configured on the server. "
                    "Configure OPENAI_API_KEY in apps/api/.env."
                ),
            )

        # 4. Build safe server-side instructions & session configuration
        instructions = build_safe_realtime_instructions(bundle)
        resolved_voice = (
            payload.voice_override.value
            if payload.voice_override is not None
            else self._settings.openai_realtime_voice
        )
        model = self._settings.openai_realtime_model
        modalities = self._settings.realtime_modalities

        upstream_payload: Dict[str, Any] = {
            "expires_after": {
                "anchor": "created_at",
                "seconds": self._settings.openai_realtime_session_ttl_seconds,
            },
            "session": {
                "type": "realtime",
                "model": model,
                "instructions": instructions,
                "audio": {
                    "input": {
                        "transcription": None,
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500,
                            "create_response": True,
                            "interrupt_response": True,
                        },
                    },
                    "output": {
                        "voice": resolved_voice,
                    },
                },
            },
        }

        # 5. Request short-lived ephemeral credential from OpenAI
        upstream_response = await self._upstream_mint(self._settings, upstream_payload)
        parsed = _extract_ephemeral_secret(upstream_response, self._settings)

        is_healthcare = bundle.organization.industry in {
            OrganizationIndustry.CLINIC,
            OrganizationIndustry.HOSPITAL,
        }
        base_url = self._settings.effective_realtime_base_url

        return VoiceSessionCreateResponse(
            session_id=parsed.session_id,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            industry=bundle.organization.industry,
            access_mode=payload.access_mode,
            model=model,
            voice=resolved_voice,
            webrtc_url=f"{base_url}/realtime/calls",
            webrtc_calls_url=f"{base_url}/realtime/calls",
            data_channel_label="oai-events",
            client_secret=parsed.secret,
            capabilities=VoiceSessionCapabilities(
                modalities=modalities,
                barge_in_enabled=True,
                raw_audio_storage_enabled=False,
                transcript_storage_enabled=False,
                appointment_booking_enabled=False,
                industry_workflows_enabled=False,
            ),
            assistant_context=SafeVoiceAssistantContext(
                business_name=bundle.profile.display_name,
                assistant_name=bundle.assistant.assistant_name,
                greeting=bundle.assistant.greeting,
                primary_language=bundle.languages.primary_language,
                supported_languages=bundle.languages.supported_languages,
                personality=bundle.assistant.personality,
                response_style=bundle.assistant.response_style,
                assistant_enabled=bundle.assistant.enabled,
                administrative_only_guardrails=is_healthcare,
                audio_persistence_enabled=False,
                transcript_persistence_enabled=False,
            ),
        )


def get_voice_session_service(
    settings: Settings = Depends(get_settings),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    rate_limiter: VoiceSessionRateLimiter = Depends(get_voice_rate_limiter),
    public_registry: PublicVoicePolicyRegistry = Depends(get_public_voice_policy_registry),
) -> VoiceSessionService:
    """FastAPI dependency returning a configured VoiceSessionService."""
    return VoiceSessionService(
        settings=settings,
        onboarding_service=onboarding_service,
        rate_limiter=rate_limiter,
        public_registry=public_registry,
    )
