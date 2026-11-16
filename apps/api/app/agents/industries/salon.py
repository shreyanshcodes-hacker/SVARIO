"""Stage 5 Salon Industry Agent (`OrganizationIndustry.SALON`)."""

from typing import List
from app.agents.base import BaseIndustryAgent
from app.agents.schemas import AgentToolName
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry


class SalonAgent(BaseIndustryAgent):
    """Conversational policy and instructions for Salon reception desks."""

    @property
    def industry(self) -> OrganizationIndustry:
        return OrganizationIndustry.SALON

    @property
    def is_healthcare_vertical(self) -> bool:
        return False

    @property
    def allowed_tools(self) -> List[AgentToolName]:
        """Approved backend tools available to the salon agent in Stage 5."""
        return [
            AgentToolName.GET_BUSINESS_PROFILE,
            AgentToolName.GET_BUSINESS_HOURS,
            AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
            AgentToolName.SAVE_CONVERSATION_SUMMARY,
            AgentToolName.REQUEST_HUMAN_ESCALATION,
            AgentToolName.GET_SALON_SERVICES,
            AgentToolName.GET_SALON_STAFF,
            AgentToolName.CHECK_SALON_AVAILABILITY,
            AgentToolName.CREATE_SALON_APPOINTMENT,
            AgentToolName.RESCHEDULE_SALON_APPOINTMENT,
            AgentToolName.CANCEL_SALON_APPOINTMENT,
        ]

    def build_industry_directives(self, bundle: OnboardingBundleResponse) -> str:
        business_name = bundle.profile.display_name
        return (
            f"SALON INDUSTRY INSTRUCTIONS ({business_name}):\n"
            "- Help callers with general salon information, location, operating hours, and active services.\n"
            "- To inspect treatments, pricing, and durations, call `get_salon_services`.\n"
            "- To view qualified stylists or specialists, call `get_salon_staff`.\n"
            "- When a customer wants to book an appointment (e.g. 'I want a haircut tomorrow around 4 PM'):\n"
            "  1. Identify the requested service (or ask clarifying question if missing).\n"
            "  2. Check actual real-time availability via `check_salon_availability`.\n"
            "  3. Quote the available slot(s) and ask the customer for confirmation.\n"
            "  4. When the customer confirms, call `create_salon_appointment` with customer name and phone.\n"
            "  5. Confirm the booking ONLY after receiving a successful backend response with the booking reference.\n"
            "- When a customer wants to reschedule, verify availability and call `reschedule_salon_appointment`.\n"
            "- When a customer wants to cancel, call `cancel_salon_appointment`.\n"
            "- Never invent prices, durations, or booking confirmations without backend confirmation."
        )

    def build_emergency_response(
        self, bundle: OnboardingBundleResponse, language_code: str = "en"
    ) -> str:
        phone = bundle.profile.phone or bundle.escalation.contact_phone or "local emergency services (112 / 911)"
        if language_code == "hi":
            return (
                "यदि यह कोई आपातकालीन स्थिति है, तो कृपया तुरंत स्थानीय आपातकालीन सेवाओं (112) "
                f"या हमारे रिसेप्शन ({phone}) से संपर्क करें।"
            )
        if language_code == "hinglish":
            return (
                "Agar yeh emergency situation hai, toh please turant local emergency services (112) "
                f"ya salon front desk ({phone}) par call karein."
            )
        return (
            "If this is an emergency, please contact local emergency services immediately "
            f"or reach our reception desk directly at {phone}."
        )
