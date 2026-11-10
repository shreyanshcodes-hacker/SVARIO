"""Tool 4: `save_conversation_summary` — Privacy-Aware Conversation Summary Tool."""

from typing import Any, Dict, Optional
from uuid import UUID
from app.agents.context import (
    ConversationContextManager,
    redact_sensitive_summary_text,
)
from app.agents.schemas import (
    SaveConversationSummaryToolInput,
    SaveConversationSummaryToolOutput,
)
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry


def execute_save_conversation_summary(
    *,
    bundle: OnboardingBundleResponse,
    session_id: str,
    raw_arguments: Dict[str, Any],
    context_manager: ConversationContextManager,
    actor_user_id: Optional[UUID] = None,
    persist_enabled: bool = True,
) -> SaveConversationSummaryToolOutput:
    """Validate, redact, and persist a non-sensitive conversation summary."""
    validated = SaveConversationSummaryToolInput.model_validate(raw_arguments or {})
    is_healthcare = bundle.organization.industry in {
        OrganizationIndustry.CLINIC,
        OrganizationIndustry.HOSPITAL,
    }

    redacted = redact_sensitive_summary_text(
        validated.summary_text, is_healthcare=is_healthcare
    )

    # Filter booking preferences to safe non-clinical administrative keys
    safe_prefs: Dict[str, str] = {}
    for k, v in (validated.booking_preferences or {}).items():
        clean_k = str(k).strip()[:64]
        clean_v = redact_sensitive_summary_text(
            str(v).strip()[:160], is_healthcare=is_healthcare
        )
        if clean_k and clean_v:
            safe_prefs[clean_k] = clean_v

    summary_id = context_manager.save_summary_record(
        organization_id=bundle.organization.id,
        business_id=bundle.business_id,
        session_id=session_id,
        primary_intent=validated.primary_intent,
        detected_language=validated.detected_language,
        redacted_summary=redacted,
        booking_preferences=safe_prefs,
        persist_enabled=persist_enabled,
    )

    audit_entry = context_manager.record_audit_log(
        organization_id=bundle.organization.id,
        business_id=bundle.business_id,
        session_id=session_id,
        actor_user_id=actor_user_id,
        action="agent.save_conversation_summary",
        target_type="conversation_summary",
        target_id=str(summary_id or session_id),
        metadata={
            "primary_intent": validated.primary_intent.value,
            "detected_language": validated.detected_language.value,
            "persist_enabled": persist_enabled,
            "booking_preferences_keys": sorted(safe_prefs.keys()),
        },
    )

    return SaveConversationSummaryToolOutput(
        saved=True,
        persistence_mode="persisted" if persist_enabled else "session_ephemeral_only",
        summary_id=summary_id,
        session_id=session_id,
        redacted_summary=redacted,
        booking_preferences_captured=safe_prefs,
        booking_created=False,
        audit_log_id=audit_entry.id,
    )
