"""Authentication verification routes for Svario API (Stage 1)."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class AuthMeResponse(BaseModel):
    """Verified identity information returned by GET /api/v1/auth/me."""

    id: UUID = Field(..., description="Verified Supabase user UUID")
    email: Optional[str] = Field(default=None, description="Verified user email")
    role: str = Field(..., description="Verified token role claim")
    session_id: Optional[str] = Field(default=None, description="Verified session ID")
    full_name: Optional[str] = Field(default=None, description="User display name")
    email_verified: bool = Field(default=False, description="Email verification state")
    issuer: str = Field(..., description="Verified token issuer")
    audience: str = Field(..., description="Verified token audience")


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Return Verified Authenticated User Identity",
)
async def get_auth_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthMeResponse:
    """Return cryptographically verified identity claims for the current Bearer token."""
    return AuthMeResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        session_id=current_user.session_id,
        full_name=current_user.full_name,
        email_verified=current_user.email_verified,
        issuer=current_user.issuer,
        audience=current_user.audience,
    )
