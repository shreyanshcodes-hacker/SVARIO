"""Stage 5 Salon Industry Agent (`OrganizationIndustry.SALON`)."""

from datetime import datetime, timezone
from typing import List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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
        raw_tz = (bundle.profile.timezone or "Asia/Kolkata").strip()
        tz_name = {"IST": "Asia/Kolkata", "IND": "Asia/Kolkata"}.get(raw_tz.upper(), raw_tz)
        try:
            now_local = datetime.now(ZoneInfo(tz_name))
        except ZoneInfoNotFoundError:
            tz_name = "UTC"
            now_local = datetime.now(timezone.utc)
        today_str = now_local.strftime("%Y-%m-%d (%A)")

        return (
            f"SALON INDUSTRY INSTRUCTIONS ({business_name}):\n"
            f"- Current Local Date: {today_str} ({tz_name}). Use this date when resolving relative dates such as 'today' or 'tomorrow' into YYYY-MM-DD format.\n"
            "- Help callers with general salon information, location, operating hours, active services, pricing, durations, and appointments.\n"
            "- SERVICE & PRICING ENQUIRIES: Whenever a caller asks about services, treatments, pricing, or durations, ALWAYS call `get_salon_services` (and `search_business_knowledge` if they ask about general policies/FAQs). Answer strictly from the returned records (service name, category, price, currency, duration). Never invent service names, prices, durations, or discounts. If no matching service is returned, clearly inform the caller.\n"
            "- STAFF ENQUIRIES: Call `get_salon_staff` when a caller asks for stylists or has a stylist preference.\n"
            "- APPOINTMENT BOOKING WORKFLOW (follow every step in order):\n"
            "  1. Understand the request: identify service, requested date, preferred time, customer name, customer phone, and optional preferred stylist. Ask naturally for any missing details.\n"
            "  2. Fetch services via `get_salon_services` and resolve the real `service_id`. NEVER fabricate a `service_id`.\n"
            "  3. Fetch staff via `get_salon_staff` if the caller requests a specific stylist or recommendations.\n"
            "  4. Check real-time availability via `check_salon_availability` using the real `service_id` and `YYYY-MM-DD` date. Use actual returned slots and `staff_id` values. If the requested slot is unavailable, suggest available alternatives. Never assume a time is available.\n"
            "  5. Explicit customer confirmation BEFORE booking: clearly repeat the Service, Date, Time, Stylist (if applicable), Price, Customer Name, and Customer Phone, and ask for explicit confirmation. NEVER call `create_salon_appointment` before the customer confirms.\n"
            "  6. Commit the booking: only after explicit confirmation, call `create_salon_appointment` with the verified `service_id`, `appointment_date`, `start_time`, `customer_name`, `customer_phone`, and optional `staff_id`.\n"
            "  7. Confirm the result: ONLY when `create_salon_appointment` returns `booking_confirmed: true`, share the real `booking_reference`, service, date, time, stylist, duration, and price. If the backend rejects or fails, explain clearly that the booking was NOT completed.\n"
            "- RESCHEDULING & CANCELLATION: Identify the existing appointment, check availability via `check_salon_availability` before rescheduling, require explicit customer confirmation before modifying or cancelling, and call `reschedule_salon_appointment` or `cancel_salon_appointment`. Report the actual backend result."
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
