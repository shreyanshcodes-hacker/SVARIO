"""Domain service for White-Label Booking Website Engine (Stage 1 + Stage 2 Dynamic Public Engine)."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import re
import time
from typing import Any, Deque, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.schemas import OrganizationIndustry, OrganizationRole
from app.modules.websites.repository import (
    BookingWebsiteRecord,
    BookingWebsiteRepositoryProtocol,
    get_booking_website_repository,
)
from app.modules.websites.schemas import (
    BookingWebsiteButtonStyle,
    BookingWebsiteConfigResponse,
    BookingWebsiteDraftUpdateRequest,
    BookingWebsiteFontFamily,
    BookingWebsitePublishReadiness,
    BookingWebsiteStatus,
    BookingWebsiteTemplateId,
    BookingWebsiteTheme,
    BrandAssetUploadResponse,
    PublicBookingWebsiteResponse,
    PublicBusinessHour,
    PublicBusinessProfile,
    PublicReceptionistInfo,
    PublicSalonService,
    RESERVED_WEBSITE_SLUGS,
    SlugAvailabilityResponse,
    normalize_website_slug,
)

MAX_BRAND_ASSET_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_IMAGE_MIME_TYPES: Dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

# Stage 2 Dynamic Public Booking Website Engine is active.
PUBLIC_WEBSITE_ENGINE_READY = True


class PublicWebsiteRateLimiter:
    """In-process sliding-window IP rate limiter for public /s/[slug] API endpoints."""

    def __init__(self, *, max_requests: int = 60, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = {}

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        key = (client_ip or "unknown").strip() or "unknown"
        bucket = self._hits.setdefault(key, deque())
        cutoff = now - self._window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
            )
        bucket.append(now)


_public_rate_limiter = PublicWebsiteRateLimiter(max_requests=60, window_seconds=60)


def _verify_image_magic_bytes(content_type: str, data: bytes) -> bool:
    """Verify binary image headers match the declared MIME type."""
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _derive_default_slug(org_slug: str, business_name: str, business_id: UUID) -> str:
    """Derive a clean, non-reserved default slug from organization slug or business name."""
    for candidate in (org_slug, business_name):
        cleaned = re.sub(r"[^a-z0-9]+", "-", (candidate or "").strip().lower()).strip("-")
        cleaned = re.sub(r"-{2,}", "-", cleaned)
        if 3 <= len(cleaned) <= 64 and cleaned not in RESERVED_WEBSITE_SLUGS:
            return cleaned
    return f"salon-{business_id.hex[:8]}"


class BookingWebsiteService:
    """Orchestrates tenant-scoped booking website configuration, validation, and brand uploads."""

    def __init__(
        self,
        settings: Settings,
        onboarding_service: OnboardingService,
        website_repo: BookingWebsiteRepositoryProtocol,
        salon_repo: Any = None,
        rate_limiter: Optional[PublicWebsiteRateLimiter] = None,
    ) -> None:
        self._settings = settings
        self._onboarding_service = onboarding_service
        self._website_repo = website_repo
        self._salon_repo = salon_repo
        self._rate_limiter = rate_limiter or _public_rate_limiter

    async def _require_salon_bundle(
        self,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        require_admin: bool = False,
    ) -> OnboardingBundleResponse:
        bundle = await self._onboarding_service.get_onboarding_bundle(
            actor=actor, organization_id=organization_id
        )
        if bundle.organization.industry != OrganizationIndustry.SALON:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking Website configuration is currently available for salon organizations only.",
            )
        if require_admin and bundle.organization.membership_role not in {
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions: only organization owners or admins may modify booking website settings.",
            )
        return bundle

    def _evaluate_publish_readiness(
        self,
        record: BookingWebsiteRecord,
        bundle: OnboardingBundleResponse,
    ) -> BookingWebsitePublishReadiness:
        missing: List[str] = []
        if not bundle.profile.display_name or len(bundle.profile.display_name.strip()) < 2:
            missing.append("Business display name is required.")
        if not bundle.profile.phone and not bundle.profile.email:
            missing.append("At least one contact method (phone or email) is required.")
        if not record.slug or len(record.slug.strip()) < 3:
            missing.append("A valid unique website slug is required.")
        try:
            BookingWebsiteTemplateId(record.template_id.value)
        except Exception:
            missing.append("A valid approved website template must be selected.")
        if not any(not h.is_closed for h in (bundle.hours.schedule or [])):
            missing.append("At least one open operating day is required in business hours.")

        is_valid = len(missing) == 0
        can_publish = is_valid and PUBLIC_WEBSITE_ENGINE_READY
        return BookingWebsitePublishReadiness(
            is_valid=is_valid,
            public_engine_ready=PUBLIC_WEBSITE_ENGINE_READY,
            can_publish=can_publish,
            missing_requirements=missing,
        )

    async def _to_response(
        self,
        actor: AuthenticatedUser,
        record: BookingWebsiteRecord,
        bundle: OnboardingBundleResponse,
    ) -> BookingWebsiteConfigResponse:
        readiness = self._evaluate_publish_readiness(record, bundle)
        public_path = (
            f"/s/{record.slug}"
            if PUBLIC_WEBSITE_ENGINE_READY and record.status == BookingWebsiteStatus.PUBLISHED
            else None
        )
        logo_url = await self._website_repo.resolve_asset_url(actor, record.logo_path)
        cover_url = await self._website_repo.resolve_asset_url(actor, record.cover_image_path)
        return BookingWebsiteConfigResponse(
            id=record.id,
            organization_id=record.organization_id,
            business_id=record.business_id,
            slug=record.slug,
            template_id=record.template_id,
            status=record.status,
            published_at=record.published_at,
            headline=record.headline,
            tagline=record.tagline,
            logo_path=record.logo_path,
            logo_url=logo_url,
            cover_image_path=record.cover_image_path,
            cover_image_url=cover_url,
            primary_color=record.primary_color,
            secondary_color=record.secondary_color,
            accent_color=record.accent_color,
            background_color=record.background_color,
            text_color=record.text_color,
            theme=record.theme,
            font_family=record.font_family,
            button_style=record.button_style,
            social_instagram=record.social_instagram,
            social_facebook=record.social_facebook,
            social_whatsapp=record.social_whatsapp,
            show_services=record.show_services,
            show_hours=record.show_hours,
            show_ai_receptionist=record.show_ai_receptionist,
            preview_url_path=f"/s/{record.slug}",
            public_url_path=public_path,
            publish_readiness=readiness,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def get_or_init_website_config(
        self, *, actor: AuthenticatedUser, organization_id: UUID
    ) -> BookingWebsiteConfigResponse:
        """Retrieve existing booking website config or initialize a safe draft for the salon."""
        bundle = await self._require_salon_bundle(
            actor=actor, organization_id=organization_id, require_admin=False
        )
        existing = await self._website_repo.get_by_business(
            actor, bundle.organization.id, bundle.business_id
        )
        if existing is not None:
            return await self._to_response(actor, existing, bundle)

        base_slug = _derive_default_slug(
            bundle.organization.slug,
            bundle.profile.display_name,
            bundle.business_id,
        )
        candidate_slug = base_slug
        if await self._website_repo.is_slug_taken(
            actor, candidate_slug, exclude_business_id=bundle.business_id
        ):
            candidate_slug = f"{base_slug[:55]}-{bundle.business_id.hex[:6]}"

        default_payload = {
            "organization_id": str(bundle.organization.id),
            "business_id": str(bundle.business_id),
            "slug": candidate_slug,
            "template_id": BookingWebsiteTemplateId.LUXE_STUDIO.value,
            "status": BookingWebsiteStatus.DRAFT.value,
            "headline": f"Book your next visit at {bundle.profile.display_name}",
            "tagline": bundle.profile.description
            or "Effortless salon appointments with instant AI voice & online scheduling.",
            "primary_color": "#7657F6",
            "secondary_color": "#36C6D3",
            "accent_color": "#F59E0B",
            "background_color": "#0B1020",
            "text_color": "#F5F7FC",
            "theme": "dark",
            "font_family": "inter",
            "button_style": "rounded",
            "show_services": True,
            "show_hours": True,
            "show_ai_receptionist": True,
        }

        # Staff members can view default preview config without triggering an INSERT RLS denial
        if bundle.organization.membership_role not in {
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        }:
            ephemeral = BookingWebsiteRecord({"id": str(uuid4()), **default_payload})
            return await self._to_response(actor, ephemeral, bundle)

        created = await self._website_repo.create_config(actor, default_payload)
        return await self._to_response(actor, created, bundle)

    async def check_slug_availability(
        self, *, actor: AuthenticatedUser, organization_id: UUID, raw_slug: str
    ) -> SlugAvailabilityResponse:
        """Validate slug format, reserved-name protection, and cross-tenant uniqueness."""
        bundle = await self._require_salon_bundle(
            actor=actor, organization_id=organization_id, require_admin=False
        )
        try:
            normalized = normalize_website_slug(raw_slug)
        except ValueError as exc:
            return SlugAvailabilityResponse(
                requested_slug=raw_slug,
                normalized_slug=None,
                available=False,
                reason=str(exc),
            )

        taken = await self._website_repo.is_slug_taken(
            actor, normalized, exclude_business_id=bundle.business_id
        )
        if taken:
            return SlugAvailabilityResponse(
                requested_slug=raw_slug,
                normalized_slug=normalized,
                available=False,
                reason=f"'{normalized}' is already in use by another salon.",
            )
        return SlugAvailabilityResponse(
            requested_slug=raw_slug,
            normalized_slug=normalized,
            available=True,
            reason=None,
        )

    async def save_draft(
        self,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: BookingWebsiteDraftUpdateRequest,
    ) -> BookingWebsiteConfigResponse:
        """Validate and persist draft website/branding/slug changes (Owner/Admin only)."""
        bundle = await self._require_salon_bundle(
            actor=actor, organization_id=organization_id, require_admin=True
        )
        existing = await self._website_repo.get_by_business(
            actor, bundle.organization.id, bundle.business_id
        )
        if existing is None:
            await self.get_or_init_website_config(actor=actor, organization_id=organization_id)

        updates = payload.model_dump(exclude_unset=True)
        for enum_key in ("template_id", "theme", "font_family", "button_style"):
            if enum_key in updates and updates[enum_key] is not None:
                val = updates[enum_key]
                updates[enum_key] = val.value if hasattr(val, "value") else str(val)

        if "slug" in updates and updates["slug"] is not None:
            taken = await self._website_repo.is_slug_taken(
                actor, str(updates["slug"]), exclude_business_id=bundle.business_id
            )
            if taken:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Website slug '{updates['slug']}' is already claimed by another salon.",
                )

        if not updates:
            current = await self._website_repo.get_by_business(
                actor, bundle.organization.id, bundle.business_id
            )
            assert current is not None
            return await self._to_response(actor, current, bundle)

        updated = await self._website_repo.update_config(
            actor, bundle.organization.id, bundle.business_id, updates
        )
        return await self._to_response(actor, updated, bundle)

    async def upload_brand_asset(
        self,
        *,
        actor: AuthenticatedUser,
        organization_id: UUID,
        asset_type: str,
        content_type: str,
        data: bytes,
    ) -> BrandAssetUploadResponse:
        """Validate and upload a brand logo or cover image to tenant-scoped Supabase Storage."""
        if asset_type not in {"logo", "cover"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="asset_type must be 'logo' or 'cover'.",
            )
        bundle = await self._require_salon_bundle(
            actor=actor, organization_id=organization_id, require_admin=True
        )
        normalized_mime = (content_type or "").split(";")[0].strip().lower()
        if normalized_mime not in ALLOWED_IMAGE_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported image format. Upload a PNG, JPEG, or WEBP image.",
            )
        if not data or len(data) > MAX_BRAND_ASSET_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image file must be non-empty and at most 2 MB.",
            )
        if not _verify_image_magic_bytes(normalized_mime, data):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contents do not match the declared image type.",
            )

        existing = await self._website_repo.get_by_business(
            actor, bundle.organization.id, bundle.business_id
        )
        if existing is None:
            await self.get_or_init_website_config(actor=actor, organization_id=organization_id)

        ext = ALLOWED_IMAGE_MIME_TYPES[normalized_mime]
        storage_path = f"{bundle.organization.id}/{bundle.business_id}/{asset_type}-{uuid4().hex[:12]}.{ext}"
        public_url = await self._website_repo.upload_brand_asset(
            actor,
            bundle.organization.id,
            bundle.business_id,
            storage_path,
            normalized_mime,
            data,
        )

        field_name = "logo_path" if asset_type == "logo" else "cover_image_path"
        await self._website_repo.update_config(
            actor,
            bundle.organization.id,
            bundle.business_id,
            {field_name: storage_path},
        )

        return BrandAssetUploadResponse(
            asset_type=asset_type,
            storage_path=storage_path,
            public_url=public_url,
            content_type=normalized_mime,
            size_bytes=len(data),
        )

    async def publish_website(
        self, *, actor: AuthenticatedUser, organization_id: UUID
    ) -> BookingWebsiteConfigResponse:
        """Guard publishing behind completeness validation and Stage 2 public engine availability."""
        bundle = await self._require_salon_bundle(
            actor=actor, organization_id=organization_id, require_admin=True
        )
        existing = await self._website_repo.get_by_business(
            actor, bundle.organization.id, bundle.business_id
        )
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Save your booking website draft configuration before publishing.",
            )
        readiness = self._evaluate_publish_readiness(existing, bundle)
        if not readiness.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot publish incomplete website: " + " ".join(readiness.missing_requirements),
            )
        if not PUBLIC_WEBSITE_ENGINE_READY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Publishing is disabled in Stage 1: the public customer-facing website engine "
                    "(/s/[slug]) is pending Stage 2. Your draft configuration and preview are saved."
                ),
            )
        updated = await self._website_repo.update_config(
            actor,
            bundle.organization.id,
            bundle.business_id,
            {
                "status": BookingWebsiteStatus.PUBLISHED.value,
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return await self._to_response(actor, updated, bundle)

    async def unpublish_website(
        self, *, actor: AuthenticatedUser, organization_id: UUID
    ) -> BookingWebsiteConfigResponse:
        """Transition website back to draft status (Owner/Admin only)."""
        bundle = await self._require_salon_bundle(
            actor=actor, organization_id=organization_id, require_admin=True
        )
        existing = await self._website_repo.get_by_business(
            actor, bundle.organization.id, bundle.business_id
        )
        if existing is None:
            return await self.get_or_init_website_config(actor=actor, organization_id=organization_id)
        updated = await self._website_repo.update_config(
            actor,
            bundle.organization.id,
            bundle.business_id,
            {"status": BookingWebsiteStatus.DRAFT.value, "published_at": None},
        )
        return await self._to_response(actor, updated, bundle)

    def _build_inmemory_public_payload(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Hydrate strictly allowlisted public payload from in-memory repositories (tests/local)."""
        ob_repo = getattr(self._onboarding_service, "_repo", None) or getattr(
            self._onboarding_service, "_repository", None
        )
        if ob_repo is None:
            return None
        org_id = UUID(str(row["organization_id"]))
        biz_id = UUID(str(row["business_id"]))

        org_repo = getattr(ob_repo, "_org_repo", None)
        if org_repo is not None:
            org = getattr(org_repo, "_organizations", {}).get(org_id)
            org_industry = org.get("industry") if isinstance(org, dict) else getattr(org, "industry", None)
            if org is None or str(getattr(org_industry, "value", org_industry)) != OrganizationIndustry.SALON.value:
                return None

        profiles = getattr(ob_repo, "_profiles", {})
        profile = profiles.get(biz_id)
        if profile is None:
            return None

        hours_list: List[Dict[str, Any]] = []
        if bool(row.get("show_hours", True)):
            raw_hours_obj = getattr(ob_repo, "_hours", {}).get(biz_id)
            raw_hours = getattr(raw_hours_obj, "schedule", raw_hours_obj) if raw_hours_obj is not None else []
            for h in sorted(raw_hours, key=lambda x: x.weekday):
                hours_list.append(
                    {
                        "weekday": h.weekday,
                        "is_closed": h.is_closed,
                        "opens_at": h.opens_at,
                        "closes_at": h.closes_at,
                        "is_overnight": getattr(h, "is_overnight", False),
                    }
                )

        services_list: List[Dict[str, Any]] = []
        if bool(row.get("show_services", True)) and self._salon_repo is not None:
            raw_map = getattr(self._salon_repo, "_services", {})
            raw_svcs = []
            for val in raw_map.values():
                if isinstance(val, list):
                    raw_svcs.extend(val)
                else:
                    raw_svcs.append(val)
            for s in raw_svcs:
                if (
                    getattr(s, "business_id", None) == biz_id
                    and getattr(s, "organization_id", None) == org_id
                    and getattr(s, "is_active", False)
                ):
                    services_list.append(
                        {
                            "id": str(s.id),
                            "name": s.name,
                            "category": s.category,
                            "description": s.description,
                            "duration_minutes": s.duration_minutes,
                            "price": float(s.price),
                            "currency": s.currency,
                        }
                    )

        assistant = getattr(ob_repo, "_assistant", {}).get(biz_id)
        show_ai = bool(row.get("show_ai_receptionist", True)) and bool(
            assistant and getattr(assistant, "enabled", False)
        )
        receptionist = {
            "enabled": show_ai,
            "assistant_name": assistant.assistant_name if show_ai and assistant else None,
            "greeting": assistant.greeting if show_ai and assistant else None,
        }

        return {
            **row,
            "business": {
                "display_name": profile.display_name,
                "description": profile.description,
                "phone": profile.phone,
                "email": profile.email,
                "address": profile.address,
                "city": profile.city,
                "state": profile.state,
                "country": profile.country,
                "timezone": profile.timezone,
            },
            "hours": hours_list,
            "services": services_list,
            "receptionist": receptionist,
        }

    async def get_public_website_by_slug(
        self, *, slug: str, client_ip: str = "unknown"
    ) -> PublicBookingWebsiteResponse:
        """Resolve a published salon website by normalized slug with strict public allowlist."""
        self._rate_limiter.check(client_ip)
        try:
            normalized = normalize_website_slug(slug)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking website not found.",
            )

        raw = await self._website_repo.get_published_by_slug(normalized)
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking website not found.",
            )

        if "business" not in raw:
            hydrated = self._build_inmemory_public_payload(raw)
            if hydrated is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Booking website not found.",
                )
            raw = hydrated

        raw_template = str(raw.get("template_id") or BookingWebsiteTemplateId.LUXE_STUDIO.value)
        try:
            template_id = BookingWebsiteTemplateId(raw_template)
        except ValueError:
            template_id = BookingWebsiteTemplateId.LUXE_STUDIO

        has_logo = bool(raw.get("has_logo")) or bool(raw.get("logo_path"))
        has_cover = bool(raw.get("has_cover")) or bool(raw.get("cover_image_path"))
        logo_url = (
            f"/api/v1/public/websites/{normalized}/assets/logo"
            if has_logo
            else None
        )
        cover_url = (
            f"/api/v1/public/websites/{normalized}/assets/cover"
            if has_cover
            else None
        )

        biz = raw.get("business") or {}
        rec = raw.get("receptionist") or {}
        raw_hours = raw.get("hours") or []
        raw_services = raw.get("services") or []

        return PublicBookingWebsiteResponse(
            slug=normalized,
            template_id=template_id,
            published_at=raw.get("published_at"),
            headline=raw.get("headline"),
            tagline=raw.get("tagline"),
            logo_url=logo_url,
            cover_image_url=cover_url,
            primary_color=str(raw.get("primary_color") or "#7657F6"),
            secondary_color=str(raw.get("secondary_color") or "#36C6D3"),
            accent_color=str(raw.get("accent_color") or "#F59E0B"),
            background_color=str(raw.get("background_color") or "#0B1020"),
            text_color=str(raw.get("text_color") or "#F5F7FC"),
            theme=BookingWebsiteTheme(str(raw.get("theme") or "dark")),
            font_family=BookingWebsiteFontFamily(str(raw.get("font_family") or "inter")),
            button_style=BookingWebsiteButtonStyle(str(raw.get("button_style") or "rounded")),
            social_instagram=raw.get("social_instagram"),
            social_facebook=raw.get("social_facebook"),
            social_whatsapp=raw.get("social_whatsapp"),
            show_services=bool(raw.get("show_services", True)),
            show_hours=bool(raw.get("show_hours", True)),
            show_ai_receptionist=bool(raw.get("show_ai_receptionist", True)),
            business=PublicBusinessProfile(
                display_name=str(biz.get("display_name") or ""),
                description=biz.get("description"),
                phone=biz.get("phone"),
                email=biz.get("email"),
                address=biz.get("address"),
                city=biz.get("city"),
                state=biz.get("state"),
                country=biz.get("country"),
                timezone=str(biz.get("timezone") or "Asia/Kolkata"),
            ),
            hours=[
                PublicBusinessHour(
                    weekday=int(h["weekday"]),
                    is_closed=bool(h.get("is_closed", False)),
                    opens_at=h.get("opens_at"),
                    closes_at=h.get("closes_at"),
                    is_overnight=bool(h.get("is_overnight", False)),
                )
                for h in raw_hours
            ],
            services=[
                PublicSalonService(
                    id=UUID(str(s["id"])),
                    name=str(s["name"]),
                    category=s.get("category"),
                    description=s.get("description"),
                    duration_minutes=int(s["duration_minutes"]),
                    price=float(s["price"]),
                    currency=str(s.get("currency") or "INR"),
                )
                for s in raw_services
            ],
            receptionist=PublicReceptionistInfo(
                enabled=bool(rec.get("enabled", False)),
                assistant_name=rec.get("assistant_name"),
                greeting=rec.get("greeting"),
            ),
        )

    async def get_public_website_asset(
        self, *, slug: str, asset_type: str, client_ip: str = "unknown"
    ) -> Tuple[bytes, str]:
        """Stream a published website's logo or cover image via trusted server-side resolution."""
        self._rate_limiter.check(client_ip)
        if asset_type not in {"logo", "cover"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found.",
            )
        try:
            normalized = normalize_website_slug(slug)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found.",
            )

        fetched = await self._website_repo.fetch_published_brand_asset_by_slug(
            normalized, asset_type
        )
        if fetched is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found.",
            )
        return fetched


def get_booking_website_service(
    settings: Settings = Depends(get_settings),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    website_repo: BookingWebsiteRepositoryProtocol = Depends(get_booking_website_repository),
) -> BookingWebsiteService:
    """FastAPI dependency returning a configured BookingWebsiteService."""
    return BookingWebsiteService(
        settings=settings,
        onboarding_service=onboarding_service,
        website_repo=website_repo,
    )
