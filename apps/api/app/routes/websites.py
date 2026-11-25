"""API routes for White-Label Booking Website Engine (Stage 1 Dashboard + Stage 2 Public Engine)."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from app.agents.schemas import VoiceToolExecutionResponse
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.client_ip import resolve_client_ip
from app.core.config import Settings, get_settings
from app.modules.websites.public_voice import (
    PublicWebsiteVoiceBridgeService,
    get_public_website_voice_bridge_service,
)
from app.modules.websites.schemas import (
    BookingWebsiteConfigResponse,
    BookingWebsiteDraftUpdateRequest,
    BrandAssetUploadResponse,
    PublicBookingWebsiteResponse,
    PublicWebsiteVoiceSessionRequest,
    PublicWebsiteVoiceSessionResponse,
    PublicWebsiteVoiceToolRequest,
    SlugAvailabilityResponse,
)
from app.modules.websites.service import (
    BookingWebsiteService,
    MAX_BRAND_ASSET_BYTES,
    get_booking_website_service,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/booking-website",
    tags=["Booking Website (Stage 1–2)"],
)

public_router = APIRouter(
    prefix="/api/v1/public/websites",
    tags=["Public Booking Website (Stage 2)"],
)

UPLOAD_STREAM_CHUNK_SIZE = 64 * 1024  # 64 KiB


async def read_bounded_body(
    request: Request,
    max_bytes: int = MAX_BRAND_ASSET_BYTES,
    chunk_size: int = UPLOAD_STREAM_CHUNK_SIZE,
) -> bytes:
    """Read request body incrementally up to `max_bytes`, failing fast with HTTP 413."""
    raw_content_length = request.headers.get("content-length")
    if raw_content_length is not None:
        try:
            advertised_length = int(raw_content_length.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            ) from exc
        if advertised_length < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            )
        if advertised_length > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image file must be at most 2 MB.",
            )

    buffer = bytearray()
    async for raw_chunk in request.stream():
        if not raw_chunk:
            continue
        offset = 0
        chunk_len = len(raw_chunk)
        while offset < chunk_len:
            piece = raw_chunk[offset : offset + chunk_size]
            offset += chunk_size
            remaining = max_bytes - len(buffer)
            if len(piece) > remaining:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Image file must be at most 2 MB.",
                )
            buffer.extend(piece)
    return bytes(buffer)


@router.get(
    "",
    response_model=BookingWebsiteConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get or initialize salon booking website configuration",
)
async def get_booking_website_config(
    organization_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> BookingWebsiteConfigResponse:
    return await service.get_or_init_website_config(
        actor=actor, organization_id=organization_id
    )


@router.put(
    "",
    response_model=BookingWebsiteConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Save booking website draft configuration (Owner/Admin only)",
)
async def save_booking_website_draft(
    organization_id: UUID,
    payload: BookingWebsiteDraftUpdateRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> BookingWebsiteConfigResponse:
    return await service.save_draft(
        actor=actor, organization_id=organization_id, payload=payload
    )


@router.get(
    "/slug-availability",
    response_model=SlugAvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and check availability of a booking website slug",
)
async def check_booking_website_slug(
    organization_id: UUID,
    slug: str = Query(..., min_length=1, max_length=100),
    actor: AuthenticatedUser = Depends(get_current_user),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> SlugAvailabilityResponse:
    return await service.check_slug_availability(
        actor=actor, organization_id=organization_id, raw_slug=slug
    )


@router.post(
    "/assets/{asset_type}",
    response_model=BrandAssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload validated brand logo or cover image (Owner/Admin only)",
)
async def upload_booking_website_asset(
    organization_id: UUID,
    asset_type: str,
    request: Request,
    actor: AuthenticatedUser = Depends(get_current_user),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> BrandAssetUploadResponse:
    data = await read_bounded_body(request, max_bytes=MAX_BRAND_ASSET_BYTES)
    content_type = request.headers.get("content-type", "")
    return await service.upload_brand_asset(
        actor=actor,
        organization_id=organization_id,
        asset_type=asset_type,
        content_type=content_type,
        data=data,
    )


@router.post(
    "/publish",
    response_model=BookingWebsiteConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish salon booking website (guarded until Stage 2 public engine)",
)
async def publish_booking_website(
    organization_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> BookingWebsiteConfigResponse:
    return await service.publish_website(
        actor=actor, organization_id=organization_id
    )


@router.post(
    "/unpublish",
    response_model=BookingWebsiteConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Unpublish salon booking website back to draft (Owner/Admin only)",
)
async def unpublish_booking_website(
    organization_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> BookingWebsiteConfigResponse:
    return await service.unpublish_website(
        actor=actor, organization_id=organization_id
    )


@public_router.get(
    "/{slug}",
    response_model=PublicBookingWebsiteResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a published salon booking website by slug (allowlisted public fields only)",
)
async def get_public_booking_website(
    slug: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> PublicBookingWebsiteResponse:
    return await service.get_public_website_by_slug(
        slug=slug, client_ip=resolve_client_ip(request, settings)
    )


@public_router.get(
    "/{slug}/assets/{asset_type}",
    status_code=status.HTTP_200_OK,
    summary="Stream a published salon website's logo or cover image from private Storage",
)
async def get_public_booking_website_asset(
    slug: str,
    asset_type: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> Response:
    data, content_type = await service.get_public_website_asset(
        slug=slug,
        asset_type=asset_type,
        client_ip=resolve_client_ip(request, settings),
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@public_router.post(
    "/{slug}/voice/sessions",
    response_model=PublicWebsiteVoiceSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tenant-scoped public AI Receptionist voice session for a published salon website",
)
async def create_public_website_voice_session(
    slug: str,
    payload: PublicWebsiteVoiceSessionRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    bridge: PublicWebsiteVoiceBridgeService = Depends(get_public_website_voice_bridge_service),
) -> PublicWebsiteVoiceSessionResponse:
    return await bridge.create_public_voice_session(
        slug=slug,
        client_ip=resolve_client_ip(request, settings),
        payload=payload,
    )


@public_router.post(
    "/{slug}/voice/tools/execute",
    response_model=VoiceToolExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a salon AI Receptionist tool call for an active public website voice session",
)
async def execute_public_website_voice_tool(
    slug: str,
    payload: PublicWebsiteVoiceToolRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    bridge: PublicWebsiteVoiceBridgeService = Depends(get_public_website_voice_bridge_service),
) -> VoiceToolExecutionResponse:
    return await bridge.execute_public_voice_tool(
        slug=slug,
        client_ip=resolve_client_ip(request, settings),
        payload=payload,
    )
