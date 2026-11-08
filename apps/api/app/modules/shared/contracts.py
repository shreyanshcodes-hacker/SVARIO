"""Domain contracts defining how industry modules plug into shared platform services.

Stage 0 Note:
These Pydantic models and Protocols define strict architectural boundaries only.
Concrete business workflow implementations are intentionally deferred to later stages.
"""

from enum import Enum
from typing import List, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class IndustryDomain(str, Enum):
    """Supported Svario industry verticals."""

    SALONS = "salons"
    CLINICS = "clinics"
    HOSPITALS = "hospitals"


class SharedSubsystemBoundary(BaseModel):
    """Metadata describing a shared platform subsystem contract."""

    subsystem_id: str = Field(..., description="Unique identifier for the shared subsystem")
    name: str = Field(..., description="Human-readable subsystem name")
    purpose: str = Field(..., description="Architectural role in the Svario platform")
    planned_provider: str = Field(..., description="Target infrastructure provider for later stages")
    stage_status: str = Field(default="Stage 0 — Architectural Boundary Defined")


class IndustryModuleDescriptor(BaseModel):
    """Declarative specification of an industry vertical module in Svario."""

    domain: IndustryDomain
    title: str
    subtitle: str
    summary: str
    voice_persona_focus: str
    planned_capabilities: List[str]
    shared_dependencies: List[str] = Field(
        default_factory=lambda: ["voice", "ai", "scheduling", "notifications"]
    )
    stage_status: str = Field(default="Stage 0 — Boundary Only (Informational)")


@runtime_checkable
class IndustryModuleContract(Protocol):
    """Protocol that every industry module in `app.modules.<industry>` must satisfy."""

    def get_descriptor(self) -> IndustryModuleDescriptor:
        """Return static metadata and architectural boundaries for this industry."""
        ...
