"""Server-authoritative system instruction builder for Stage 3 Voice Sessions.

Security & Product Rules:
- Never accepts arbitrary system instructions from browser clients.
- Uses only verified organization/business configuration from Stage 2 onboarding:
  - business display name & location summary
  - supported languages (`en`, `hi`, `hinglish`)
  - assistant name, greeting, personality, and response style
  - configured operating hours & active FAQs
  - human escalation contact details
- Enforces Stage 3 shared infrastructure scope (no appointment booking or
  transactional workflows in Stage 3).
- Enforces mandatory administrative-only healthcare guardrails for `clinic`
  and `hospital` organizations.
"""

from typing import List
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

LANGUAGE_LABELS = {
    LanguageCode.ENGLISH: "English (en)",
    LanguageCode.HINDI: "Hindi (hi)",
    LanguageCode.HINGLISH: "Hinglish (conversational Hindi-English blend)",
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


def _format_weekly_hours(schedule: List[WeekdayHoursItem], timezone: str) -> str:
    lines: List[str] = []
    for item in sorted(schedule, key=lambda s: s.weekday):
        day_name = WEEKDAY_NAMES.get(item.weekday, f"Day {item.weekday}")
        if item.is_closed:
            lines.append(f"- {day_name}: Closed")
        else:
            overnight_suffix = " (next day)" if item.is_overnight else ""
            lines.append(
                f"- {day_name}: {item.opens_at} to {item.closes_at}{overnight_suffix}"
            )
    return f"Operating Hours ({timezone}):\n" + "\n".join(lines)


def build_safe_realtime_instructions(bundle: OnboardingBundleResponse) -> str:
    """Compose deterministic, server-authoritative Realtime instructions."""
    industry = bundle.organization.industry
    profile = bundle.profile
    assistant = bundle.assistant
    languages = bundle.languages
    escalation = bundle.escalation

    primary_lang_label = LANGUAGE_LABELS.get(
        languages.primary_language, languages.primary_language.value
    )
    supported_lang_labels = ", ".join(
        LANGUAGE_LABELS.get(lang, lang.value) for lang in languages.supported_languages
    )

    personality_line = PERSONALITY_DIRECTIVES.get(
        assistant.personality, PERSONALITY_DIRECTIVES[AssistantPersonality.PROFESSIONAL]
    )
    style_line = STYLE_DIRECTIVES.get(
        assistant.response_style, STYLE_DIRECTIVES[AssistantResponseStyle.BALANCED]
    )

    sections: List[str] = [
        f"You are {assistant.assistant_name}, the AI voice receptionist for {profile.display_name} "
        f"(industry vertical: {industry.value}).",
        f"Opening Greeting: When the conversation begins or the caller greets you, welcome them using: \"{assistant.greeting}\"",
        f"Persona & Delivery: {personality_line} {style_line}",
        f"Language Policy: Default to {primary_lang_label}. You may converse only in the business's configured languages: {supported_lang_labels}.",
    ]

    # Business profile summary
    location_parts = [
        p for p in [profile.address, profile.city, profile.state, profile.country] if p
    ]
    profile_lines: List[str] = [f"Business Name: {profile.display_name}"]
    if profile.description:
        profile_lines.append(f"Overview: {profile.description}")
    if location_parts:
        profile_lines.append(f"Location: {', '.join(location_parts)}")
    if profile.phone:
        profile_lines.append(f"Reception Phone: {profile.phone}")
    if profile.email:
        profile_lines.append(f"Reception Email: {profile.email}")
    if profile.website:
        profile_lines.append(f"Website: {profile.website}")
    sections.append("Verified Business Details:\n" + "\n".join(profile_lines))

    # Operating hours
    if bundle.hours and bundle.hours.schedule:
        sections.append(_format_weekly_hours(bundle.hours.schedule, bundle.hours.timezone))

    # Active FAQs
    active_faqs = [faq for faq in bundle.faqs if faq.is_active]
    if active_faqs:
        faq_lines = [
            f"- Q ({faq.category}): {faq.question}\n  A: {faq.answer}"
            for faq in active_faqs[:20]
        ]
        sections.append("Verified Business FAQs:\n" + "\n".join(faq_lines))

    # Human escalation rules
    if escalation.enabled:
        esc_details: List[str] = []
        if escalation.contact_name:
            esc_details.append(f"Contact: {escalation.contact_name}")
        if escalation.contact_phone:
            esc_details.append(f"Phone: {escalation.contact_phone}")
        if escalation.contact_email:
            esc_details.append(f"Email: {escalation.contact_email}")
        if escalation.escalation_instructions:
            esc_details.append(f"Instructions: {escalation.escalation_instructions}")
        sections.append(
            "Human Escalation Policy: If a caller requests a human staff member or asks a question "
            "outside your verified business information, direct them via "
            f"{escalation.preferred_method.value}. " + " | ".join(esc_details)
        )

    # Stage 3 Shared Infrastructure Boundary
    sections.append(
        "Stage 3 Operational Boundary: You are operating on the shared voice reception infrastructure. "
        "Answer general inquiries using only the verified business details, operating hours, and FAQs above. "
        "Do not invent prices, staff schedules, or unverified facts. "
        "Automated appointment booking, rescheduling, and industry-specific transactional workflows "
        "are not enabled in this stage—if a caller asks to book or modify an appointment, politely "
        "share the business's operating hours and direct them to the reception contact."
    )

    # Mandatory Healthcare Guardrails for Clinics & Hospitals
    if industry in {OrganizationIndustry.CLINIC, OrganizationIndustry.HOSPITAL}:
        sections.append(
            "MANDATORY HEALTHCARE & ADMINISTRATIVE SAFEGUARDS (STRICT ENFORCEMENT):\n"
            "1. You are an ADMINISTRATIVE-ONLY receptionist for a healthcare organization.\n"
            "2. NEVER provide medical diagnosis, clinical opinions, symptom triage, prescriptions, "
            "medication dosing, or treatment recommendations under any circumstances.\n"
            "3. Do NOT ask for or collect sensitive patient medical history or clinical symptoms.\n"
            "4. If a caller describes a medical emergency, chest pain, breathing difficulty, severe bleeding, "
            "or urgent distress, immediately instruct them to hang up and contact local emergency services "
            "or proceed to the nearest hospital emergency department."
        )

    return "\n\n".join(sections)
