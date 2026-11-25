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
import hashlib
import json
import secrets
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, NAMESPACE_URL, uuid5
from fastapi import Depends, HTTPException, status
from app.core.redis_provider import (
    RedisClientProtocol,
    RedisUnavailableError,
    get_redis_client,
    raise_redis_unavailable,
)
from app.agents.schemas import (
    AgentToolName,
    VoiceToolExecutionRequest,
    VoiceToolExecutionResponse,
)
from app.core.config import Settings, get_settings
from app.core.state_protocols import PublicSessionStoreProtocol
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
    has_persistent_db_access: bool
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


class RedisPublicSessionStore:
    """Distributed Redis-backed public website visitor voice session store."""

    MAX_TTL_SECONDS = 600

    def __init__(self, redis_client: RedisClientProtocol) -> None:
        self._redis = redis_client

    @staticmethod
    def _key_for(token: str) -> str:
        digest = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
        return f"svario:pub_sess:{digest}"

    def clear(self) -> None:
        return None

    def put(self, token: str, record: _BoundPublicVoiceSession) -> None:
        now = datetime.now(timezone.utc)
        ttl_seconds = max(
            1,
            min(self.MAX_TTL_SECONDS, int((record.expires_at - now).total_seconds())),
        )
        payload = json.dumps(
            {
                "slug": record.slug,
                "session_id": record.session_id,
                "organization_id": str(record.organization_id),
                "business_id": str(record.business_id),
                "internal_public_token": record.internal_public_token,
                "has_persistent_db_access": bool(record.has_persistent_db_access),
                "expires_at": record.expires_at.isoformat(),
            },
            separators=(",", ":"),
        )
        try:
            self._redis.execute(["SET", self._key_for(token), payload, "EX", ttl_seconds])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

    def revoke(self, token: str) -> None:
        try:
            self._redis.execute(["DEL", self._key_for(token)])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

    def verify(self, *, token: str, slug: str, session_id: str) -> _BoundPublicVoiceSession:
        key = self._key_for(token)
        try:
            raw = self._redis.execute(["GET", key])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

        if not raw or not isinstance(raw, str):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired public voice session token.",
            )

        try:
            data = json.loads(raw)
            rec = _BoundPublicVoiceSession(
                slug=str(data["slug"]),
                session_id=str(data["session_id"]),
                organization_id=UUID(str(data["organization_id"])),
                business_id=UUID(str(data["business_id"])),
                internal_public_token=str(data["internal_public_token"]),
                has_persistent_db_access=bool(data["has_persistent_db_access"]),
                expires_at=datetime.fromisoformat(str(data["expires_at"])),
            )
        except Exception as exc:
            try:
                self._redis.execute(["DEL", key])
            except RedisUnavailableError:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired public voice session token.",
            ) from exc

        if rec.slug != slug or rec.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public voice session token does not match this salon session.",
            )

        if rec.expires_at <= datetime.now(timezone.utc):
            try:
                self._redis.execute(["DEL", key])
            except RedisUnavailableError:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Public voice session has expired.",
            )

        return rec


def get_public_website_voice_session_store(
    settings: Settings = Depends(get_settings),
) -> PublicSessionStoreProtocol:
    resolved = settings if isinstance(settings, Settings) else get_settings()
    redis_client = get_redis_client(resolved)
    if redis_client is not None:
        return RedisPublicSessionStore(redis_client)
    if resolved.is_production:
        raise raise_redis_unavailable()
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
        session_store: Optional[PublicSessionStoreProtocol] = None,
    ) -> None:
        self._settings = settings
        self._website_service = website_service
        self._voice_service = voice_service
        self._session_store = session_store or _shared_session_store

    async def _resolve_published_ids(self, slug: str) -> Tuple[UUID, UUID, bool]:
        """Resolve real (organization_id, business_id) via service_role RPC (or in-memory repo).

        Returns `(org_id, biz_id, has_persistent_db_access)`. Never leaks real UUIDs to the browser.
        """
        resolved = await self._website_service._website_repo.get_published_tenant_ids(slug)
        if resolved is not None:
            return resolved[0], resolved[1], True
        return (
            uuid5(NAMESPACE_URL, f"svario:public-org:{slug}"),
            uuid5(NAMESPACE_URL, f"svario:public-biz:{slug}"),
            False,
        )

    @staticmethod
    def _build_public_services_tool_output(
        site: PublicBookingWebsiteResponse,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a `get_salon_services` tool output strictly from the verified published catalogue."""
        category_filter = str((arguments or {}).get("category") or "").strip().lower()
        items: List[Dict[str, Any]] = []
        for svc in site.services:
            if category_filter and (svc.category or "").strip().lower() != category_filter:
                continue
            items.append(
                {
                    "service_id": str(svc.id),
                    "name": svc.name,
                    "category": svc.category or "general",
                    "description": svc.description,
                    "price": float(svc.price),
                    "currency": svc.currency or "INR",
                    "duration_minutes": int(svc.duration_minutes),
                }
            )
        return {
            "services": items,
            "count": len(items),
        }

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

        org_id, biz_id, has_persistent_db_access = await self._resolve_published_ids(site.slug)
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
                has_persistent_db_access=has_persistent_db_access,
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
        if getattr(site, "published", True) is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI receptionist is not available for an unpublished salon website.",
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

        # Reject any model attempt to inject client-side tenant IDs
        if {"organization_id", "business_id", "tenant_id"}.intersection(
            (payload.arguments or {}).keys()
        ):
            return VoiceToolExecutionResponse(
                session_id=payload.session_id,
                call_id=payload.call_id,
                tool_name=tool_enum,
                status="rejected",
                output={
                    "error": "forbidden_tenant_override",
                    "message": "Tool arguments must not override server-resolved salon identity.",
                },
                detected_language=LanguageCode("en"),
            )

        # Service discovery: when backend service-role DB access is unavailable, serve the
        # verified active catalogue already fetched from Supabase by get_published_booking_website_by_slug.
        if (
            tool_enum == AgentToolName.GET_SALON_SERVICES
            and not bound.has_persistent_db_access
        ):
            return VoiceToolExecutionResponse(
                session_id=payload.session_id,
                call_id=payload.call_id,
                tool_name=tool_enum,
                status="succeeded",
                output=self._build_public_services_tool_output(site, payload.arguments or {}),
                detected_language=LanguageCode("en"),
            )

        # Fail closed truthfully for live staff/availability/booking tools if SUPABASE_SERVICE_ROLE_KEY
        # is not configured on the backend (never invent slots or claim bookings succeeded).
        if (
            tool_enum
            in {
                AgentToolName.GET_SALON_STAFF,
                AgentToolName.CHECK_SALON_AVAILABILITY,
                AgentToolName.CREATE_SALON_APPOINTMENT,
                AgentToolName.RESCHEDULE_SALON_APPOINTMENT,
                AgentToolName.CANCEL_SALON_APPOINTMENT,
            }
            and not bound.has_persistent_db_access
        ):
            return VoiceToolExecutionResponse(
                session_id=payload.session_id,
                call_id=payload.call_id,
                tool_name=tool_enum,
                status="error",
                output={
                    "error": "public_booking_backend_not_configured",
                    "message": (
                        "Real-time stylist availability and online appointment booking require "
                        "server-side database service-role configuration (SUPABASE_SERVICE_ROLE_KEY). "
                        "Please contact the salon directly to confirm your appointment."
                    ),
                },
                detected_language=LanguageCode("en"),
            )

        # Refresh handling worker's runtime policy registry from authoritative Supabase state
        refreshed_bundle = _build_allowlisted_bundle_from_public_site(
            site,
            organization_id=bound.organization_id,
            business_id=bound.business_id,
        )
        self._voice_service._public_registry.register_bundle(refreshed_bundle)

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
    session_store: PublicSessionStoreProtocol = Depends(get_public_website_voice_session_store),
) -> PublicWebsiteVoiceBridgeService:
    return PublicWebsiteVoiceBridgeService(
        settings=settings,
        website_service=website_service,
        voice_service=voice_service,
        session_store=session_store,
    )
