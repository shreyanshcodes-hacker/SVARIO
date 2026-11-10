"""Stage 4 Common Base Instructions, Industry Instructions, Multilingual Rules & Tool Definitions."""

from typing import Any, Dict, List
from app.agents.industries import get_industry_agent
from app.modules.onboarding.schemas import (
    AssistantPersonality,
    AssistantResponseStyle,
    LanguageCode,
    OnboardingBundleResponse,
    WeekdayHoursItem,
)

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

    common_base = (
        "COMMON SVARIO AGENT OPERATING RULES (STAGE 4):\n"
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
        "6. Stage 4 Booking Boundary: Recognising booking, rescheduling, or cancellation intent does NOT create or modify "
        "appointments in Stage 4. Collect the caller's preferences without claiming an appointment has been booked."
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


def build_realtime_tool_definitions() -> List[Dict[str, Any]]:
    """Return the OpenAI Realtime API function tool definitions for Stage 4."""
    return [
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
    ]
