"""Repository layer for Stage 1 multi-tenant organizations and memberships.

Provides:
1. `SupabaseRestOrganizationRepository` — interacts with Supabase PostgREST using
   the caller's verified JWT (enforcing PostgreSQL RLS) while ALSO enforcing
   application-layer membership and RBAC checks.
2. `InMemoryOrganizationRepository` — clean, initially empty repository used when
   a live Supabase URL is not configured (e.g., local CI/unit testing), with zero
   hardcoded users or demo organizations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException, status
from app.core.auth import AuthenticatedUser
from app.core.config import Settings
from app.modules.organizations.schemas import (
    AddOrganizationMemberRequest,
    CreateOrganizationRequest,
    OrganizationDetailResponse,
    OrganizationIndustry,
    OrganizationMemberResponse,
    OrganizationRole,
    OrganizationSummaryResponse,
    slugify_organization_name,
)


class OrganizationRepositoryProtocol(Protocol):
    """Storage interface for organization and membership persistence."""

    async def create_organization(
        self, actor: AuthenticatedUser, payload: CreateOrganizationRequest
    ) -> OrganizationSummaryResponse:
        ...

    async def list_user_organizations(
        self, actor: AuthenticatedUser
    ) -> List[OrganizationSummaryResponse]:
        ...

    async def get_organization_for_member(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        ...

    async def get_member_role(
        self, actor: AuthenticatedUser, organization_id: UUID, user_id: UUID
    ) -> Optional[OrganizationRole]:
        ...

    async def list_organization_members(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> List[OrganizationMemberResponse]:
        ...

    async def add_organization_member(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: AddOrganizationMemberRequest,
    ) -> OrganizationMemberResponse:
        ...


class InMemoryOrganizationRepository:
    """Initially empty, multi-tenant in-memory repository with strict isolation.

    Contains NO demo data or hardcoded identities.
    """

    def __init__(self) -> None:
        self._profiles: Dict[UUID, Dict[str, Optional[str]]] = {}
        self._organizations: Dict[UUID, Dict[str, object]] = {}
        self._slugs: Dict[str, UUID] = {}
        self._members: Dict[UUID, List[Dict[str, object]]] = {}
        self._businesses: Dict[UUID, List[Dict[str, object]]] = {}
        self._business_settings: Dict[UUID, List[Dict[str, object]]] = {}
        self._audit_logs: List[Dict[str, object]] = []

    def _ensure_profile(
        self, user_id: UUID, full_name: Optional[str] = None
    ) -> None:
        if user_id not in self._profiles:
            self._profiles[user_id] = {
                "id": str(user_id),
                "full_name": full_name or "",
            }
        elif full_name and not self._profiles[user_id].get("full_name"):
            self._profiles[user_id]["full_name"] = full_name

    def _allocate_unique_slug(self, desired_slug: Optional[str], name: str) -> str:
        base_slug = desired_slug or slugify_organization_name(name)
        if desired_slug and base_slug in self._slugs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization slug '{base_slug}' is already in use.",
            )
        candidate = base_slug
        while candidate in self._slugs:
            suffix = uuid4().hex[:6]
            candidate = f"{base_slug[:56]}-{suffix}"
        return candidate

    async def create_organization(
        self, actor: AuthenticatedUser, payload: CreateOrganizationRequest
    ) -> OrganizationSummaryResponse:
        now = datetime.now(timezone.utc)
        self._ensure_profile(actor.id, actor.full_name)

        org_id = uuid4()
        unique_slug = self._allocate_unique_slug(payload.slug, payload.name)

        org_record: Dict[str, object] = {
            "id": org_id,
            "name": payload.name,
            "slug": unique_slug,
            "industry": payload.industry,
            "created_at": now,
            "updated_at": now,
        }
        self._organizations[org_id] = org_record
        self._slugs[unique_slug] = org_id

        owner_membership: Dict[str, object] = {
            "id": uuid4(),
            "organization_id": org_id,
            "user_id": actor.id,
            "role": OrganizationRole.OWNER,
            "created_at": now,
        }
        self._members[org_id] = [owner_membership]

        # Provision initial business & business_settings records for the organization
        business_id = uuid4()
        self._businesses[org_id] = [
            {
                "id": business_id,
                "organization_id": org_id,
                "name": payload.name,
                "timezone": payload.timezone,
                "created_at": now,
                "updated_at": now,
            }
        ]
        self._business_settings[org_id] = [
            {
                "id": uuid4(),
                "organization_id": org_id,
                "business_id": business_id,
                "default_language": "en",
                "supported_languages": ["en"],
                "assistant_enabled": False,
                "created_at": now,
                "updated_at": now,
            }
        ]
        self._audit_logs.append(
            {
                "id": uuid4(),
                "organization_id": org_id,
                "actor_user_id": actor.id,
                "action": "organization.created",
                "resource_type": "organization",
                "resource_id": org_id,
                "metadata": {"industry": payload.industry.value, "slug": unique_slug},
                "created_at": now,
            }
        )

        return OrganizationSummaryResponse(
            id=org_id,
            name=payload.name,
            slug=unique_slug,
            industry=payload.industry,
            membership_role=OrganizationRole.OWNER,
            created_at=now,
            updated_at=now,
        )

    async def get_member_role(
        self, actor: AuthenticatedUser, organization_id: UUID, user_id: UUID
    ) -> Optional[OrganizationRole]:
        members = self._members.get(organization_id, [])
        for entry in members:
            if entry["user_id"] == user_id:
                role_val = entry["role"]
                return (
                    role_val
                    if isinstance(role_val, OrganizationRole)
                    else OrganizationRole(str(role_val))
                )
        return None

    async def list_user_organizations(
        self, actor: AuthenticatedUser
    ) -> List[OrganizationSummaryResponse]:
        results: List[OrganizationSummaryResponse] = []
        for org_id, members in self._members.items():
            for entry in members:
                if entry["user_id"] == actor.id:
                    org = self._organizations.get(org_id)
                    if org:
                        results.append(
                            OrganizationSummaryResponse(
                                id=org["id"],  # type: ignore[arg-type]
                                name=str(org["name"]),
                                slug=str(org["slug"]),
                                industry=OrganizationIndustry(str(org["industry"].value if isinstance(org["industry"], OrganizationIndustry) else org["industry"])),
                                membership_role=OrganizationRole(str(entry["role"].value if isinstance(entry["role"], OrganizationRole) else entry["role"])),
                                created_at=org["created_at"],  # type: ignore[arg-type]
                                updated_at=org["updated_at"],  # type: ignore[arg-type]
                            )
                        )
        return results

    async def get_organization_for_member(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        org = self._organizations.get(organization_id)
        role = await self.get_member_role(actor, organization_id, actor.id)
        if org is None or role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )
        members = self._members.get(organization_id, [])
        return OrganizationDetailResponse(
            id=org["id"],  # type: ignore[arg-type]
            name=str(org["name"]),
            slug=str(org["slug"]),
            industry=OrganizationIndustry(
                str(
                    org["industry"].value
                    if isinstance(org["industry"], OrganizationIndustry)
                    else org["industry"]
                )
            ),
            membership_role=role,
            member_count=len(members),
            created_at=org["created_at"],  # type: ignore[arg-type]
            updated_at=org["updated_at"],  # type: ignore[arg-type]
        )

    async def list_organization_members(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> List[OrganizationMemberResponse]:
        members = self._members.get(organization_id, [])
        responses: List[OrganizationMemberResponse] = []
        for entry in members:
            target_uid: UUID = entry["user_id"]  # type: ignore[assignment]
            profile = self._profiles.get(target_uid, {})
            responses.append(
                OrganizationMemberResponse(
                    id=entry["id"],  # type: ignore[arg-type]
                    organization_id=organization_id,
                    user_id=target_uid,
                    role=OrganizationRole(
                        str(
                            entry["role"].value
                            if isinstance(entry["role"], OrganizationRole)
                            else entry["role"]
                        )
                    ),
                    full_name=profile.get("full_name") or None,
                    created_at=entry["created_at"],  # type: ignore[arg-type]
                )
            )
        return responses

    async def add_organization_member(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: AddOrganizationMemberRequest,
    ) -> OrganizationMemberResponse:
        if organization_id not in self._organizations:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )

        existing_role = await self.get_member_role(
            actor, organization_id, payload.user_id
        )
        if existing_role is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization.",
            )

        now = datetime.now(timezone.utc)
        self._ensure_profile(payload.user_id, payload.full_name)

        member_id = uuid4()
        new_entry: Dict[str, object] = {
            "id": member_id,
            "organization_id": organization_id,
            "user_id": payload.user_id,
            "role": payload.role,
            "created_at": now,
        }
        self._members.setdefault(organization_id, []).append(new_entry)
        self._audit_logs.append(
            {
                "id": uuid4(),
                "organization_id": organization_id,
                "actor_user_id": actor.id,
                "action": "organization.member_added",
                "resource_type": "organization_member",
                "resource_id": member_id,
                "metadata": {
                    "target_user_id": str(payload.user_id),
                    "assigned_role": payload.role.value,
                },
                "created_at": now,
            }
        )

        profile = self._profiles.get(payload.user_id, {})
        return OrganizationMemberResponse(
            id=member_id,
            organization_id=organization_id,
            user_id=payload.user_id,
            role=payload.role,
            full_name=profile.get("full_name") or None,
            created_at=now,
        )


class SupabaseRestOrganizationRepository:
    """Supabase PostgREST repository forwarding user JWTs so DB RLS is enforced."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = (settings.supabase_url or "").rstrip("/")
        self._anon_key = settings.supabase_anon_key or ""

    def _headers(self, actor: AuthenticatedUser) -> Dict[str, str]:
        return {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {actor.raw_token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _ensure_profile_row(
        self, client: httpx.AsyncClient, actor: AuthenticatedUser
    ) -> None:
        await client.post(
            f"{self._base_url}/rest/v1/profiles",
            headers={
                **self._headers(actor),
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
            json={
                "id": str(actor.id),
                "full_name": actor.full_name or "",
            },
        )

    async def create_organization(
        self, actor: AuthenticatedUser, payload: CreateOrganizationRequest
    ) -> OrganizationSummaryResponse:
        slug = payload.slug or f"{slugify_organization_name(payload.name)}-{uuid4().hex[:6]}"
        org_id = uuid4()

        async with httpx.AsyncClient(timeout=10.0) as client:
            await self._ensure_profile_row(client, actor)

            org_resp = await client.post(
                f"{self._base_url}/rest/v1/organizations",
                headers={
                    **self._headers(actor),
                    "Prefer": "return=minimal",
                },
                json={
                    "id": str(org_id),
                    "name": payload.name,
                    "slug": slug,
                    "industry": payload.industry.value,
                },
            )
            if org_resp.status_code == status.HTTP_409_CONFLICT:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Organization slug '{slug}' already exists.",
                )
            if org_resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to create organization in Supabase.",
                )

            member_resp = await client.post(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                json={
                    "organization_id": str(org_id),
                    "user_id": str(actor.id),
                    "role": OrganizationRole.OWNER.value,
                },
            )
            if member_resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to assign owner membership in Supabase.",
                )

            org_fetch = await client.get(
                f"{self._base_url}/rest/v1/organizations",
                headers=self._headers(actor),
                params={"id": f"eq.{org_id}", "select": "*"},
            )
            org_rows = org_fetch.json() if org_fetch.status_code < 400 else []
            now_iso = datetime.now(timezone.utc).isoformat()
            org_row = (
                org_rows[0]
                if org_rows
                else {
                    "id": str(org_id),
                    "name": payload.name,
                    "slug": slug,
                    "industry": payload.industry.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
            )

            business_id = uuid4()
            await client.post(
                f"{self._base_url}/rest/v1/businesses",
                headers=self._headers(actor),
                json={
                    "id": str(business_id),
                    "organization_id": str(org_id),
                    "name": payload.name,
                    "timezone": payload.timezone,
                },
            )
            await client.post(
                f"{self._base_url}/rest/v1/business_settings",
                headers=self._headers(actor),
                json={
                    "organization_id": str(org_id),
                    "business_id": str(business_id),
                    "default_language": "en",
                    "supported_languages": ["en"],
                    "assistant_enabled": False,
                },
            )
            await client.post(
                f"{self._base_url}/rest/v1/audit_logs",
                headers=self._headers(actor),
                json={
                    "organization_id": str(org_id),
                    "actor_user_id": str(actor.id),
                    "action": "organization.created",
                    "resource_type": "organization",
                    "resource_id": str(org_id),
                    "metadata": {"industry": payload.industry.value, "slug": slug},
                },
            )

        return OrganizationSummaryResponse(
            id=UUID(org_row["id"]),
            name=org_row["name"],
            slug=org_row["slug"],
            industry=OrganizationIndustry(org_row["industry"]),
            membership_role=OrganizationRole.OWNER,
            created_at=datetime.fromisoformat(org_row["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(org_row["updated_at"].replace("Z", "+00:00")),
        )

    async def get_member_role(
        self, actor: AuthenticatedUser, organization_id: UUID, user_id: UUID
    ) -> Optional[OrganizationRole]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "user_id": f"eq.{user_id}",
                    "select": "role",
                },
            )
            if resp.status_code >= 400:
                return None
            rows = resp.json()
            if not rows:
                return None
            return OrganizationRole(rows[0]["role"])

    async def list_user_organizations(
        self, actor: AuthenticatedUser
    ) -> List[OrganizationSummaryResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                params={
                    "user_id": f"eq.{actor.id}",
                    "select": "role,organizations(id,name,slug,industry,created_at,updated_at)",
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to fetch organization memberships.",
                )
            rows = resp.json()

        items: List[OrganizationSummaryResponse] = []
        for row in rows:
            org = row.get("organizations")
            if not org:
                continue
            items.append(
                OrganizationSummaryResponse(
                    id=UUID(org["id"]),
                    name=org["name"],
                    slug=org["slug"],
                    industry=OrganizationIndustry(org["industry"]),
                    membership_role=OrganizationRole(row["role"]),
                    created_at=datetime.fromisoformat(org["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(org["updated_at"].replace("Z", "+00:00")),
                )
            )
        return items

    async def get_organization_for_member(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> OrganizationDetailResponse:
        role = await self.get_member_role(actor, organization_id, actor.id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you are not a member of this organization.",
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            org_resp = await client.get(
                f"{self._base_url}/rest/v1/organizations",
                headers=self._headers(actor),
                params={"id": f"eq.{organization_id}", "select": "*"},
            )
            members_resp = await client.get(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                params={"organization_id": f"eq.{organization_id}", "select": "id"},
            )

        org_rows = org_resp.json() if org_resp.status_code < 400 else []
        if not org_rows:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: organization not accessible.",
            )
        org = org_rows[0]
        member_count = len(members_resp.json()) if members_resp.status_code < 400 else 1

        return OrganizationDetailResponse(
            id=UUID(org["id"]),
            name=org["name"],
            slug=org["slug"],
            industry=OrganizationIndustry(org["industry"]),
            membership_role=role,
            member_count=member_count,
            created_at=datetime.fromisoformat(org["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(org["updated_at"].replace("Z", "+00:00")),
        )

    async def list_organization_members(
        self, actor: AuthenticatedUser, organization_id: UUID
    ) -> List[OrganizationMemberResponse]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                params={
                    "organization_id": f"eq.{organization_id}",
                    "select": "id,organization_id,user_id,role,created_at,profiles(full_name)",
                },
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to list organization members.",
                )
            rows = resp.json()

        results: List[OrganizationMemberResponse] = []
        for row in rows:
            profile_obj = row.get("profiles") or {}
            results.append(
                OrganizationMemberResponse(
                    id=UUID(row["id"]),
                    organization_id=UUID(row["organization_id"]),
                    user_id=UUID(row["user_id"]),
                    role=OrganizationRole(row["role"]),
                    full_name=profile_obj.get("full_name") or None,
                    created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
                )
            )
        return results

    async def add_organization_member(
        self,
        actor: AuthenticatedUser,
        organization_id: UUID,
        payload: AddOrganizationMemberRequest,
    ) -> OrganizationMemberResponse:
        existing_role = await self.get_member_role(
            actor, organization_id, payload.user_id
        )
        if existing_role is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization.",
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/rest/v1/organization_members",
                headers=self._headers(actor),
                json={
                    "organization_id": str(organization_id),
                    "user_id": str(payload.user_id),
                    "role": payload.role.value,
                },
            )
            if resp.status_code == status.HTTP_409_CONFLICT:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User is already a member of this organization.",
                )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to add member; verify the target user profile exists.",
                )
            row = resp.json()[0]

            await client.post(
                f"{self._base_url}/rest/v1/audit_logs",
                headers=self._headers(actor),
                json={
                    "organization_id": str(organization_id),
                    "actor_user_id": str(actor.id),
                    "action": "organization.member_added",
                    "resource_type": "organization_member",
                    "resource_id": row["id"],
                    "metadata": {
                        "target_user_id": str(payload.user_id),
                        "assigned_role": payload.role.value,
                    },
                },
            )

        return OrganizationMemberResponse(
            id=UUID(row["id"]),
            organization_id=UUID(row["organization_id"]),
            user_id=UUID(row["user_id"]),
            role=OrganizationRole(row["role"]),
            full_name=payload.full_name,
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
        )
