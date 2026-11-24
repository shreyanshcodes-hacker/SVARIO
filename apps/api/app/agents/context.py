"""Phase 4E — Session-Scoped, Tenant-Isolated Conversation Context & Privacy Redaction.

Security & Privacy Guarantees:
- Never mixes context across sessions, businesses, or organizations.
- Rejects any access to a `session_id` if `(organization_id, business_id)` does not
  match the session's bound owner (`403 Forbidden`).
- Redacts unnecessary PII and clinical symptom disclosures from summaries.
- Never stores raw audio or patient medical histories.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from fastapi import HTTPException, status
from app.agents.schemas import (
    AgentIntent,
    AuditLogRecord,
    SessionConversationContext,
)
from app.modules.onboarding.schemas import LanguageCode
from app.modules.organizations.schemas import OrganizationIndustry

SENSITIVE_MEDICAL_KEYWORDS = re.compile(
    r"\b(hiv|cancer|tumor|insulin|diabetes|hypertension|depression|psychiatric|pregnancy|miscarriage|blood pressure|cholesterol|biopsy|chemotherapy|severe headache|fever|chest pain|bleeding)\b",
    re.IGNORECASE,
)

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
PHONE_OR_ID_REGEX = re.compile(r"(?:\+?\d[\d -]{8,15}\d)")


def redact_sensitive_summary_text(
    text: str, is_healthcare: bool = False
) -> str:
    """Redact email addresses, phone/ID digit sequences, and clinical medical history from summaries."""
    cleaned = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text.strip())
    cleaned = PHONE_OR_ID_REGEX.sub("[REDACTED_PHONE]", cleaned)
    if is_healthcare:
        cleaned = SENSITIVE_MEDICAL_KEYWORDS.sub(
            "[REDACTED_CLINICAL_DETAIL]", cleaned
        )
    return cleaned[:1500]


class ConversationContextManager:
    """Manages isolated session contexts, persisted summaries, escalations, and audit logs."""

    def __init__(self) -> None:
        self._contexts: Dict[str, SessionConversationContext] = {}
        self._saved_summaries: Dict[str, Dict[str, Any]] = {}
        self._escalations: Dict[str, Dict[str, Any]] = {}
        self._audit_logs: List[AuditLogRecord] = []

    def clear(self) -> None:
        """Reset all in-memory contexts, summaries, escalations, and audit logs (used in tests)."""
        self._contexts.clear()
        self._saved_summaries.clear()
        self._escalations.clear()
        self._audit_logs.clear()

    def initialize_session(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: OrganizationIndustry,
        initial_language: LanguageCode = LanguageCode.ENGLISH,
    ) -> SessionConversationContext:
        """Initialize a freshly minted voice session bound to `(organization_id, business_id)`."""
        cleaned_sid = session_id.strip()
        created = SessionConversationContext(
            session_id=cleaned_sid,
            organization_id=organization_id,
            business_id=business_id,
            industry=industry,
            detected_language=initial_language,
            last_updated_at=datetime.now(timezone.utc),
        )
        self._contexts[cleaned_sid] = created
        return created

    def get_or_create_context(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: OrganizationIndustry,
        initial_language: LanguageCode = LanguageCode.ENGLISH,
    ) -> SessionConversationContext:
        """Retrieve or initialize a session context strictly bound to `(organization_id, business_id)`."""
        cleaned_sid = session_id.strip()
        existing = self._contexts.get(cleaned_sid)

        if existing is not None:
            if (
                existing.organization_id != organization_id
                or existing.business_id != business_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Session context isolation violation: session_id is bound to a "
                        "different organization or business."
                    ),
                )
            return existing

        created = SessionConversationContext(
            session_id=cleaned_sid,
            organization_id=organization_id,
            business_id=business_id,
            industry=industry,
            detected_language=initial_language,
            last_updated_at=datetime.now(timezone.utc),
        )
        self._contexts[cleaned_sid] = created
        return created

    def start_new_turn(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: OrganizationIndustry,
        user_query: str,
    ) -> SessionConversationContext:
        """Increment turn counter, reset per-turn tool counter, and record normalized query."""
        ctx = self.get_or_create_context(
            session_id=session_id,
            organization_id=organization_id,
            business_id=business_id,
            industry=industry,
        )
        ctx.turn_count += 1
        ctx.tool_calls_in_current_turn = 0
        normalized_q = user_query.strip().lower()[:200]
        if normalized_q:
            ctx.recent_user_queries = [*ctx.recent_user_queries[-4:], normalized_q]
        ctx.last_updated_at = datetime.now(timezone.utc)
        return ctx

    def record_tool_call(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        max_tool_calls_per_turn: int = 3,
    ) -> SessionConversationContext:
        """Verify and increment the per-turn tool call counter."""
        ctx = self._contexts.get(session_id.strip())
        if ctx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice or agent session context not found.",
            )
        if ctx.organization_id != organization_id or ctx.business_id != business_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session context isolation violation.",
            )

        now = datetime.now(timezone.utc)
        # In live Realtime voice sessions, `start_new_turn()` is not called between spoken turns.
        # Reset the per-turn tool counter when a new spoken turn begins (>= 2s gap since last tool call)
        # while still blocking rapid back-to-back runaway tool bursts within a single turn.
        if (now - ctx.last_updated_at).total_seconds() >= 2.0:
            ctx.tool_calls_in_current_turn = 0
            ctx.turn_count += 1

        if ctx.tool_calls_in_current_turn >= max_tool_calls_per_turn:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Maximum tool calls per turn ({max_tool_calls_per_turn}) exceeded "
                    "for this conversation turn."
                ),
            )

        ctx.tool_calls_in_current_turn += 1
        ctx.total_tool_calls += 1
        ctx.last_updated_at = now
        return ctx

    def reset_turn_tool_counter(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
    ) -> None:
        """Reset per-turn tool counter (e.g. when a new Realtime user speech turn begins)."""
        ctx = self._contexts.get(session_id.strip())
        if (
            ctx is not None
            and ctx.organization_id == organization_id
            and ctx.business_id == business_id
        ):
            ctx.tool_calls_in_current_turn = 0
            ctx.last_updated_at = datetime.now(timezone.utc)

    def update_from_intent(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        intent: AgentIntent,
        confidence: float,
        detected_language: LanguageCode,
        entities: Dict[str, Any],
        clarification_question: Optional[str] = None,
    ) -> SessionConversationContext:
        """Update session context with latest intent, entities (non-sensitive), and clarification."""
        ctx = self._contexts[session_id.strip()]
        if ctx.organization_id != organization_id or ctx.business_id != business_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session context isolation violation.",
            )

        ctx.current_intent = intent
        ctx.detected_language = detected_language

        # Store only safe administrative entities (weekday, preferred_date, preferred_time, topic)
        safe_keys = {
            "weekday",
            "weekday_name",
            "preferred_date",
            "preferred_time",
            "topic",
            "language",
        }
        for key, value in entities.items():
            if key in safe_keys and value is not None:
                ctx.extracted_entities[key] = value

        if confidence < 0.55 or intent == AgentIntent.UNKNOWN:
            ctx.consecutive_low_confidence_turns += 1
        else:
            ctx.consecutive_low_confidence_turns = 0

        if clarification_question:
            ctx.previous_clarification_questions = [
                *ctx.previous_clarification_questions[-4:],
                clarification_question,
            ]

        ctx.last_updated_at = datetime.now(timezone.utc)
        return ctx

    def record_audit_log(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        session_id: str,
        action: str,
        target_type: str,
        target_id: str,
        actor_user_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLogRecord:
        """Record an immutable audit entry for important tool actions."""
        record = AuditLogRecord(
            id=uuid4(),
            organization_id=organization_id,
            business_id=business_id,
            session_id=session_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
        )
        self._audit_logs.append(record)
        return record

    def list_audit_logs(self, organization_id: UUID) -> List[AuditLogRecord]:
        """Return audit logs scoped strictly to `organization_id`."""
        return [
            log for log in self._audit_logs if log.organization_id == organization_id
        ]

    def save_summary_record(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        session_id: str,
        primary_intent: AgentIntent,
        detected_language: LanguageCode,
        redacted_summary: str,
        booking_preferences: Dict[str, str],
        persist_enabled: bool = True,
    ) -> Optional[UUID]:
        """Save privacy-redacted conversation summary scoped to `(organization_id, business_id)`."""
        ctx = self._contexts.get(session_id.strip())
        if ctx is not None:
            if ctx.organization_id != organization_id or ctx.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session context isolation violation.",
                )
            ctx.conversation_summary = redacted_summary
            ctx.last_updated_at = datetime.now(timezone.utc)

        if not persist_enabled:
            return None

        summary_id = uuid4()
        key = f"{organization_id}:{business_id}:{session_id}"
        self._saved_summaries[key] = {
            "id": summary_id,
            "organization_id": organization_id,
            "business_id": business_id,
            "session_id": session_id,
            "primary_intent": primary_intent.value,
            "detected_language": detected_language.value,
            "summary_text": redacted_summary,
            "booking_preferences": dict(booking_preferences),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return summary_id

    def save_escalation_record(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        session_id: str,
        escalation_reference: str,
        reason: str,
        summary: str,
        urgency: str,
        preferred_method: str,
        contact_name: Optional[str],
    ) -> Dict[str, Any]:
        """Save a controlled human escalation record and update session context."""
        ctx = self._contexts.get(session_id.strip())
        if ctx is not None:
            if ctx.organization_id != organization_id or ctx.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session context isolation violation.",
                )
            ctx.escalated = True
            ctx.escalation_reference = escalation_reference
            ctx.escalation_status = "pending_human_review"
            ctx.last_updated_at = datetime.now(timezone.utc)

        record = {
            "id": str(uuid4()),
            "organization_id": str(organization_id),
            "business_id": str(business_id),
            "session_id": session_id,
            "escalation_reference": escalation_reference,
            "reason": reason,
            "summary": summary,
            "urgency": urgency,
            "status": "pending_human_review",
            "target_contact_name": contact_name,
            "target_contact_method": preferred_method,
            "notification_delivered": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._escalations[escalation_reference] = record
        return record


_context_manager = ConversationContextManager()


def get_conversation_context_manager() -> ConversationContextManager:
    """Return the shared Stage 4 ConversationContextManager singleton."""
    return _context_manager
