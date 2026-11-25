"""Repository layer for White-Label Booking Website Engine (In-Memory + Supabase PostgREST)."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional, Protocol, Tuple
from uuid import UUID, uuid4
import httpx
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.modules.websites.schemas import (
    BookingWebsiteButtonStyle,
    BookingWebsiteFontFamily,
    BookingWebsiteStatus,
    BookingWebsiteTemplateId,
    BookingWebsiteTheme,
)

BRAND_ASSETS_BUCKET = "salon-brand-assets"

SAFE_BRAND_ASSET_PATH_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/"
    r"(logo|cover)-[0-9a-f]{12}\.(png|jpg|webp)$"
)


def is_valid_brand_asset_path(
    storage_path: Optional[str],
    *,
    asset_type: Optional[str] = None,
    organization_id: Optional[UUID] = None,
    business_id: Optional[UUID] = None,
) -> bool:
    """Defense-in-depth validation for tenant-scoped Storage asset paths."""
    if not storage_path or ".." in storage_path or storage_path.startswith("/"):
        return False
    match = SAFE_BRAND_ASSET_PATH_REGEX.match(storage_path)
    if not match:
        return False
    if asset_type is not None and match.group(1) != asset_type:
        return False
    if organization_id is not None and business_id is not None:
        expected_prefix = f"{str(organization_id).lower()}/{str(business_id).lower()}/"
        if not storage_path.startswith(expected_prefix):
            return False
    return True


class BookingWebsiteRecord:
    """Internal domain record matching public.booking_website_configs."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.id: UUID = UUID(str(data["id"]))
        self.organization_id: UUID = UUID(str(data["organization_id"]))
        self.business_id: UUID = UUID(str(data["business_id"]))
        self.slug: str = str(data["slug"])
        raw_template = str(data.get("template_id") or BookingWebsiteTemplateId.LUXE_STUDIO.value)
        try:
            self.template_id: BookingWebsiteTemplateId = BookingWebsiteTemplateId(raw_template)
        except ValueError:
            self.template_id = BookingWebsiteTemplateId.LUXE_STUDIO
        self.status: BookingWebsiteStatus = BookingWebsiteStatus(str(data["status"]))
        self.published_at: Optional[datetime] = _parse_dt(data.get("published_at"))
        self.headline: Optional[str] = data.get("headline")
        self.tagline: Optional[str] = data.get("tagline")
        self.logo_path: Optional[str] = data.get("logo_path")
        self.cover_image_path: Optional[str] = data.get("cover_image_path")
        self.primary_color: str = str(data.get("primary_color") or "#7657F6")
        self.secondary_color: str = str(data.get("secondary_color") or "#36C6D3")
        self.accent_color: str = str(data.get("accent_color") or "#F59E0B")
        self.background_color: str = str(data.get("background_color") or "#0B1020")
        self.text_color: str = str(data.get("text_color") or "#F5F7FC")
        self.theme: BookingWebsiteTheme = BookingWebsiteTheme(str(data.get("theme") or "dark"))
        self.font_family: BookingWebsiteFontFamily = BookingWebsiteFontFamily(
            str(data.get("font_family") or "inter")
        )
        self.button_style: BookingWebsiteButtonStyle = BookingWebsiteButtonStyle(
            str(data.get("button_style") or "rounded")
        )
        self.social_instagram: Optional[str] = data.get("social_instagram")
        self.social_facebook: Optional[str] = data.get("social_facebook")
        self.social_whatsapp: Optional[str] = data.get("social_whatsapp")
        self.show_services: bool = bool(data.get("show_services", True))
        self.show_hours: bool = bool(data.get("show_hours", True))
        self.show_ai_receptionist: bool = bool(data.get("show_ai_receptionist", True))
        self.created_at: datetime = _parse_dt(data.get("created_at")) or datetime.now(timezone.utc)
        self.updated_at: datetime = _parse_dt(data.get("updated_at")) or datetime.now(timezone.utc)


def _parse_dt(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


class BookingWebsiteRepositoryProtocol(Protocol):
    """Protocol for tenant-scoped booking website persistence."""

    async def get_by_business(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> Optional[BookingWebsiteRecord]: ...

    async def is_slug_taken(
        self, actor: AuthenticatedUser, slug: str, *, exclude_business_id: UUID
    ) -> bool: ...

    async def create_config(
        self, actor: AuthenticatedUser, data: Dict[str, Any]
    ) -> BookingWebsiteRecord: ...

    async def update_config(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        updates: Dict[str, Any],
    ) -> BookingWebsiteRecord: ...

    async def upload_brand_asset(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        storage_path: str,
        content_type: str,
        data: bytes,
    ) -> str: ...

    async def resolve_asset_url(
        self, actor: AuthenticatedUser, storage_path: Optional[str]
    ) -> Optional[str]: ...

    async def get_published_by_slug(self, slug: str) -> Optional[Dict[str, Any]]: ...

    async def get_published_tenant_ids(self, slug: str) -> Optional[Tuple[UUID, UUID]]: ...

    async def fetch_published_brand_asset_by_slug(
        self, slug: str, asset_type: str
    ) -> Optional[Tuple[bytes, str]]: ...

    def build_public_asset_url(self, storage_path: Optional[str]) -> Optional[str]: ...


class InMemoryBookingWebsiteRepository:
    """In-memory repository used for unit tests and non-Supabase local dev."""

    def __init__(self) -> None:
        self._records_by_business: Dict[UUID, Dict[str, Any]] = {}
        self._assets: Dict[str, bytes] = {}
        self._asset_content_types: Dict[str, str] = {}

    def clear(self) -> None:
        self._records_by_business.clear()
        self._assets.clear()
        self._asset_content_types.clear()

    async def get_by_business(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> Optional[BookingWebsiteRecord]:
        row = self._records_by_business.get(business_id)
        if not row or UUID(str(row["organization_id"])) != organization_id:
            return None
        return BookingWebsiteRecord(row)

    async def is_slug_taken(
        self, actor: AuthenticatedUser, slug: str, *, exclude_business_id: UUID
    ) -> bool:
        target = slug.strip().lower()
        for biz_id, row in self._records_by_business.items():
            if biz_id != exclude_business_id and str(row["slug"]).strip().lower() == target:
                return True
        return False

    async def create_config(
        self, actor: AuthenticatedUser, data: Dict[str, Any]
    ) -> BookingWebsiteRecord:
        biz_id = UUID(str(data["business_id"]))
        slug_lower = str(data["slug"]).strip().lower()
        if await self.is_slug_taken(actor, slug_lower, exclude_business_id=biz_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Website slug '{slug_lower}' is already claimed by another salon.",
            )
        now = datetime.now(timezone.utc)
        row = {
            "id": str(data.get("id") or uuid4()),
            **data,
            "slug": slug_lower,
            "created_at": now,
            "updated_at": now,
        }
        self._records_by_business[biz_id] = row
        return BookingWebsiteRecord(row)

    async def update_config(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        updates: Dict[str, Any],
    ) -> BookingWebsiteRecord:
        row = self._records_by_business.get(business_id)
        if not row or UUID(str(row["organization_id"])) != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking website configuration not found.",
            )
        if "slug" in updates and updates["slug"] is not None:
            slug_lower = str(updates["slug"]).strip().lower()
            if await self.is_slug_taken(actor, slug_lower, exclude_business_id=business_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Website slug '{slug_lower}' is already claimed by another salon.",
                )
            updates["slug"] = slug_lower

        row.update(updates)
        row["updated_at"] = datetime.now(timezone.utc)
        return BookingWebsiteRecord(row)

    async def upload_brand_asset(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        storage_path: str,
        content_type: str,
        data: bytes,
    ) -> str:
        self._assets[storage_path] = data
        self._asset_content_types[storage_path] = content_type
        return self.build_public_asset_url(storage_path) or ""

    async def resolve_asset_url(
        self, actor: AuthenticatedUser, storage_path: Optional[str]
    ) -> Optional[str]:
        return self.build_public_asset_url(storage_path)

    async def get_published_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        target = slug.strip().lower()
        for row in self._records_by_business.values():
            if (
                str(row.get("slug", "")).strip().lower() == target
                and str(row.get("status", "")) == BookingWebsiteStatus.PUBLISHED.value
            ):
                return dict(row)
        return None

    async def get_published_tenant_ids(self, slug: str) -> Optional[Tuple[UUID, UUID]]:
        row = await self.get_published_by_slug(slug)
        if row is None:
            return None
        return UUID(str(row["organization_id"])), UUID(str(row["business_id"]))

    async def fetch_published_brand_asset_by_slug(
        self, slug: str, asset_type: str
    ) -> Optional[Tuple[bytes, str]]:
        if asset_type not in {"logo", "cover"}:
            return None
        row = await self.get_published_by_slug(slug)
        if row is None:
            return None
        storage_path = row.get("logo_path") if asset_type == "logo" else row.get("cover_image_path")
        org_id = UUID(str(row["organization_id"]))
        biz_id = UUID(str(row["business_id"]))
        if not is_valid_brand_asset_path(
            storage_path,
            asset_type=asset_type,
            organization_id=org_id,
            business_id=biz_id,
        ):
            return None
        assert isinstance(storage_path, str)
        data = self._assets.get(storage_path)
        if data is None:
            return None
        return data, self._asset_content_types.get(storage_path, "image/png")

    def build_public_asset_url(self, storage_path: Optional[str]) -> Optional[str]:
        if not storage_path:
            return None
        return f"https://storage.local/{BRAND_ASSETS_BUCKET}/{storage_path}"


class SupabaseRestBookingWebsiteRepository:
    """Supabase PostgREST + Storage implementation of BookingWebsiteRepositoryProtocol."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_live_supabase_configured or not settings.supabase_url or not settings.supabase_anon_key:
            raise RuntimeError("SupabaseRestBookingWebsiteRepository requires SUPABASE_URL and SUPABASE_ANON_KEY.")
        self._base_url = settings.supabase_url.strip().rstrip("/")
        self._anon_key = settings.supabase_anon_key.strip()
        self._service_role_key = (
            settings.supabase_service_role_key.strip()
            if settings.supabase_service_role_key and settings.supabase_service_role_key.strip()
            else None
        )

    def _headers(self, actor: AuthenticatedUser, *, prefer: str = "return=representation") -> Dict[str, str]:
        if not actor.raw_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user JWT is required for booking website persistence.",
            )
        return {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {actor.raw_token}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    @staticmethod
    def _handle_error(resp: httpx.Response, *, context: str) -> None:
        if resp.status_code < 400:
            return
        try:
            body = resp.json()
        except Exception:
            body = {}
        pg_code = str(body.get("code") or "")
        msg = str(body.get("message") or "")
        if pg_code == "23505" and "slug" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That website slug is already claimed by another salon.",
            )
        if pg_code == "42P01" or "booking_website_configs" in msg.lower() and "does not exist" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking website table migration (20261124000008_stage7_booking_website_foundation.sql) has not been applied to Supabase yet.",
            )
        if resp.status_code in {401, 403} or pg_code == "42501":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied by organization security policy.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Database error during {context}: {msg or resp.status_code}",
        )

    async def get_by_business(
        self, actor: AuthenticatedUser, organization_id: UUID, business_id: UUID
    ) -> Optional[BookingWebsiteRecord]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/booking_website_configs",
                headers=self._headers(actor),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                    "limit": "1",
                },
            )
            self._handle_error(resp, context="get_booking_website")
            rows = resp.json()
            return BookingWebsiteRecord(rows[0]) if rows else None

    async def is_slug_taken(
        self, actor: AuthenticatedUser, slug: str, *, exclude_business_id: UUID
    ) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            rpc_resp = await client.post(
                f"{self._base_url}/rest/v1/rpc/is_booking_website_slug_taken",
                headers=self._headers(actor),
                json={
                    "p_slug": slug.strip().lower(),
                    "p_exclude_business_id": str(exclude_business_id),
                },
            )
            if rpc_resp.status_code < 400:
                return bool(rpc_resp.json())

            # Fallback if Stage 2 RPC migration has not yet been applied
            resp = await client.get(
                f"{self._base_url}/rest/v1/booking_website_configs",
                headers=self._headers(actor),
                params={
                    "select": "business_id",
                    "slug": f"eq.{slug.strip().lower()}",
                    "limit": "1",
                },
            )
            self._handle_error(resp, context="check_slug_availability")
            rows = resp.json()
            if not rows:
                return False
            return UUID(str(rows[0]["business_id"])) != exclude_business_id

    async def create_config(
        self, actor: AuthenticatedUser, data: Dict[str, Any]
    ) -> BookingWebsiteRecord:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/booking_website_configs",
                headers=self._headers(actor),
                json=data,
            )
            self._handle_error(resp, context="create_booking_website")
            return BookingWebsiteRecord(resp.json()[0])

    async def update_config(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        updates: Dict[str, Any],
    ) -> BookingWebsiteRecord:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self._base_url}/rest/v1/booking_website_configs",
                headers=self._headers(actor),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "business_id": f"eq.{business_id}",
                },
                json=updates,
            )
            self._handle_error(resp, context="update_booking_website")
            rows = resp.json()
            if not rows:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Booking website configuration not found.",
                )
            return BookingWebsiteRecord(rows[0])

    async def upload_brand_asset(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        business_id: UUID,
        storage_path: str,
        content_type: str,
        data: bytes,
    ) -> str:
        if not actor.raw_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user JWT is required to upload brand assets.",
            )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/storage/v1/object/{BRAND_ASSETS_BUCKET}/{storage_path}",
                headers={
                    "apikey": self._anon_key,
                    "Authorization": f"Bearer {actor.raw_token}",
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=data,
            )
        if resp.status_code >= 400:
            upstream_detail = ""
            try:
                err_body = resp.json()
                if isinstance(err_body, dict):
                    raw_msg = err_body.get("message") or err_body.get("error") or ""
                    if isinstance(raw_msg, str) and raw_msg.strip():
                        upstream_detail = f": {raw_msg.strip()[:160]}"
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Brand asset upload failed (HTTP {resp.status_code}){upstream_detail}.",
            )
        return (await self.resolve_asset_url(actor, storage_path)) or ""

    async def resolve_asset_url(
        self, actor: AuthenticatedUser, storage_path: Optional[str]
    ) -> Optional[str]:
        if not storage_path or not actor.raw_token:
            return None
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/storage/v1/object/sign/{BRAND_ASSETS_BUCKET}/{storage_path}",
                headers={
                    "apikey": self._anon_key,
                    "Authorization": f"Bearer {actor.raw_token}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 3600},
            )
            if resp.status_code < 400:
                body = resp.json()
                signed = body.get("signedURL") or body.get("signedUrl")
                if isinstance(signed, str) and signed:
                    if signed.startswith("http"):
                        return signed
                    prefix = "/storage/v1" if not signed.startswith("/storage/v1") else ""
                    return f"{self._base_url}{prefix}{signed}"
        return None

    async def get_published_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Resolve a published salon website via strictly allowlisted SECURITY DEFINER RPC."""
        bearer = self._service_role_key or self._anon_key
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/rpc/get_published_booking_website_by_slug",
                headers={
                    "apikey": bearer,
                    "Authorization": f"Bearer {bearer}",
                    "Content-Type": "application/json",
                },
                json={"p_slug": slug.strip().lower()},
            )
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {}
            pg_code = str(body.get("code") or "")
            if pg_code in {"42883", "PGRST202"}:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Stage 2 public website migration (20261124000009_stage8_booking_website_templates_and_public_rpc.sql) has not been applied to Supabase yet.",
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to resolve public booking website right now.",
            )
        payload = resp.json()
        if not payload or not isinstance(payload, dict):
            return None
        return payload

    async def get_published_tenant_ids(self, slug: str) -> Optional[Tuple[UUID, UUID]]:
        """Resolve real (organization_id, business_id) strictly server-side using service_role ONLY."""
        if not self._service_role_key:
            return None
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/rpc/get_published_website_tenant_ids",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": "application/json",
                },
                json={"p_slug": slug.strip().lower()},
            )
        if resp.status_code >= 400:
            return None
        payload = resp.json()
        if not isinstance(payload, dict) or not payload.get("organization_id") or not payload.get("business_id"):
            return None
        return UUID(str(payload["organization_id"])), UUID(str(payload["business_id"]))

    async def fetch_published_brand_asset_by_slug(
        self, slug: str, asset_type: str
    ) -> Optional[Tuple[bytes, str]]:
        """Resolve and stream a published brand asset using ONLY backend service-role credentials."""
        if asset_type not in {"logo", "cover"}:
            return None
        if not self._service_role_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private brand asset proxy requires SUPABASE_SERVICE_ROLE_KEY on the backend.",
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            path_resp = await client.post(
                f"{self._base_url}/rest/v1/rpc/get_published_brand_asset_path",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                    "Content-Type": "application/json",
                },
                json={"p_slug": slug.strip().lower(), "p_asset_type": asset_type},
            )
            if path_resp.status_code >= 400:
                return None
            storage_path = path_resp.json()
            if not isinstance(storage_path, str) or not is_valid_brand_asset_path(
                storage_path, asset_type=asset_type
            ):
                return None

            resp = await client.get(
                f"{self._base_url}/storage/v1/object/{BRAND_ASSETS_BUCKET}/{storage_path}",
                headers={
                    "apikey": self._service_role_key,
                    "Authorization": f"Bearer {self._service_role_key}",
                },
            )
        if resp.status_code >= 400:
            return None
        content_type = (resp.headers.get("content-type") or "image/png").split(";")[0].strip().lower()
        if content_type not in {"image/png", "image/jpeg", "image/webp"}:
            content_type = "image/png"
        return resp.content, content_type

    def build_public_asset_url(self, storage_path: Optional[str]) -> Optional[str]:
        if not storage_path:
            return None
        return f"{self._base_url}/storage/v1/object/authenticated/{BRAND_ASSETS_BUCKET}/{storage_path}"


_in_memory_website_repo = InMemoryBookingWebsiteRepository()


def get_booking_website_repository(
    settings: Settings = Depends(get_settings),
) -> BookingWebsiteRepositoryProtocol:
    resolved = settings if isinstance(settings, Settings) else get_settings()
    if resolved.is_live_supabase_configured:
        return SupabaseRestBookingWebsiteRepository(resolved)
    return _in_memory_website_repo
