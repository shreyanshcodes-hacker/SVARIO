"""Stage 3 Additive Bridge: Public Website AI Receptionist Voice Integration.

Security & Architecture Guarantees:
- Reuses the existing locked `VoiceSessionService` (`create_voice_session` and
  `execute_voice_tool`) without creating a second voice engine or modifying any
  protected voice core files.
- Resolves the salon strictly server-side from the published website slug.
- Never accepts client-supplied `organization_id`, `business_id`, or prompts.
- Never returns raw tenant UUIDs (`organization_id`, `business_id`) to public visitors.
- Binds tool execution to an opaque, short-lived, server-verified `visitor_session_token`
  and re-verifies that the website is still published on every tool call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Dict, Optional, Tuple
from uuid import UUID, NAMESPACE_URL, uuid5
from fastapi import Depends, HTTPException, status
from app.agents.schemas import (
    AgentToolName,
    VoiceToolExecutionRequest,
    VoiceToolExecutionResponse,
)
from app.core.config import Settings, get_settings
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    AssistantSettingsResponse,
    BusinessHoursResponse,
    BusinessLanguagesResponse,
    BusinessProfileResponse,
    EscalationSettingsResponse,
    HealthcareSafeguardNotice,
    LanguageCode,
    OnboardingBundleResponse,
    OnboardingProgressResponse,
    OnboardingStepId,
    WeekdayHoursItem,
)
from app.modules.organizations.schemas import (
    OrganizationDetailResponse,
    OrganizationIndustry,
    OrganizationRole,
)
from app.modules.voice.public_access import mint_public_voice_token
from app.modules.voice.schemas import (
    RealtimeVoicePreset,
    VoiceAccessMode,
    VoiceSessionCreateRequest,
)
from app.modules.voice.service import VoiceSessionService, get_voice_session_service
from app.modules.websites.schemas import (
    PublicBookingWebsiteResponse,
    PublicWebsiteVoiceSessionRequest,
    PublicWebsiteVoiceSessionResponse,
    PublicWebsiteVoiceToolRequest,
    normalize_website_slug,
)
from app.modules.websites.service import (
    BookingWebsiteService,
    get_booking_website_service,
)


@dataclass(frozen=True)
class _BoundPublicVoiceSession:
    """Server-side session record binding an opaque visitor token to a verified tenant."""

    slug: str
    session_id: str
    organization_id: UUID
    business_id: UUID
    internal_public_token: str
    expires_at: datetime


class PublicWebsiteVoiceSessionStore:
    """Bounded in-memory store for opaque public website visitor voice sessions."""

    def __init__(self, max_entries: int = 500) -> None:
        self._max_entries = max_entries
        self._sessions: Dict[str, _BoundPublicVoiceSession] = {}

    def clear(self) -> None:
        self._sessions.clear()

    def _prune_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [tok for tok, rec in self._sessions.items() if rec.expires_at <= now]
        for tok in expired:
            self._sessions.pop(tok, None)

    def put(self, token: str, record: _BoundPublicVoiceSession) -> None:
        self._prune_expired()
        if len(self._sessions) >= self._max_entries:
            oldest_key = next(iter(self._sessions))
            self._sessions.pop(oldest_key, None)
        self._sessions[token] = record

    def verify(self, *, token: str, slug: str, session_id: str) -> _BoundPublicVoiceSession:
        self._prune_expired()
        rec = self._sessions.get(token)
        if rec is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired public voice session token.",
            )
        if rec.slug != slug or rec.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public voice session token does not match this salon session.",
            )
        if rec.expires_at <= datetime.now(timezone.utc):
            self._sessions.pop(token, None)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public voice session has expired.",
            )
        return rec


_shared_session_store = PublicWebsiteVoiceSessionStore()


def get_public_website_voice_session_store() -> PublicWebsiteVoiceSessionStore:
    return _shared_session_store


def _build_allowlisted_bundle_from_public_site(
    site: PublicBookingWebsiteResponse,
    *,
    organization_id: UUID,
    business_id: UUID,
) -> OnboardingBundleResponse:
    """Construct a strictly allowlisted OnboardingBundleResponse from verified public website data."""
    now = datetime.now(timezone.utc)
    schedule = [
        WeekdayHoursItem(
            weekday=h.weekday,
            is_closed=h.is_closed,
            opens_at=h.opens_at,
            closes_at=h.closes_at,
            is_overnight=h.is_overnight,
        )
        for h in site.hours
    ]
    if not schedule:
        schedule = [
            WeekdayHoursItem(
                weekday=d,
                is_closed=(d == 0),
                opens_at=None if d == 0 else "09:00",
                closes_at=None if d == 0 else "18:00",
                is_overnight=False,
            )
            for d in range(7)
        ]

    return OnboardingBundleResponse(
        organization=OrganizationDetailResponse(
            id=organization_id,
            name=site.business.display_name,
            slug=site.slug,
            industry=OrganizationIndustry.SALON,
            membership_role=OrganizationRole.STAFF,
            member_count=1,
            created_at=now,
            updated_at=now,
        ),
        business_id=business_id,
        profile=BusinessProfileResponse(
            id=uuid5(NAMESPACE_URL, f"svario:public-profile:{business_id}"),
            organization_id=organization_id,
            business_id=business_id,
            display_name=site.business.display_name,
            description=site.business.description,
            phone=site.business.phone,
            email=site.business.email,
            website=None,
            address=site.business.address,
            city=site.business.city,
            state=site.business.state,
            country=site.business.country,
            postal_code=None,
            timezone=site.business.timezone or "Asia/Kolkata",
            created_at=now,
            updated_at=now,
        ),
        hours=BusinessHoursResponse(
            organization_id=organization_id,
            business_id=business_id,
            timezone=site.business.timezone or "Asia/Kolkata",
            schedule=schedule,
        ),
        languages=BusinessLanguagesResponse(
            organization_id=organization_id,
            business_id=business_id,
            primary_language=LanguageCode("en"),
            supported_languages=[LanguageCode("en")],
            entries=[],
        ),
        assistant=AssistantSettingsResponse(
            id=uuid5(NAMESPACE_URL, f"svario:public-assistant:{business_id}"),
            organization_id=organization_id,
            business_id=business_id,
            assistant_name=site.receptionist.assistant_name or f"{site.business.display_name} Receptionist",
            greeting=site.receptionist.greeting
            or f"Welcome to {site.business.display_name}! How can I help you with services or appointments today?",
            personality=AssistantPersonality.WARM,
            response_style=AssistantResponseStyle.BALANCED,
            enabled=True,
            created_at=now,
            updated_at=now,
        ),
        faqs=[],
        faq_templates=[],
        escalation=EscalationSettingsResponse(
            id=uuid5(NAMESPACE_URL, f"svario:public-escalation:{business_id}"),
            organization_id=organization_id,
            business_id=business_id,
            enabled=False,
            contact_name=None,
            contact_email=None,
            contact_phone=None,
            preferred_method="phone",
            escalation_instructions=None,
            created_at=now,
            updated_at=now,
        ),
        healthcare_safeguards=HealthcareSafeguardNotice(
            applies_to_healthcare=False,
            administrative_only=False,
            prohibited_actions=[],
            emergency_directive="",
        ),
        progress=OnboardingProgressResponse(
            id=uuid5(NAMESPACE_URL, f"svario:public-progress:{business_id}"),
            organization_id=organization_id,
            business_id=business_id,
            current_step=OnboardingStepId.REVIEW,
            completed_steps=[],
            is_completed=True,
            completed_at=now,
            created_at=now,
            updated_at=now,
        ),
    )


class PublicWebsiteVoiceBridgeService:
    """Connects published `/s/[slug]` websites to the locked `VoiceSessionService` safely."""

    def __init__(
        self,
        *,
        settings: Settings,
        website_service: BookingWebsiteService,
        voice_service: VoiceSessionService,
        session_store: Optional[PublicWebsiteVoiceSessionStore] = None,
    ) -> None:
        self._settings = settings
        self._website_service = website_service
        self._voice_service = voice_service
        self._session_store = session_store or _shared_session_store

    async def _resolve_published_ids(self, slug: str) -> Tuple[UUID, UUID]:
        """Resolve real tenant UUIDs when available in-memory, or deterministic scoped UUIDs otherwise."""
        raw = await self._website_service._website_repo.get_published_by_slug(slug)
        if raw and raw.get("organization_id") and raw.get("business_id"):
            return UUID(str(raw["organization_id"])), UUID(str(raw["business_id"]))
        return (
            uuid5(NAMESPACE_URL, f"svario:public-org:{slug}"),
            uuid5(NAMESPACE_URL, f"svario:public-biz:{slug}"),
        )

    async def create_public_voice_session(
        self,
        *,
        slug: str,
        client_ip: str,
        payload: PublicWebsiteVoiceSessionRequest,
    ) -> PublicWebsiteVoiceSessionResponse:
        """Verify published salon slug and delegate session creation to the locked VoiceSessionService."""
        site = await self._website_service.get_public_website_by_slug(
            slug=slug, client_ip=client_ip
        )
        if not site.show_ai_receptionist or not site.receptionist.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI receptionist is not enabled for this salon website.",
            )

        voice_override: Optional[RealtimeVoicePreset] = None
        if payload.voice_override is not None:
            try:
                voice_override = RealtimeVoicePreset(payload.voice_override.strip().lower())
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Unsupported voice preset.",
                ) from exc

        org_id, biz_id = await self._resolve_published_ids(site.slug)
        bundle = _build_allowlisted_bundle_from_public_site(
            site, organization_id=org_id, business_id=biz_id
        )

        # Register allowlisted bundle and mint short-lived internal public visitor token
        self._voice_service._public_registry.register_bundle(bundle)
        internal_token, token_expires_at, _ = mint_public_voice_token(
            settings=self._settings,
            organization_id=org_id,
            business_id=biz_id,
            ttl_seconds=600,
        )

        # Delegate directly to the LOCKED VoiceSessionService core
        session_resp = await self._voice_service.create_voice_session(
            actor=None,
            client_ip=client_ip,
            payload=VoiceSessionCreateRequest(
                organization_id=org_id,
                business_id=biz_id,
                access_mode=VoiceAccessMode.PUBLIC_VISITOR,
                public_access_token=internal_token,
                voice_override=voice_override,
            ),
        )

        visitor_token = secrets.token_urlsafe(32)
        self._session_store.put(
            visitor_token,
            _BoundPublicVoiceSession(
                slug=site.slug,
                session_id=session_resp.session_id,
                organization_id=org_id,
                business_id=biz_id,
                internal_public_token=internal_token,
                expires_at=min(token_expires_at, datetime.now(timezone.utc) + timedelta(minutes=10)),
            ),
        )

        # Sanitized response: NEVER expose organization_id, business_id, or internal tokens
        return PublicWebsiteVoiceSessionResponse(
            session_id=session_resp.session_id,
            slug=site.slug,
            visitor_session_token=visitor_token,
            model=session_resp.model,
            voice=session_resp.voice,
            webrtc_url=session_resp.webrtc_url,
            webrtc_calls_url=session_resp.webrtc_calls_url,
            data_channel_label=session_resp.data_channel_label,
            client_secret=session_resp.client_secret.model_dump(mode="json"),
            capabilities=session_resp.capabilities.model_dump(mode="json"),
            assistant_context=session_resp.assistant_context.model_dump(mode="json"),
        )

    async def execute_public_voice_tool(
        self,
        *,
        slug: str,
        client_ip: str,
        payload: PublicWebsiteVoiceToolRequest,
    ) -> VoiceToolExecutionResponse:
        """Re-verify published slug & opaque visitor token, then delegate to locked VoiceSessionService."""
        try:
            normalized = normalize_website_slug(slug)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking website not found.",
            )

        # Re-verify website is STILL published and receptionist is enabled
        site = await self._website_service.get_public_website_by_slug(
            slug=normalized, client_ip=client_ip
        )
        if not site.show_ai_receptionist or not site.receptionist.enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI receptionist is not enabled for this salon website.",
            )

        bound = self._session_store.verify(
            token=payload.visitor_session_token,
            slug=site.slug,
            session_id=payload.session_id,
        )

        try:
            tool_enum = AgentToolName(payload.tool_name)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported receptionist tool.",
            ) from exc

        return await self._voice_service.execute_voice_tool(
            actor=None,
            client_ip=client_ip,
            payload=VoiceToolExecutionRequest(
                session_id=payload.session_id,
                call_id=payload.call_id,
                organization_id=bound.organization_id,
                business_id=bound.business_id,
                access_mode=VoiceAccessMode.PUBLIC_VISITOR,
                public_access_token=bound.internal_public_token,
                tool_name=tool_enum,
                arguments=payload.arguments,
            ),
        )


def get_public_website_voice_bridge_service(
    settings: Settings = Depends(get_settings),
    website_service: BookingWebsiteService = Depends(get_booking_website_service),
    voice_service: VoiceSessionService = Depends(get_voice_session_service),
    session_store: PublicWebsiteVoiceSessionStore = Depends(get_public_website_voice_session_store),
) -> PublicWebsiteVoiceBridgeService:
    return PublicWebsiteVoiceBridgeService(
        settings=settings,
        website_service=website_service,
        voice_service=voice_service,
        session_store=session_store,
    )
