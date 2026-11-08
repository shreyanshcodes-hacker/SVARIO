"""API route definitions for Svario API (Stage 0, Stage 1 & Stage 2)."""

from fastapi import APIRouter
from app.routes.auth import router as auth_router
from app.routes.health import router as health_router
from app.routes.industries import router as industries_router
from app.routes.onboarding import router as onboarding_router
from app.routes.organizations import router as organizations_router
from app.routes.root import router as root_router

api_router = APIRouter()
api_router.include_router(root_router, tags=["Platform"])
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(industries_router, tags=["Architecture"])
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(onboarding_router)

__all__ = ["api_router"]
