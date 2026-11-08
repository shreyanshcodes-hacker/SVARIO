"""Domain service enforcing explicit multi-tenant RBAC and membership checks."""

from typing import List
from uuid import UUID
from fastapi import Depends, HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.modules.organizations.repository import (
    InMemoryOrganizationRepository,
    OrganizationRepositoryProtocol,
    SupabaseRestOrganizationRepository,
)
from app.modules.organizations.schemas import (
    AddOrganizationMemberRequest,
    CreateOrganizationRequest,
    OrganizationDetailResponse,
    OrganizationMemberResponse,
    OrganizationRole,
    OrganizationSummaryResponse,
)

# Singleton ephemeral repository instance for local/test execution when live Supabase is not configured
_in_memory_repo = InMemoryOrganizationRepository()


def get_in_memory_organization_repository() -> InMemoryOrganizationRepository:
    """Return the shared in-memory organization repository (used in tests/dev)."""
    return _in_memory_repo


def get_organization_repository(
    settings: Settings = Depends(get_settings),
) -> OrganizationRepositoryProtocol:
    """Resolve the active organization repository based on environment configuration."""
    if settings.is_live_supabase_configured:
        return SupabaseRestOrganizationRepository(settings=settings)
    return _in_memory_repo


class OrganizationService:
    """Application service enforcing organization membership and role hierarchy."""

    def __init__(self, repository: OrganizationRepositoryProtocol) -> None:
        self._repo = repository

    async def create_organization(
        self, actor: AuthenticatedUser, payload: CreateOrganizationRequest
    ) -> OrganizationSummaryResponse:
        """Create an organization and assign the authenticated creator as owner."""
        return await self._repo.create_organization(actor=actor, payload=payload)

    async def list_organizations(
        self, actor: AuthenticatedUser
    ) -> List[OrganizationSummaryResponse]:
        """List only the organizations where `actor` is a verified member."""
        return await self._repo.list_user_organizations(actor=actor)

    async def get_organization(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        """Verify membership and return organization details."""
        actor_role = await self._repo.get_member_role(
            actor=actor, organization_id=organization_id, user_id=actor.id
        )
        if actor_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )
        return await self._repo.get_organization_for_member(
            actor=actor, organization_id=organization_id
        )

    async def list_members(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> List[OrganizationMemberResponse]:
        """Verify membership and list all members of `organization_id`."""
        actor_role = await self._repo.get_member_role(
            actor=actor, organization_id=organization_id, user_id=actor.id
        )
        if actor_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )
        return await self._repo.list_organization_members(
            actor=actor, organization_id=organization_id
        )

    async def add_member(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: AddOrganizationMemberRequest,
    ) -> OrganizationMemberResponse:
        """Verify caller's role in `organization_id` and prevent unauthorized escalation.

        Permission Model:
        - Non-members: 403 Forbidden.
        - `staff`: 403 Forbidden (cannot add members or promote anyone).
        - `admin`: Can ONLY add `staff` members; attempting to assign `owner` or `admin` -> 403 Forbidden.
        - `owner`: Can add `owner`, `admin`, or `staff` members.
        """
        actor_role = await self._repo.get_member_role(
            actor=actor, organization_id=organization_id, user_id=actor.id
        )
        if actor_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )

        if actor_role == OrganizationRole.STAFF:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions: staff members cannot add or manage organization members.",
            )

        if actor_role == OrganizationRole.ADMIN and payload.role in {
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions: admins may only add staff members; owner role is required to grant admin or owner privileges.",
            )

        return await self._repo.add_organization_member(
            actor=actor,
            organization_id=organization_id,
            payload=payload,
        )


def get_organization_service(
    repository: OrganizationRepositoryProtocol = Depends(get_organization_repository),
) -> OrganizationService:
    """FastAPI dependency returning an OrganizationService instance."""
    return OrganizationService(repository=repository)
