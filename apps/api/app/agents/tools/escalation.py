"""Tool 5 & Phase 4H: `request_human_escalation` — Controlled Human Escalation Tool.

Requirements:
- Uses configured business `escalation_settings`.
- Creates a controlled escalation record and audit log entry.
- Never claims a person has been contacted live unless an actual notification
  integration confirms delivery (`notification_delivered = False` in Stage 4).
"""

from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from app.agents.context import (
    ConversationContextManager,
    redact_sensitive_summary_text,
)
from app.agents.schemas import (
    RequestHumanEscalationToolInput,
    RequestHumanEscalationToolOutput,
)
from app.modules.onboarding.schemas import OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry


def execute_request_human_escalation(
    *,
    bundle: OnboardingBundleResponse,
    session_id: str,
    raw_arguments: Dict[str, Any],
    context_manager: ConversationContextManager,
    actor_user_id: Optional[UUID] = None,
) -> RequestHumanEscalationToolOutput:
    """Validate and record a human escalation request using `bundle.escalation`."""
    validated = RequestHumanEscalationToolInput.model_validate(raw_arguments or {})
    escalation_cfg = bundle.escalation
    is_healthcare = bundle.organization.industry in {
        OrganizationIndustry.CLINIC,
        OrganizationIndustry.HOSPITAL,
    }

    redacted_summary = redact_sensitive_summary_text(
        validated.summary, is_healthcare=is_healthcare
    )

    if not escalation_cfg.enabled:
        fallback_phone = bundle.profile.phone
        fallback_email = bundle.profile.email
        audit_rejected = context_manager.record_audit_log(
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            session_id=session_id,
            actor_user_id=actor_user_id,
            action="agent.request_human_escalation.disabled",
            target_type="escalation_request",
            target_id=session_id,
            metadata={"reason": validated.reason, "urgency": validated.urgency.value},
        )
        return RequestHumanEscalationToolOutput(
            accepted=False,
            escalation_reference=None,
            status="escalation_disabled_for_business",
            urgency=validated.urgency,
            preferred_method=None,
            contact_name=None,
            contact_phone=fallback_phone,
            contact_email=fallback_email,
            escalation_instructions=None,
            notification_delivered=False,
            customer_message_directive=(
                "Automated escalation logging is disabled for this business. "
                "Share the direct reception contact details with the caller instead, "
                "and do NOT claim a staff member has been notified."
            ),
            audit_log_id=audit_rejected.id,
        )

    ref_code = f"ESC-{uuid4().hex[:8].upper()}"
    preferred_method = escalation_cfg.preferred_method.value
    contact_name = escalation_cfg.contact_name or f"{bundle.profile.display_name} Reception"
    contact_phone = escalation_cfg.contact_phone or bundle.profile.phone
    contact_email = escalation_cfg.contact_email or bundle.profile.email

    context_manager.save_escalation_record(
        organization_id=bundle.organization.id,
        business_id=bundle.business_id,
        session_id=session_id,
        escalation_reference=ref_code,
        reason=validated.reason,
        summary=redacted_summary,
        urgency=validated.urgency.value,
        preferred_method=preferred_method,
        contact_name=contact_name,
    )

    audit_entry = context_manager.record_audit_log(
        organization_id=bundle.organization.id,
        business_id=bundle.business_id,
        session_id=session_id,
        actor_user_id=actor_user_id,
        action="agent.request_human_escalation.accepted",
        target_type="escalation_request",
        target_id=ref_code,
        metadata={
            "escalation_reference": ref_code,
            "reason": validated.reason,
            "urgency": validated.urgency.value,
            "preferred_method": preferred_method,
            "notification_delivered": False,
        },
    )

    return RequestHumanEscalationToolOutput(
        accepted=True,
        escalation_reference=ref_code,
        status="pending_human_review",
        urgency=validated.urgency,
        preferred_method=preferred_method,
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        escalation_instructions=escalation_cfg.escalation_instructions,
        notification_delivered=False,
        customer_message_directive=(
            f"Escalation request {ref_code} has been recorded with status 'pending_human_review'. "
            "Inform the caller of reference code "
            f"{ref_code} and provide the direct contact ({contact_name}: {contact_phone or contact_email or 'reception desk'}). "
            "IMPORTANT: Do NOT claim a person has already been contacted or notified in real time."
        ),
        audit_log_id=audit_entry.id,
    )
