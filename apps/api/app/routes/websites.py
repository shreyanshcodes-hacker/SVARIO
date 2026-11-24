"""API routes for White-Label Booking Website Engine (Stage 1 Dashboard + Stage 2 Public Engine)."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, Response, status
from app.core.auth import AuthenticatedUser, get_current_user
from app.modules.websites.schemas import (
    BookingWebsiteConfigResponse,
    BookingWebsiteDraftUpdateRequest,
    BrandAssetUploadResponse,
    PublicBookingWebsiteResponse,
    SlugAvailabilityResponse,
)
from app.modules.websites.service import (
    BookingWebsiteService,
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


def _extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


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
    data = await request.body()
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
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> PublicBookingWebsiteResponse:
    return await service.get_public_website_by_slug(
        slug=slug, client_ip=_extract_client_ip(request)
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
    service: BookingWebsiteService = Depends(get_booking_website_service),
) -> Response:
    data, content_type = await service.get_public_website_asset(
        slug=slug,
        asset_type=asset_type,
        client_ip=_extract_client_ip(request),
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=300",
        },
    )
