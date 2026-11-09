"""Pydantic schemas for Stage 3 Shared Browser Voice Infrastructure.

Security guarantees:
- Request models enforce `ConfigDict(extra="forbid")` so browser clients cannot
  inject `instructions`, `system_prompt`, `api_key`, `tools`, or arbitrary model
  parameters.
- Response models never include permanent backend API keys.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    LanguageCode,
)
from app.modules.organizations.schemas import OrganizationIndustry


class VoiceAccessMode(str, Enum):
    """Supported authorization modes for `POST /api/v1/voice/sessions`."""

    ORGANIZATION_MEMBER = "organization_member"
    PUBLIC_VISITOR = "public_visitor"


class RealtimeVoicePreset(str, Enum):
    """Supported OpenAI Realtime voice presets."""

    ALLOY = "alloy"
    ASH = "ash"
    BALLAD = "ballad"
    CORAL = "coral"
    ECHO = "echo"
    SAGE = "sage"
    SHIMMER = "shimmer"
    VERSE = "verse"
    MARIN = "marin"
    CEDAR = "cedar"


class VoiceSessionCreateRequest(BaseModel):
    """Strict request schema for `POST /api/v1/voice/sessions`.

    Arbitrary system instructions or raw OpenAI session overrides from the browser
    are strictly forbidden via `extra="forbid"`.
    """

    model_config = ConfigDict(extra="forbid")

    organization_id: UUID = Field(
        ...,
        description="Target organization UUID owning the business voice assistant.",
    )
    business_id: Optional[UUID] = Field(
        default=None,
        description="Target business UUID. Verified against organization ownership.",
    )
    access_mode: VoiceAccessMode = Field(
        default=VoiceAccessMode.ORGANIZATION_MEMBER,
        description="Authorization policy mode ('organization_member' or 'public_visitor').",
    )
    public_access_token: Optional[str] = Field(
        default=None,
        min_length=16,
        max_length=2048,
        description="Required signed public-business access token when access_mode='public_visitor'.",
    )
    voice_override: Optional[RealtimeVoicePreset] = Field(
        default=None,
        description="Optional safe voice preset selection from allowed Realtime voices.",
    )

    @field_validator("public_access_token")
    @classmethod
    def clean_public_token(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None


class PublicVoiceTokenCreateRequest(BaseModel):
    """Request by an organization owner/admin to mint a deliberate public visitor token."""

    model_config = ConfigDict(extra="forbid")

    ttl_seconds: Optional[int] = Field(
        default=None,
        ge=60,
        le=86400,
        description="Optional token lifetime in seconds (60s to 24h).",
    )


class PublicVoiceTokenResponse(BaseModel):
    """Deliberate short-lived public visitor access token bound to a specific business."""

    organization_id: UUID
    business_id: UUID
    industry: OrganizationIndustry
    public_access_token: str
    expires_at: datetime
    ttl_seconds: int


class EphemeralClientSecret(BaseModel):
    """Short-lived ephemeral client credential for browser WebRTC SDP exchange."""

    value: str = Field(
        ...,
        description="Short-lived ephemeral OpenAI Realtime client token (never the permanent API key).",
    )
    expires_at: datetime = Field(
        ...,
        description="UTC timestamp when the ephemeral client credential expires.",
    )
    ttl_seconds: int = Field(
        ...,
        ge=1,
        description="Remaining lifetime in seconds at session creation time.",
    )


class SafeVoiceAssistantContext(BaseModel):
    """Sanitized assistant metadata returned to the browser UI for display."""

    business_name: str
    assistant_name: str
    greeting: str
    primary_language: LanguageCode
    supported_languages: List[LanguageCode]
    personality: AssistantPersonality
    response_style: AssistantResponseStyle
    assistant_enabled: bool
    administrative_only_guardrails: bool
    audio_persistence_enabled: bool = False
    transcript_persistence_enabled: bool = False


class VoiceSessionCapabilities(BaseModel):
    """Explicit capabilities permitted for a Stage 3 shared voice session."""

    modalities: List[str]
    barge_in_enabled: bool = True
    raw_audio_storage_enabled: bool = False
    transcript_storage_enabled: bool = False
    appointment_booking_enabled: bool = False
    industry_workflows_enabled: bool = False


class VoiceSessionCreateResponse(BaseModel):
    """Sanitized response from `POST /api/v1/voice/sessions` for WebRTC negotiation."""

    session_id: str
    organization_id: UUID
    business_id: UUID
    industry: OrganizationIndustry
    access_mode: VoiceAccessMode
    model: str
    voice: str
    webrtc_url: str
    webrtc_calls_url: str
    data_channel_label: str = "oai-events"
    client_secret: EphemeralClientSecret
    capabilities: VoiceSessionCapabilities
    assistant_context: SafeVoiceAssistantContext
