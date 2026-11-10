"""Stage 4 Hospital Industry Agent (`OrganizationIndustry.HOSPITAL`)."""

from app.agents.base import BaseIndustryAgent
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry


class HospitalAgent(BaseIndustryAgent):
    """Administrative switchboard policy & emergency-first safeguards for Hospitals."""

    @property
    def industry(self) -> OrganizationIndustry:
        return OrganizationIndustry.HOSPITAL

    @property
    def is_healthcare_vertical(self) -> bool:
        return True

    def build_industry_directives(self, bundle: OnboardingBundleResponse) -> str:
        business_name = bundle.profile.display_name
        return (
            f"HOSPITAL INDUSTRY INSTRUCTIONS ({business_name} — ADMINISTRATIVE-ONLY SWITCHBOARD):\n"
            "- Provide verified hospital department information, OPD timings, and visiting hours using `get_business_hours` and `search_business_knowledge`.\n"
            "- Help route administrative enquiries and explain verified hospital contact, address, and navigation details via `get_business_profile`.\n"
            "- If a caller asks to book, reschedule, or cancel an OPD appointment, clarify that automated appointment booking is not active in this stage; capture their department/timing preference or escalate to the OPD desk.\n"
            "- STRICT HOSPITAL & CLINICAL SAFEGUARDS:\n"
            "  1. NEVER provide medical diagnosis, diagnose conditions, interpret test results, or recommend treatments.\n"
            "  2. NEVER make clinical decisions or provide medication advice.\n"
            "  3. Route clinical questions to qualified hospital staff via `request_human_escalation` (`urgency='clinical_staff'`).\n"
            "  4. EMERGENCY-INTENT PROTOCOL: Any emergency-intent request (chest pain, stroke signs, severe bleeding, breathing distress, trauma, unconsciousness) MUST immediately receive clear direction to local emergency services or the hospital emergency channel.\n"
            "  5. Do NOT delay emergency guidance by asking unnecessary clarification questions."
        )

    def build_emergency_response(
        self, bundle: OnboardingBundleResponse, language_code: str = "en"
    ) -> str:
        hospital_name = bundle.profile.display_name
        emergency_phone = (
            bundle.escalation.contact_phone
            or bundle.profile.phone
            or "local emergency services (112 / 108 / 911)"
        )
        if language_code == "hi":
            return (
                f"आपातकालीन सूचना: कृपया तुरंत स्थानीय आपातकालीन सेवाओं (112 / 108) से संपर्क करें या सीधे "
                f"{hospital_name} के इमरजेंसी / कैजुअल्टी विभाग में पहुंचें। आपातकालीन हेल्पलाइन: {emergency_phone}।"
            )
        if language_code == "hinglish":
            return (
                f"Emergency Alert: Please bina kisi सवाल-जवाब ke turant local emergency services (112 / 108) "
                f"par call karein ya seedhe {hospital_name} ke Emergency / Casualty department mein pahunchein. "
                f"Emergency helpline: {emergency_phone}."
            )
        return (
            f"EMERGENCY DIRECTIVE: Please contact local emergency services (112 / 108 / 911) immediately "
            f"or proceed directly to the {hospital_name} Emergency / Casualty Department. "
            f"Hospital emergency line: {emergency_phone}. Do not wait on this line."
        )
