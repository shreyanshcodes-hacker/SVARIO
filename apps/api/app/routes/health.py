"""Health check endpoint for Svario API."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.config import Settings, get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response schema for Stage 0."""

    status: str = Field(default="ok", examples=["ok"])
    service: str = Field(default="Svario API", examples=["Svario API"])
    stage: int = Field(default=0, examples=[0])


@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return operational status, service name, and current milestone stage."""
    return HealthResponse(
        status="ok",
        service=settings.api_service_name,
        stage=settings.svario_stage,
    )
