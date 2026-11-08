"""Pydantic schemas for Stage 1 organizations, memberships, and audit logs."""

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationIndustry(str, Enum):
    """Allowed industry types in Stage 1 database and API contracts."""

    SALON = "salon"
    CLINIC = "clinic"
    HOSPITAL = "hospital"


class OrganizationRole(str, Enum):
    """Allowed membership roles within an organization."""

    OWNER = "owner"
    ADMIN = "admin"
    STAFF = "staff"


SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify_organization_name(name: str) -> str:
    """Convert an organization name into a URL-safe lowercase slug."""
    lowered = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if len(cleaned) < 2:
        cleaned = "org-unit"
    return cleaned[:64].rstrip("-")


class CreateOrganizationRequest(BaseModel):
    """Payload to create a new organization. Rejects unknown/spoofed fields."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120, description="Organization display name")
    industry: OrganizationIndustry = Field(
        ..., description="Target industry vertical: salon, clinic, or hospital"
    )
    slug: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=80,
        description="Optional unique URL slug; generated automatically if omitted",
    )
    timezone: str = Field(
        default="UTC",
        min_length=2,
        max_length=64,
        description="Default timezone for the primary business record",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2:
            raise ValueError("Organization name must contain at least 2 non-whitespace characters.")
        return trimmed

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip().lower()
        if not SLUG_REGEX.match(trimmed):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and single hyphens."
            )
        return trimmed


class AddOrganizationMemberRequest(BaseModel):
    """Payload to add a member to an organization. Rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID = Field(..., description="Target profile/auth user UUID to add")
    role: OrganizationRole = Field(
        default=OrganizationRole.STAFF,
        description="Role to assign: owner, admin, or staff",
    )
    full_name: Optional[str] = Field(
        default=None, max_length=120, description="Optional profile full name if known"
    )


class OrganizationSummaryResponse(BaseModel):
    """Organization record enriched with the current user's membership role."""

    id: UUID
    name: str
    slug: str
    industry: OrganizationIndustry
    membership_role: OrganizationRole
    created_at: datetime
    updated_at: datetime


class OrganizationDetailResponse(BaseModel):
    """Detailed organization response for verified organization members."""

    id: UUID
    name: str
    slug: str
    industry: OrganizationIndustry
    membership_role: OrganizationRole
    member_count: int
    created_at: datetime
    updated_at: datetime


class OrganizationMemberResponse(BaseModel):
    """Single membership entry within an organization."""

    id: UUID
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    full_name: Optional[str] = None
    created_at: datetime


class OrganizationListResponse(BaseModel):
    """Envelope for GET /api/v1/organizations."""

    organizations: List[OrganizationSummaryResponse]


class OrganizationMemberListResponse(BaseModel):
    """Envelope for GET /api/v1/organizations/{organization_id}/members."""

    organization_id: UUID
    members: List[OrganizationMemberResponse]
