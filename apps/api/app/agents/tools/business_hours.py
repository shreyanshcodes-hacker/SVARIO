"""Tool 2: `get_business_hours` — Verified Weekly Operating Schedule Retrieval."""

from datetime import datetime, timezone
from typing import Any, Dict
from app.agents.schemas import (
    GetBusinessHoursToolInput,
    GetBusinessHoursToolOutput,
    SourceMetadata,
)
from app.modules.onboarding.schemas import OnboardingBundleResponse


def execute_get_business_hours(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
) -> GetBusinessHoursToolOutput:
    """Validate input and return verified weekly business hours for backend-resolved business."""
    validated = GetBusinessHoursToolInput.model_validate(raw_arguments or {})

    if (
        bundle.hours.organization_id != bundle.organization.id
        or bundle.hours.business_id != bundle.business_id
    ):
        raise ValueError("Tenant ownership mismatch on business hours bundle.")

    schedule = list(bundle.hours.schedule)
    if validated.weekday is not None:
        schedule = [item for item in schedule if item.weekday == validated.weekday]

    return GetBusinessHoursToolOutput(
        business_name=bundle.profile.display_name,
        timezone=bundle.hours.timezone,
        schedule=schedule,
        source_metadata=SourceMetadata(
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            source_tables=["business_hours"],
            retrieved_at=datetime.now(timezone.utc),
        ),
    )
