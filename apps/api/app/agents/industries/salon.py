"""Stage 4 Salon Industry Agent (`OrganizationIndustry.SALON`)."""

from app.agents.base import BaseIndustryAgent
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

    def build_industry_directives(self, bundle: OnboardingBundleResponse) -> str:
        business_name = bundle.profile.display_name
        return (
            f"SALON INDUSTRY INSTRUCTIONS ({business_name}):\n"
            "- Help callers with general salon information, location, and operating hours.\n"
            "- Explain salon services, treatments, and pricing ONLY if verified in the business profile or active FAQs retrieved via `search_business_knowledge`.\n"
            "- Never invent hair/beauty service prices, package discounts, or stylist availability.\n"
            "- If a caller wants to book, reschedule, or cancel a salon appointment, politely clarify that live appointment booking is not executed automatically in this stage; collect their preferred service, preferred day/time, and save those preferences via `save_conversation_summary` or offer human front-desk assistance via `request_human_escalation`.\n"
            "- Escalate uncertain or custom bridal/chemical consultation requests to the salon front desk using `request_human_escalation`."
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
