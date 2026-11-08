"""Shared platform infrastructure boundaries (Voice, AI, Scheduling, Notifications)."""

from app.modules.shared.contracts import (
    IndustryDomain,
    IndustryModuleDescriptor,
    SharedSubsystemBoundary,
)

__all__ = [
    "IndustryDomain",
    "IndustryModuleDescriptor",
    "SharedSubsystemBoundary",
]
