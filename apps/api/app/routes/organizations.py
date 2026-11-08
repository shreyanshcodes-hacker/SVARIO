"""Multi-tenant organization management routes for Svario API (Stage 1)."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from app.core.auth import AuthenticatedUser, get_current_user
from app.modules.organizations.schemas import (
    AddOrganizationMemberRequest,
    CreateOrganizationRequest,
    OrganizationDetailResponse,
    OrganizationMemberResponse,
    OrganizationSummaryResponse,
)
from app.modules.organizations.service import (
    OrganizationService,
    get_organization_service,
)

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


@router.post(
    "",
    response_model=OrganizationSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization (Creator Becomes Owner)",
)
async def create_organization(
    payload: CreateOrganizationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationSummaryResponse:
    """Create a new organization for Salon, Clinic, or Hospital and assign creator as owner."""
    return await service.create_organization(actor=current_user, payload=payload)


@router.get(
    "",
    response_model=List[OrganizationSummaryResponse],
    summary="List Current User's Organizations",
)
async def list_organizations(
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> List[OrganizationSummaryResponse]:
    """Return only organizations where the authenticated user is a verified member."""
    return await service.list_organizations(actor=current_user)


@router.get(
    "/{organization_id}",
    response_model=OrganizationDetailResponse,
    summary="Get Organization Details (Members Only)",
)
async def get_organization(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationDetailResponse:
    """Verify membership and return organization details."""
    return await service.get_organization(
        actor=current_user, organization_id=organization_id
    )


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Organization Member (Owner/Admin RBAC Enforced)",
)
async def add_organization_member(
    organization_id: UUID,
    payload: AddOrganizationMemberRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationMemberResponse:
    """Add a member to an organization after verifying caller's membership and role."""
    return await service.add_member(
        actor=current_user,
        organization_id=organization_id,
        payload=payload,
    )


@router.get(
    "/{organization_id}/members",
    response_model=List[OrganizationMemberResponse],
    summary="List Organization Members (Members Only)",
)
async def list_organization_members(
    organization_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> List[OrganizationMemberResponse]:
    """Verify membership and return all members of the organization."""
    return await service.list_members(
        actor=current_user, organization_id=organization_id
    )
