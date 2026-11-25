"""Health and readiness check endpoints for Svario API."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.core.config import Settings, get_settings
from app.core.redis_provider import get_redis_client

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response schema for Stage 0."""

    status: str = Field(default="ok", examples=["ok"])
    service: str = Field(default="Svario API", examples=["Svario API"])
    stage: int = Field(default=0, examples=[0])


class ReadinessResponse(BaseModel):
    """Readiness check response schema verifying distributed dependencies."""

    status: str = Field(default="ready")
    redis: str = Field(default="not_configured")


@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return operational status, service name, and current milestone stage."""
    return HealthResponse(
        status="ok",
        service=settings.api_service_name,
        stage=settings.svario_stage,
    )


@router.get("/health/ready", response_model=ReadinessResponse, summary="Service Readiness Check")
async def get_readiness(settings: Settings = Depends(get_settings)) -> ReadinessResponse:
    """Verify Redis connectivity without exposing credentials."""
    redis_client = get_redis_client(settings)
    if redis_client is None:
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Distributed state store is not configured.",
            )
        return ReadinessResponse(status="ready", redis="in_memory")

    if not redis_client.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Distributed state store is unavailable.",
        )

    return ReadinessResponse(status="ready", redis="ok")
