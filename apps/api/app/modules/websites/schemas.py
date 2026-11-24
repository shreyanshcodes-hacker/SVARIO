"""Pydantic v2 schemas and strict validation helpers for White-Label Booking Website Engine (Stage 1)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
import re
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX_COLOR_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HTML_TAG_REGEX = re.compile(r"<[^>]+>")

RESERVED_WEBSITE_SLUGS = frozenset(
    {
        "api",
        "admin",
        "app",
        "assets",
        "auth",
        "billing",
        "booking",
        "bookings",
        "clinic",
        "clinics",
        "dashboard",
        "docs",
        "forgot-password",
        "health",
        "help",
        "hospital",
        "hospitals",
        "login",
        "logout",
        "onboarding",
        "pricing",
        "privacy",
        "public",
        "reset-password",
        "s",
        "salon",
        "salons",
        "settings",
        "signup",
        "static",
        "status",
        "support",
        "svario",
        "terms",
        "voice",
        "voice-test",
        "www",
    }
)


class BookingWebsiteStatus(str, Enum):
    """Lifecycle status for a tenant's white-label booking website."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class BookingWebsiteTheme(str, Enum):
    """Approved safe theme modes."""

    DARK = "dark"
    LIGHT = "light"


class BookingWebsiteFontFamily(str, Enum):
    """Predefined safe typography choices (no arbitrary CSS/font URLs)."""

    INTER = "inter"
    PLUS_JAKARTA_SANS = "plus_jakarta_sans"
    DM_SANS = "dm_sans"
    PLAYFAIR_DISPLAY = "playfair_display"
    POPPINS = "poppins"


class BookingWebsiteButtonStyle(str, Enum):
    """Approved button corner styles."""

    ROUNDED = "rounded"
    PILL = "pill"
    SQUARE = "square"


class BookingWebsiteTemplateId(str, Enum):
    """Explicit server-controlled registry of approved Stage 2 salon website templates."""

    LUXE_STUDIO = "luxe_studio"
    MINIMAL_ELEGANCE = "minimal_elegance"
    BLUSH_BEAUTY = "blush_beauty"
    NOIR_SALON = "noir_salon"
    ORGANIC_GLOW = "organic_glow"
    URBAN_CHIC = "urban_chic"
    EDITORIAL_PRO = "editorial_pro"
    CLASSIC_BEAUTY = "classic_beauty"


def normalize_website_slug(raw: str) -> str:
    """Normalize a raw slug string into lowercase kebab-case and validate format/reserved names."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (raw or "").strip().lower()).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    if len(cleaned) < 3 or len(cleaned) > 64:
        raise ValueError("Website slug must be between 3 and 64 characters (letters, numbers, hyphens).")
    if not SLUG_REGEX.match(cleaned):
        raise ValueError("Website slug must contain only lowercase letters, numbers, and single hyphens.")
    if cleaned in RESERVED_WEBSITE_SLUGS:
        raise ValueError(f"'{cleaned}' is a reserved route name and cannot be used as a booking website slug.")
    return cleaned


def validate_hex_color(raw: str, field_name: str = "color") -> str:
    """Validate strict 6-digit hex color to prevent CSS injection."""
    cleaned = (raw or "").strip()
    if not HEX_COLOR_REGEX.match(cleaned):
        raise ValueError(f"{field_name} must be a valid 6-digit hex color (e.g. #7657F6).")
    return cleaned.upper()


def validate_safe_text(raw: Optional[str], *, max_len: int = 240) -> Optional[str]:
    """Strip whitespace and reject raw HTML tags to prevent HTML/script injection."""
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if HTML_TAG_REGEX.search(cleaned):
        raise ValueError("HTML markup is not permitted in website text fields.")
    if len(cleaned) > max_len:
        raise ValueError(f"Text must be at most {max_len} characters.")
    return cleaned


def validate_safe_social_url(raw: Optional[str]) -> Optional[str]:
    """Allow only http(s) URLs or clean @handles for social links."""
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    lower = cleaned.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:")):
        raise ValueError("Unsafe URL scheme is not permitted.")
    if HTML_TAG_REGEX.search(cleaned):
        raise ValueError("HTML markup is not permitted in social links.")
    if len(cleaned) > 255:
        raise ValueError("Social link must be at most 255 characters.")
    return cleaned


class BookingWebsitePublishReadiness(BaseModel):
    """Validation summary indicating whether a salon website meets publishing prerequisites."""

    is_valid: bool
    public_engine_ready: bool = True
    can_publish: bool = False
    missing_requirements: List[str] = Field(default_factory=list)
    stage_notice: str = (
        "Stage 2 Dynamic Engine: Select from 8 templates, preview with your live salon data, "
        "and publish to your public /s/[slug] URL when ready."
    )


class BookingWebsiteConfigResponse(BaseModel):
    """Complete tenant-scoped booking website configuration returned to authorized members."""

    id: UUID
    organization_id: UUID
    business_id: UUID
    slug: str
    template_id: BookingWebsiteTemplateId = BookingWebsiteTemplateId.LUXE_STUDIO
    status: BookingWebsiteStatus
    published_at: Optional[datetime] = None
    headline: Optional[str] = None
    tagline: Optional[str] = None
    logo_path: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_path: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str = "#7657F6"
    secondary_color: str = "#36C6D3"
    accent_color: str = "#F59E0B"
    background_color: str = "#0B1020"
    text_color: str = "#F5F7FC"
    theme: BookingWebsiteTheme = BookingWebsiteTheme.DARK
    font_family: BookingWebsiteFontFamily = BookingWebsiteFontFamily.INTER
    button_style: BookingWebsiteButtonStyle = BookingWebsiteButtonStyle.ROUNDED
    social_instagram: Optional[str] = None
    social_facebook: Optional[str] = None
    social_whatsapp: Optional[str] = None
    show_services: bool = True
    show_hours: bool = True
    show_ai_receptionist: bool = True
    preview_url_path: str
    public_url_path: Optional[str] = None
    publish_readiness: BookingWebsitePublishReadiness
    created_at: datetime
    updated_at: datetime


class BookingWebsiteDraftUpdateRequest(BaseModel):
    """Strict payload to save booking website draft settings (Owner/Admin only)."""

    model_config = ConfigDict(extra="forbid")

    slug: Optional[str] = Field(default=None, min_length=3, max_length=80)
    template_id: Optional[BookingWebsiteTemplateId] = None
    headline: Optional[str] = Field(default=None, max_length=140)
    tagline: Optional[str] = Field(default=None, max_length=240)
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    theme: Optional[BookingWebsiteTheme] = None
    font_family: Optional[BookingWebsiteFontFamily] = None
    button_style: Optional[BookingWebsiteButtonStyle] = None
    social_instagram: Optional[str] = Field(default=None, max_length=255)
    social_facebook: Optional[str] = Field(default=None, max_length=255)
    social_whatsapp: Optional[str] = Field(default=None, max_length=255)
    show_services: Optional[bool] = None
    show_hours: Optional[bool] = None
    show_ai_receptionist: Optional[bool] = None

    @field_validator("slug")
    @classmethod
    def check_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_website_slug(value)

    @field_validator("headline")
    @classmethod
    def check_headline(cls, value: Optional[str]) -> Optional[str]:
        return validate_safe_text(value, max_len=140)

    @field_validator("tagline")
    @classmethod
    def check_tagline(cls, value: Optional[str]) -> Optional[str]:
        return validate_safe_text(value, max_len=240)

    @field_validator(
        "primary_color",
        "secondary_color",
        "accent_color",
        "background_color",
        "text_color",
    )
    @classmethod
    def check_colors(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_hex_color(value)

    @field_validator("social_instagram", "social_facebook", "social_whatsapp")
    @classmethod
    def check_social_links(cls, value: Optional[str]) -> Optional[str]:
        return validate_safe_social_url(value)


class SlugAvailabilityResponse(BaseModel):
    """Response for checking whether a normalized booking website slug is available."""

    requested_slug: str
    normalized_slug: Optional[str] = None
    available: bool
    reason: Optional[str] = None


class BrandAssetUploadResponse(BaseModel):
    """Response returned after securely uploading a brand logo or cover image."""

    asset_type: str
    storage_path: str
    public_url: str
    content_type: str
    size_bytes: int


class PublicBusinessProfile(BaseModel):
    """Strictly allowlisted public salon profile fields for /s/[slug]."""

    display_name: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    timezone: str = "Asia/Kolkata"


class PublicBusinessHour(BaseModel):
    """Publicly visible operating hours for a weekday (0=Sunday..6=Saturday)."""

    weekday: int
    is_closed: bool
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
    is_overnight: bool = False


class PublicSalonService(BaseModel):
    """Strictly allowlisted active public salon service item."""

    id: UUID
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: int
    price: float
    currency: str = "INR"


class PublicReceptionistInfo(BaseModel):
    """Safe public AI receptionist metadata (never exposes internal prompts or secrets)."""

    enabled: bool = False
    assistant_name: Optional[str] = None
    greeting: Optional[str] = None


class PublicBookingWebsiteResponse(BaseModel):
    """Strictly allowlisted public website payload returned by GET /api/v1/public/websites/{slug}."""

    slug: str
    template_id: BookingWebsiteTemplateId = BookingWebsiteTemplateId.LUXE_STUDIO
    published_at: Optional[datetime] = None
    headline: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str = "#7657F6"
    secondary_color: str = "#36C6D3"
    accent_color: str = "#F59E0B"
    background_color: str = "#0B1020"
    text_color: str = "#F5F7FC"
    theme: BookingWebsiteTheme = BookingWebsiteTheme.DARK
    font_family: BookingWebsiteFontFamily = BookingWebsiteFontFamily.INTER
    button_style: BookingWebsiteButtonStyle = BookingWebsiteButtonStyle.ROUNDED
    social_instagram: Optional[str] = None
    social_facebook: Optional[str] = None
    social_whatsapp: Optional[str] = None
    show_services: bool = True
    show_hours: bool = True
    show_ai_receptionist: bool = True
    business: PublicBusinessProfile
    hours: List[PublicBusinessHour] = Field(default_factory=list)
    services: List[PublicSalonService] = Field(default_factory=list)
    receptionist: PublicReceptionistInfo = Field(default_factory=PublicReceptionistInfo)
