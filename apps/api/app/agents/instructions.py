"""Stage 4 Common Base Instructions, Industry Instructions, Multilingual Rules & Tool Definitions."""

from typing import Any, Dict, Iterable, List, Optional
from app.agents.industries import get_industry_agent
from app.agents.schemas import AgentToolName
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    LanguageCode,
    OnboardingBundleResponse,
    WeekdayHoursItem,
)
from app.modules.organizations.schemas import OrganizationIndustry

WEEKDAY_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}

LANGUAGE_DESCRIPTIONS = {
    LanguageCode.ENGLISH: "English (en)",
    LanguageCode.HINDI: "Hindi (hi — देवनागरी / spoken Hindi)",
    LanguageCode.HINGLISH: "Hinglish (conversational Hindi-English mix)",
}

PERSONALITY_DIRECTIVES = {
    AssistantPersonality.PROFESSIONAL: (
        "Maintain a composed, courteous, and professional receptionist demeanor."
    ),
    AssistantPersonality.FRIENDLY: (
        "Maintain an approachable, upbeat, and welcoming receptionist demeanor."
    ),
    AssistantPersonality.WARM: (
        "Maintain an empathetic, calm, and reassuring receptionist demeanor."
    ),
}

STYLE_DIRECTIVES = {
    AssistantResponseStyle.CONCISE: (
        "Keep spoken responses brief and direct (1 to 2 short sentences per turn)."
    ),
    AssistantResponseStyle.BALANCED: (
        "Keep spoken responses clear, natural, and well-paced (2 to 3 sentences per turn)."
    ),
    AssistantResponseStyle.DETAILED: (
        "Provide thorough, clear explanations while remaining natural for spoken conversation."
    ),
}


def _format_hours_summary(schedule: List[WeekdayHoursItem], timezone: str) -> str:
    lines: List[str] = []
    for item in sorted(schedule, key=lambda s: s.weekday):
        day_name = WEEKDAY_NAMES.get(item.weekday, f"Day {item.weekday}")
        if item.is_closed:
            lines.append(f"- {day_name}: Closed")
        else:
            suffix = " (next day)" if item.is_overnight else ""
            lines.append(f"- {day_name}: {item.opens_at} to {item.closes_at}{suffix}")
    return f"Configured Operating Hours ({timezone}):\n" + "\n".join(lines)


def build_stage4_agent_instructions(bundle: OnboardingBundleResponse) -> str:
    """Compose the complete Stage 4 common + industry + multilingual instruction set."""
    industry_agent = get_industry_agent(bundle.organization.industry)
    profile = bundle.profile
    assistant = bundle.assistant
    languages = bundle.languages

    primary_lang = LANGUAGE_DESCRIPTIONS.get(
        languages.primary_language, languages.primary_language.value
    )
    supported_langs = ", ".join(
        LANGUAGE_DESCRIPTIONS.get(code, code.value)
        for code in languages.supported_languages
    )

    personality = PERSONALITY_DIRECTIVES.get(
        assistant.personality, PERSONALITY_DIRECTIVES[AssistantPersonality.PROFESSIONAL]
    )
    style = STYLE_DIRECTIVES.get(
        assistant.response_style, STYLE_DIRECTIVES[AssistantResponseStyle.BALANCED]
    )

    booking_boundary_rule = (
        "6. Backend-Confirmed Scheduling Boundary: Only perform appointment booking, rescheduling, or cancellation "
        "using your approved industry scheduling tools, and NEVER claim an appointment is booked, rescheduled, or "
        "cancelled unless the backend tool returns a confirmed committed result."
        if bundle.organization.industry in {OrganizationIndustry.SALON, OrganizationIndustry.CLINIC}
        else "6. Pre-Booking Industry Boundary: Recognising booking, rescheduling, or cancellation intent does NOT "
        "create or modify appointments for this industry yet. Collect the caller's preferences without claiming an "
        "appointment has been booked."
    )

    common_base = (
        "COMMON SVARIO AGENT OPERATING RULES:\n"
        f"1. Identity & Introduction: You are {assistant.assistant_name}, the AI voice receptionist for "
        f"{profile.display_name} ({bundle.organization.industry.value}). Introduce yourself naturally using "
        f"the configured greeting: \"{assistant.greeting}\".\n"
        f"2. Persona & Delivery: {personality} {style}\n"
        "3. Tool-Backed Truthfulness: Retrieve business profile details (`get_business_profile`), operating hours "
        "(`get_business_hours`), and FAQ/service/department answers (`search_business_knowledge`) using your approved tools. "
        "NEVER fabricate services, prices, doctor schedules, department extensions, or policies.\n"
        "4. Clarification & Uncertainty: If a caller's request is ambiguous or missing details, ask a brief, polite "
        "clarification question. If the requested fact is not in verified business data, openly admit uncertainty and "
        "offer to log a human escalation request (`request_human_escalation`).\n"
        "5. Backend Confirmation Requirement: NEVER claim that a conversation summary was saved or that a human escalation "
        "request was recorded until the corresponding backend tool (`save_conversation_summary` or `request_human_escalation`) "
        "returns a confirmed result. Even after `request_human_escalation` succeeds, state clearly that a callback/follow-up "
        "request has been logged for the team—do NOT claim a human staff member has already been contacted live.\n"
        f"{booking_boundary_rule}"
    )

    multilingual_rules = (
        "MULTILINGUAL SUPPORT POLICY (ENGLISH, HINDI, HINGLISH):\n"
        f"- Primary Business Language: {primary_lang}.\n"
        f"- Supported Languages for this Business: {supported_langs}.\n"
        "- Respond in the caller's preferred or detected language (English, Hindi, or Hinglish) when supported.\n"
        "- Allow the caller to switch between English, Hindi, and Hinglish at any point during the conversation.\n"
        "- Keep all verified business facts (business name, prices, phone numbers, email addresses, street addresses, and timings) "
        "exact and consistent across languages—never mistranslate proper nouns or numbers.\n"
        "- If you are uncertain which language the caller prefers, politely ask which language (English, Hindi, or Hinglish) they prefer."
    )

    industry_rules = industry_agent.build_industry_directives(bundle)

    baseline_facts: List[str] = [
        f"Business Display Name: {profile.display_name}",
        f"Timezone: {profile.timezone}",
    ]
    if profile.description:
        baseline_facts.append(f"Description: {profile.description}")
    location_parts = [
        p for p in [profile.address, profile.city, profile.state, profile.country] if p
    ]
    if location_parts:
        baseline_facts.append(f"Location: {', '.join(location_parts)}")
    if profile.phone:
        baseline_facts.append(f"Reception Phone: {profile.phone}")
    if profile.email:
        baseline_facts.append(f"Reception Email: {profile.email}")

    sections = [
        common_base,
        multilingual_rules,
        industry_rules,
        "VERIFIED BUSINESS BASELINE:\n" + "\n".join(baseline_facts),
    ]

    if bundle.hours and bundle.hours.schedule:
        sections.append(_format_hours_summary(bundle.hours.schedule, bundle.hours.timezone))

    active_faqs = [faq for faq in bundle.faqs if faq.is_active]
    if active_faqs:
        faq_lines = [
            f"- [{faq.category}] Q: {faq.question} -> A: {faq.answer}"
            for faq in active_faqs[:20]
        ]
        sections.append("VERIFIED ACTIVE BUSINESS FAQS:\n" + "\n".join(faq_lines))

    return "\n\n".join(sections)


def build_realtime_tool_definitions(
    allowed_tools: Optional[Iterable[AgentToolName]] = None,
) -> List[Dict[str, Any]]:
    """Return OpenAI Realtime API function tool definitions, filtered by allowed_tools when provided."""
    all_tools: List[Dict[str, Any]] = [
        {
            "type": "function",
            "name": "get_business_profile",
            "description": (
                "Retrieve verified business profile details including business name, "
                "description, phone, email, website, address, and supported languages."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_business_hours",
            "description": (
                "Retrieve the business's verified weekly operating schedule and timezone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "weekday": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 6,
                        "description": "Optional weekday filter (0=Sunday through 6=Saturday).",
                    }
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "search_business_knowledge",
            "description": (
                "Search the business's verified active FAQs, services, specialities, "
                "departments, pricing, and policies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Customer question or topic keywords to search in verified business knowledge.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional FAQ category filter (e.g. hours, location, services, pricing, visiting).",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "save_conversation_summary",
            "description": (
                "Save a privacy-aware, non-sensitive summary of the conversation and any "
                "captured booking preferences (without creating an actual booking)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary_text": {
                        "type": "string",
                        "description": "Concise, non-sensitive summary of the caller's enquiry.",
                    },
                    "primary_intent": {
                        "type": "string",
                        "enum": [
                            "greeting",
                            "business_information",
                            "opening_hours",
                            "location",
                            "services_enquiry",
                            "pricing_enquiry",
                            "speciality_enquiry",
                            "department_enquiry",
                            "booking_intent",
                            "rescheduling_intent",
                            "cancellation_intent",
                            "human_support",
                            "emergency_intent",
                            "unknown",
                        ],
                    },
                    "detected_language": {
                        "type": "string",
                        "enum": ["en", "hi", "hinglish"],
                    },
                    "booking_preferences": {
                        "type": "object",
                        "description": "Optional key-value preferences (e.g. preferred_service, preferred_day, preferred_time).",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["summary_text"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "request_human_escalation",
            "description": (
                "Create a controlled human escalation request when the caller asks for a person, "
                "when a question cannot be answered from verified business knowledge, or when "
                "a clinical question requires qualified healthcare staff."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for human escalation.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief non-sensitive summary for the human staff member.",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": [
                            "standard",
                            "priority",
                            "clinical_staff",
                            "emergency_redirected",
                        ],
                    },
                },
                "required": ["reason", "summary"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_salon_services",
            "description": "Retrieve active salon services, treatments, categories, pricing, and durations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category filter (e.g. hair, nails, facial).",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "Filter by active status (default true).",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_salon_staff",
            "description": "Retrieve qualified stylists and specialists, optionally filtered by service_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "Optional UUID of a service to filter qualified staff.",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "check_salon_availability",
            "description": "Check real-time non-conflicting available appointment slots for a salon service on a date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "UUID of the salon service.",
                    },
                    "requested_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (e.g. 2026-11-16).",
                    },
                    "staff_id": {
                        "type": "string",
                        "description": "Optional UUID of preferred stylist.",
                    },
                },
                "required": ["service_id", "requested_date"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "create_salon_appointment",
            "description": "Book a confirmed salon appointment for a customer after verifying availability and getting customer confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "UUID of the salon service.",
                    },
                    "appointment_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in HH:MM format from check_salon_availability.",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Full name of the customer.",
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "Phone number of the customer.",
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Optional email of the customer.",
                    },
                    "staff_id": {
                        "type": "string",
                        "description": "Optional UUID of the preferred stylist.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes or requests from the customer.",
                    },
                    "idempotency_key": {
                        "type": "string",
                        "description": "Optional client idempotency key to prevent double-booking.",
                    },
                },
                "required": [
                    "service_id",
                    "appointment_date",
                    "start_time",
                    "customer_name",
                    "customer_phone",
                ],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "reschedule_salon_appointment",
            "description": "Reschedule an existing confirmed salon appointment to a new date and start time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the existing salon appointment.",
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New date in YYYY-MM-DD format.",
                    },
                    "new_start_time": {
                        "type": "string",
                        "description": "New start time in HH:MM format.",
                    },
                    "new_staff_id": {
                        "type": "string",
                        "description": "Optional new staff UUID.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional updated notes.",
                    },
                },
                "required": ["appointment_id", "new_date", "new_start_time"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "cancel_salon_appointment",
            "description": "Cancel an existing confirmed salon appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the salon appointment to cancel.",
                    },
                    "cancellation_reason": {
                        "type": "string",
                        "description": "Optional reason for cancellation.",
                    },
                },
                "required": ["appointment_id"],
                "additionalProperties": False,
            },
        },
        # Stage 6 Clinic Workflow Tools
        {
            "type": "function",
            "name": "get_clinic_information",
            "description": "Retrieve verified clinic profile, operating hours, location, and supported languages.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_clinic_departments",
            "description": "List active clinical departments at the clinic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {"type": "boolean", "description": "Return only active departments."}
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_clinic_specialities",
            "description": "List active medical specialities offered at the clinic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {"type": "boolean", "description": "Return only active specialities."}
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_clinic_doctors",
            "description": "List clinic doctors, optionally filtered by department_id or speciality_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "department_id": {"type": "string", "description": "Optional department UUID filter."},
                    "speciality_id": {"type": "string", "description": "Optional speciality UUID filter."},
                    "active_only": {"type": "boolean", "description": "Return only active doctors."},
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "get_clinic_consultation_types",
            "description": "List active consultation types, modes (in_person/online), durations, and configured fees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {"type": "boolean", "description": "Return only active consultation types."}
                },
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "check_clinic_availability",
            "description": "Check real-time available clinic appointment slots for a consultation type and date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consultation_type_id": {"type": "string", "description": "UUID of the consultation type."},
                    "target_date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                    "doctor_id": {"type": "string", "description": "Optional doctor UUID filter."},
                    "department_id": {"type": "string", "description": "Optional department UUID filter."},
                    "speciality_id": {"type": "string", "description": "Optional speciality UUID filter."},
                },
                "required": ["consultation_type_id", "target_date"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "create_clinic_appointment",
            "description": "Book a clinic appointment after confirming doctor, consultation type, date/time, and minimum patient details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "UUID of the doctor."},
                    "consultation_type_id": {"type": "string", "description": "UUID of the consultation type."},
                    "department_id": {"type": "string", "description": "Optional department UUID."},
                    "patient_display_name": {"type": "string", "description": "Patient name."},
                    "patient_contact": {"type": "string", "description": "Minimum patient contact (phone or email)."},
                    "starts_at": {"type": "string", "description": "ISO-8601 datetime with timezone."},
                    "idempotency_key": {"type": "string", "description": "Optional idempotency key."},
                },
                "required": [
                    "doctor_id",
                    "consultation_type_id",
                    "patient_display_name",
                    "patient_contact",
                    "starts_at",
                ],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "reschedule_clinic_appointment",
            "description": "Reschedule an existing clinic appointment after verifying booking_reference and patient contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_reference": {"type": "string", "description": "Clinic booking reference (e.g. CLN-...)."},
                    "patient_contact_verification": {"type": "string", "description": "Patient contact or last 4+ digits for verification."},
                    "new_starts_at": {"type": "string", "description": "New ISO-8601 datetime with timezone."},
                    "new_doctor_id": {"type": "string", "description": "Optional new doctor UUID."},
                },
                "required": ["booking_reference", "patient_contact_verification", "new_starts_at"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "cancel_clinic_appointment",
            "description": "Cancel an existing clinic appointment after verifying booking_reference and patient contact.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_reference": {"type": "string", "description": "Clinic booking reference (e.g. CLN-...)."},
                    "patient_contact_verification": {"type": "string", "description": "Patient contact or last 4+ digits for verification."},
                    "reason": {"type": "string", "description": "Optional cancellation reason."},
                },
                "required": ["booking_reference", "patient_contact_verification"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "request_clinic_human_escalation",
            "description": "Log a clinic human escalation or callback request for reception or clinical staff.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for escalation."},
                    "summary": {"type": "string", "description": "Brief non-sensitive summary."},
                    "urgency": {
                        "type": "string",
                        "enum": ["standard", "priority", "clinical_staff", "emergency_redirected"],
                    },
                },
                "required": ["reason", "summary"],
                "additionalProperties": False,
            },
        },
    ]
    if allowed_tools is None:
        return all_tools
    permitted_names = {tool.value for tool in allowed_tools}
    return [tool for tool in all_tools if tool.get("name") in permitted_names]
