"""Base industry agent contract for Stage 4 Conversational Intelligence."""

from abc import ABC, abstractmethod
from typing import List
from app.agents.schemas import AgentToolName
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry


class BaseIndustryAgent(ABC):
    """Abstract base class defining shared conversational & safety rules per industry."""

    @property
    @abstractmethod
    def industry(self) -> OrganizationIndustry:
        """Target industry vertical (`salon`, `clinic`, or `hospital`)."""

    @property
    def allowed_tools(self) -> List[AgentToolName]:
        """Approved backend tools available to the agent in Stage 4."""
        return [
            AgentToolName.GET_BUSINESS_PROFILE,
            AgentToolName.GET_BUSINESS_HOURS,
            AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
            AgentToolName.SAVE_CONVERSATION_SUMMARY,
            AgentToolName.REQUEST_HUMAN_ESCALATION,
        ]

    @property
    @abstractmethod
    def is_healthcare_vertical(self) -> bool:
        """Whether mandatory clinical & emergency healthcare safeguards apply."""

    @abstractmethod
    def build_industry_directives(self, bundle: OnboardingBundleResponse) -> str:
        """Return industry-specific system instructions for the given business bundle."""

    @abstractmethod
    def build_emergency_response(
        self, bundle: OnboardingBundleResponse, language_code: str = "en"
    ) -> str:
        """Return immediate emergency directive without asking delaying questions."""
