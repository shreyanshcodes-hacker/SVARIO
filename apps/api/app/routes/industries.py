"""Read-only architectural boundary inspection endpoint for Stage 0."""

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from app.modules.registry import (
    get_industry_descriptors,
    get_shared_subsystem_boundaries,
)
from app.modules.shared.contracts import (
    IndustryModuleDescriptor,
    SharedSubsystemBoundary,
)

router = APIRouter()


class ArchitectureOverviewResponse(BaseModel):
    """Read-only summary of multi-industry and shared platform boundaries."""

    stage: int
    shared_subsystems: List[SharedSubsystemBoundary]
    industry_modules: List[IndustryModuleDescriptor]


@router.get(
    "/architecture",
    response_model=ArchitectureOverviewResponse,
    summary="Multi-Industry Architectural Boundaries (Stage 0)",
)
async def get_architecture_overview() -> ArchitectureOverviewResponse:
    """Expose static Stage 0 boundaries for shared subsystems and target industries."""
    return ArchitectureOverviewResponse(
        stage=0,
        shared_subsystems=get_shared_subsystem_boundaries(),
        industry_modules=get_industry_descriptors(),
    )
