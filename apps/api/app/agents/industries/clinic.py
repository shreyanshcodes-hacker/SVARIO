"""Stage 4 Clinic Industry Agent (`OrganizationIndustry.CLINIC`)."""

from app.agents.base import BaseIndustryAgent
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry


class ClinicAgent(BaseIndustryAgent):
    """Administrative-only conversational policy and safeguards for Clinics."""

    @property
    def industry(self) -> OrganizationIndustry:
        return OrganizationIndustry.CLINIC

    @property
    def is_healthcare_vertical(self) -> bool:
        return True

    def build_industry_directives(self, bundle: OnboardingBundleResponse) -> str:
        business_name = bundle.profile.display_name
        return (
            f"CLINIC INDUSTRY INSTRUCTIONS ({business_name} — ADMINISTRATIVE-ONLY RECEPTIONIST):\n"
            "- You act strictly as an ADMINISTRATIVE-ONLY receptionist for the clinic.\n"
            "- Provide configured clinic consultation hours, location, and verified specialities using `get_business_hours`, `get_business_profile`, and `search_business_knowledge`.\n"
            "- Explain verified administrative consultation procedures and general clinic enquiries.\n"
            "- If a caller asks to book, reschedule, or cancel a doctor consultation, clarify that automated appointment booking is not executed in this stage; capture their preferred speciality/day/time without claiming an appointment is booked.\n"
            "- STRICT HEALTHCARE SAFEGUARDS:\n"
            "  1. NEVER provide medical diagnosis, diagnose any medical condition, or interpret symptoms.\n"
            "  2. NEVER prescribe medications, suggest dosages, or advise stopping medication.\n"
            "  3. NEVER recommend medical treatments or clinical procedures.\n"
            "  4. NEVER make clinical decisions or perform medical triage.\n"
            "  5. Escalate all clinical, symptom, or medication questions to qualified clinic staff via `request_human_escalation` (`urgency='clinical_staff'`).\n"
            "  6. If a caller describes a medical emergency, immediately direct them to local emergency services or the nearest hospital emergency department without asking delaying questions."
        )

    def build_emergency_response(
        self, bundle: OnboardingBundleResponse, language_code: str = "en"
    ) -> str:
        emergency_contact = (
            bundle.escalation.contact_phone
            or bundle.profile.phone
            or "local emergency services (112 / 108 / 911)"
        )
        if language_code == "hi":
            return (
                "यह एक संभावित चिकित्सा आपातकाल प्रतीत होता है। कृपया तुरंत स्थानीय आपातकालीन सेवाओं "
                f"(112 / 108) पर कॉल करें या नजदीकी अस्पताल के आपातकालीन विभाग में जाएं। क्लिनिक संपर्क: {emergency_contact}।"
            )
        if language_code == "hinglish":
            return (
                "Yeh ek medical emergency lag rahi hai. Please bina deri kiye turant local emergency services "
                f"(112 / 108) par call karein ya nearest hospital emergency department jaayein. Clinic contact: {emergency_contact}."
            )
        return (
            "This sounds like a potential medical emergency. Please hang up and call local emergency services "
            f"(112 / 108 / 911) immediately or proceed to the nearest hospital emergency department. "
            f"Direct clinic emergency contact: {emergency_contact}."
        )
