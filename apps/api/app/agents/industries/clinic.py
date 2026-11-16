"""Stage 6 Clinic Industry Agent (`OrganizationIndustry.CLINIC`)."""

from typing import List
from app.agents.base import BaseIndustryAgent
from app.agents.schemas import AgentToolName
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

    @property
    def allowed_tools(self) -> List[AgentToolName]:
        """Approved backend tools available to the clinic agent in Stage 6."""
        return [
            AgentToolName.GET_BUSINESS_PROFILE,
            AgentToolName.GET_BUSINESS_HOURS,
            AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
            AgentToolName.SAVE_CONVERSATION_SUMMARY,
            AgentToolName.REQUEST_HUMAN_ESCALATION,
            AgentToolName.GET_CLINIC_INFORMATION,
            AgentToolName.GET_CLINIC_DEPARTMENTS,
            AgentToolName.GET_CLINIC_DOCTORS,
            AgentToolName.GET_CLINIC_SPECIALITIES,
            AgentToolName.GET_CLINIC_CONSULTATION_TYPES,
            AgentToolName.CHECK_CLINIC_AVAILABILITY,
            AgentToolName.CREATE_CLINIC_APPOINTMENT,
            AgentToolName.RESCHEDULE_CLINIC_APPOINTMENT,
            AgentToolName.CANCEL_CLINIC_APPOINTMENT,
            AgentToolName.REQUEST_CLINIC_HUMAN_ESCALATION,
        ]

    def build_industry_directives(self, bundle: OnboardingBundleResponse) -> str:
        business_name = bundle.profile.display_name
        return (
            f"CLINIC INDUSTRY INSTRUCTIONS ({business_name} — ADMINISTRATIVE-ONLY RECEPTIONIST):\n"
            "- You act strictly as an ADMINISTRATIVE-ONLY receptionist for the clinic.\n"
            "- Use `get_clinic_information`, `get_clinic_departments`, `get_clinic_specialities`, "
            "`get_clinic_doctors`, and `get_clinic_consultation_types` to answer clinic administrative enquiries.\n"
            "- When a caller wants to book a doctor consultation:\n"
            "  1. Identify the doctor (or department/speciality), consultation type, and preferred date.\n"
            "  2. Check real-time slot availability using `check_clinic_availability`.\n"
            "  3. Before booking, confirm the doctor, consultation type, date, time, timezone, and minimum patient details (name & contact).\n"
            "  4. Call `create_clinic_appointment` and confirm the booking ONLY after receiving a committed backend response with the booking reference.\n"
            "  5. If the slot is no longer available, apologize and offer alternative available slots.\n"
            "- For rescheduling or cancellation:\n"
            "  1. Always require both the booking reference and patient contact verification.\n"
            "  2. Call `reschedule_clinic_appointment` or `cancel_clinic_appointment`.\n"
            "  3. Never reveal private appointment details if verification fails.\n"
            "- STRICT HEALTHCARE SAFEGUARDS (MANDATORY):\n"
            "  1. NEVER provide medical diagnosis, diagnose diseases, interpret symptoms, or interpret medical test results.\n"
            "  2. NEVER prescribe medications, suggest dosages, or recommend medical treatments.\n"
            "  3. NEVER perform clinical triage or replace a healthcare professional.\n"
            "  4. Escalate clinical, symptom, or medication questions to clinic staff via `request_clinic_human_escalation` (`urgency='clinical_staff'`).\n"
            "  5. If a caller describes a medical emergency, immediately stop normal booking and direct them to local emergency services or the nearest emergency department without asking delaying questions."
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
