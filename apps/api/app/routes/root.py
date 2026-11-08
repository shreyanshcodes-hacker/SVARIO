"""Root metadata endpoint for Svario API."""

from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.config import Settings, get_settings
from app.modules.shared.contracts import IndustryDomain

router = APIRouter()


class RootResponse(BaseModel):
    """Root informational payload returned by GET /."""

    platform: str
    tagline: str
    service: str
    version: str
    stage: int
    environment: str
    industries: List[IndustryDomain]
    health_endpoint: str
    architecture_endpoint: str


@router.get("/", response_model=RootResponse, summary="Platform Foundation Overview")
async def get_root(settings: Settings = Depends(get_settings)) -> RootResponse:
    """Return Svario platform identity and Stage 0 foundation metadata."""
    return RootResponse(
        platform="SVARIO",
        tagline="AI that speaks for your business.",
        service=settings.api_service_name,
        version=settings.api_version,
        stage=settings.svario_stage,
        environment=settings.svario_env,
        industries=[
            IndustryDomain.SALONS,
            IndustryDomain.CLINICS,
            IndustryDomain.HOSPITALS,
        ],
        health_endpoint="/health",
        architecture_endpoint="/architecture",
    )
