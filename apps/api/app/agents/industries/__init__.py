"""Industry-specific agent implementations for Salons, Clinics, and Hospitals."""

from typing import Dict
from app.agents.base import BaseIndustryAgent
from app.agents.industries.clinic import ClinicAgent
from app.agents.industries.hospital import HospitalAgent
from app.agents.industries.salon import SalonAgent
from app.modules.organizations.schemas import OrganizationIndustry

_INDUSTRY_AGENTS: Dict[OrganizationIndustry, BaseIndustryAgent] = {
    OrganizationIndustry.SALON: SalonAgent(),
    OrganizationIndustry.CLINIC: ClinicAgent(),
    OrganizationIndustry.HOSPITAL: HospitalAgent(),
}


def get_industry_agent(industry: OrganizationIndustry) -> BaseIndustryAgent:
    """Resolve the Stage 4 industry agent for `salon`, `clinic`, or `hospital`."""
    return _INDUSTRY_AGENTS[industry]


__all__ = [
    "ClinicAgent",
    "HospitalAgent",
    "SalonAgent",
    "get_industry_agent",
]
