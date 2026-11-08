"""Central registry of Svario shared subsystems and industry module boundaries."""

from typing import List
from app.modules.clinics import ClinicsModule
from app.modules.hospitals import HospitalsModule
from app.modules.salons import SalonsModule
from app.modules.shared.ai import AI_SUBSYSTEM_BOUNDARY
from app.modules.shared.contracts import (
    IndustryModuleContract,
    IndustryModuleDescriptor,
    SharedSubsystemBoundary,
)
from app.modules.shared.notifications import NOTIFICATIONS_SUBSYSTEM_BOUNDARY
from app.modules.shared.scheduling import SCHEDULING_SUBSYSTEM_BOUNDARY
from app.modules.shared.voice import VOICE_SUBSYSTEM_BOUNDARY


def get_registered_industry_modules() -> List[IndustryModuleContract]:
    """Return ordered list of registered industry boundary modules."""
    return [
        SalonsModule(),
        ClinicsModule(),
        HospitalsModule(),
    ]


def get_industry_descriptors() -> List[IndustryModuleDescriptor]:
    """Return descriptors for all supported Svario target industries."""
    return [module.get_descriptor() for module in get_registered_industry_modules()]


def get_shared_subsystem_boundaries() -> List[SharedSubsystemBoundary]:
    """Return architectural boundaries for shared platform infrastructure."""
    return [
        VOICE_SUBSYSTEM_BOUNDARY,
        AI_SUBSYSTEM_BOUNDARY,
        SCHEDULING_SUBSYSTEM_BOUNDARY,
        NOTIFICATIONS_SUBSYSTEM_BOUNDARY,
    ]
