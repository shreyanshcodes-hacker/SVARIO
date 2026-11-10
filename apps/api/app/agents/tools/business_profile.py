"""Tool 1: `get_business_profile` — Verified Business Profile Retrieval."""

from datetime import datetime, timezone
from typing import Any, Dict
from app.agents.schemas import (
    GetBusinessProfileToolInput,
    GetBusinessProfileToolOutput,
    SourceMetadata,
)
from app.modules.onboarding.schemas import OnboardingBundleResponse


def execute_get_business_profile(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
) -> GetBusinessProfileToolOutput:
    """Validate input and return verified business profile for backend-resolved business."""
    # Validate that no arbitrary extra arguments (such as organization_id) were passed
    GetBusinessProfileToolInput.model_validate(raw_arguments or {})

    profile = bundle.profile
    languages = bundle.languages
    assistant = bundle.assistant

    if (
        profile.organization_id != bundle.organization.id
        or profile.business_id != bundle.business_id
        or languages.organization_id != bundle.organization.id
        or assistant.organization_id != bundle.organization.id
    ):
        raise ValueError("Tenant ownership mismatch on business profile bundle.")

    location_parts = [
        p
        for p in [
            profile.address,
            profile.city,
            profile.state,
            profile.country,
            profile.postal_code,
        ]
        if p
    ]
    address_summary = ", ".join(location_parts) if location_parts else None

    return GetBusinessProfileToolOutput(
        business_name=profile.display_name,
        industry=bundle.organization.industry,
        description=profile.description,
        phone=profile.phone,
        email=profile.email,
        website=profile.website,
        address_summary=address_summary,
        city=profile.city,
        state=profile.state,
        country=profile.country,
        postal_code=profile.postal_code,
        timezone=profile.timezone,
        primary_language=languages.primary_language,
        supported_languages=languages.supported_languages,
        assistant_name=assistant.assistant_name,
        assistant_greeting=assistant.greeting,
        assistant_personality=assistant.personality.value,
        assistant_response_style=assistant.response_style.value,
        assistant_enabled=assistant.enabled,
        source_metadata=SourceMetadata(
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            source_tables=[
                "business_profiles",
                "business_languages",
                "assistant_settings",
            ],
            retrieved_at=datetime.now(timezone.utc),
        ),
    )
