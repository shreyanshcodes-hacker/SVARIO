"""Phase 4E — Session-Scoped, Tenant-Isolated Conversation Context & Privacy Redaction.

Security & Privacy Guarantees:
- Never mixes context across sessions, businesses, or organizations.
- Rejects any access to a `session_id` if `(organization_id, business_id)` does not
  match the session's bound owner (`403 Forbidden`).
- Redacts unnecessary PII and clinical symptom disclosures from summaries.
- Never stores raw audio or patient medical histories.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from fastapi import Depends, HTTPException, status
from app.agents.schemas import (
    AgentIntent,
    AuditLogRecord,
    SessionConversationContext,
)
from app.core.config import Settings, get_settings
from app.core.redis_provider import (
    RedisClientProtocol,
    RedisUnavailableError,
    get_redis_client,
    raise_redis_unavailable,
)
from app.core.state_protocols import ContextStoreProtocol
from app.modules.onboarding.schemas import LanguageCode
from app.modules.organizations.schemas import OrganizationIndustry

logger = logging.getLogger("svario.agents.context")

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


_CONTEXT_TTL_SECONDS = 1800  # 30 minutes inactivity TTL

_CONTEXT_CAS_LUA = """
local current = redis.call('GET', KEYS[1])
local expected_ver = tonumber(ARGV[1])
if current then
  local ok, decoded = pcall(cjson.decode, current)
  if not ok or type(decoded) ~= 'table' or tonumber(decoded['version'] or 0) ~= expected_ver then
    return 0
  end
elseif expected_ver ~= 0 then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[3]))
return 1
""".strip()


class RedisConversationContextManager:
    """Distributed Redis-backed conversation context manager with 30-min inactivity TTL and CAS."""

    def __init__(
        self,
        redis_client: RedisClientProtocol,
        *,
        ttl_seconds: int = _CONTEXT_TTL_SECONDS,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _ctx_key(session_id: str) -> str:
        digest = hashlib.sha256(session_id.strip().encode("utf-8")).hexdigest()[:24]
        return f"svario:ctx:{digest}"

    def clear(self) -> None:
        return None

    def _load(self, session_id: str) -> Tuple[Optional[SessionConversationContext], int]:
        key = self._ctx_key(session_id)
        try:
            raw = self._redis.execute(["GET", key])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

        if not raw or not isinstance(raw, str):
            return None, 0

        try:
            envelope = json.loads(raw)
            version = int(envelope["version"])
            ctx = SessionConversationContext.model_validate(envelope["context"])
            return ctx, version
        except Exception as exc:
            logger.warning("corrupted_redis_context_detected")
            try:
                self._redis.execute(["DEL", key])
            except RedisUnavailableError:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Conversation context state could not be loaded.",
            ) from exc

    def _save_cas(
        self,
        session_id: str,
        ctx: SessionConversationContext,
        expected_version: int,
    ) -> bool:
        key = self._ctx_key(session_id)
        payload = json.dumps(
            {
                "version": expected_version + 1,
                "context": ctx.model_dump(mode="json"),
            },
            separators=(",", ":"),
        )
        try:
            res = self._redis.execute(
                [
                    "EVAL",
                    _CONTEXT_CAS_LUA,
                    1,
                    key,
                    str(expected_version),
                    payload,
                    str(self._ttl_seconds),
                ]
            )
            return int(res) == 1
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

    def _refresh_ttl(self, session_id: str) -> None:
        try:
            self._redis.execute(["EXPIRE", self._ctx_key(session_id), self._ttl_seconds])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

    def initialize_session(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: OrganizationIndustry,
        initial_language: LanguageCode = LanguageCode.ENGLISH,
    ) -> SessionConversationContext:
        cleaned_sid = session_id.strip()
        created = SessionConversationContext(
            session_id=cleaned_sid,
            organization_id=organization_id,
            business_id=business_id,
            industry=industry,
            detected_language=initial_language,
            last_updated_at=datetime.now(timezone.utc),
        )
        self._save_cas(cleaned_sid, created, 0)
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
        cleaned_sid = session_id.strip()
        existing, _ = self._load(cleaned_sid)
        if existing is not None:
            if existing.organization_id != organization_id or existing.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Session context isolation violation: session_id is bound to a "
                        "different organization or business."
                    ),
                )
            self._refresh_ttl(cleaned_sid)
            return existing

        created = SessionConversationContext(
            session_id=cleaned_sid,
            organization_id=organization_id,
            business_id=business_id,
            industry=industry,
            detected_language=initial_language,
            last_updated_at=datetime.now(timezone.utc),
        )
        if not self._save_cas(cleaned_sid, created, 0):
            reread, _ = self._load(cleaned_sid)
            if reread is not None:
                if reread.organization_id != organization_id or reread.business_id != business_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Session context isolation violation.",
                    )
                return reread
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
        cleaned_sid = session_id.strip()
        for _ in range(6):
            ctx, ver = self._load(cleaned_sid)
            if ctx is None:
                ctx = SessionConversationContext(
                    session_id=cleaned_sid,
                    organization_id=organization_id,
                    business_id=business_id,
                    industry=industry,
                    detected_language=LanguageCode.ENGLISH,
                    last_updated_at=datetime.now(timezone.utc),
                )
                ver = 0
            elif ctx.organization_id != organization_id or ctx.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session context isolation violation.",
                )
            ctx.turn_count += 1
            ctx.tool_calls_in_current_turn = 0
            normalized_q = user_query.strip().lower()[:200]
            if normalized_q:
                ctx.recent_user_queries = [*ctx.recent_user_queries[-4:], normalized_q]
            ctx.last_updated_at = datetime.now(timezone.utc)
            if self._save_cas(cleaned_sid, ctx, ver):
                return ctx
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrent session update conflict. Please retry.",
        )

    def record_tool_call(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        max_tool_calls_per_turn: int = 3,
    ) -> SessionConversationContext:
        cleaned_sid = session_id.strip()
        for _ in range(3):
            ctx, ver = self._load(cleaned_sid)
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
            if self._save_cas(cleaned_sid, ctx, ver):
                return ctx
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrent session update conflict. Please retry.",
        )

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
        cleaned_sid = session_id.strip()
        for _ in range(3):
            ctx, ver = self._load(cleaned_sid)
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
            ctx.current_intent = intent
            ctx.detected_language = detected_language
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
            if self._save_cas(cleaned_sid, ctx, ver):
                return ctx
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Concurrent session update conflict. Please retry.",
        )

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
        key = f"svario:ctx_audit:{hashlib.sha256(session_id.strip().encode('utf-8')).hexdigest()[:24]}"
        try:
            self._redis.execute(["RPUSH", key, record.model_dump_json()])
            self._redis.execute(["EXPIRE", key, self._ttl_seconds])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc
        return record

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
        cleaned_sid = session_id.strip()
        for _ in range(3):
            ctx, ver = self._load(cleaned_sid)
            if ctx is None:
                break
            if ctx.organization_id != organization_id or ctx.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session context isolation violation.",
                )
            ctx.conversation_summary = redacted_summary
            ctx.last_updated_at = datetime.now(timezone.utc)
            if self._save_cas(cleaned_sid, ctx, ver):
                break

        if not persist_enabled:
            return None

        summary_id = uuid4()
        key = f"svario:ctx_sum:{hashlib.sha256(cleaned_sid.encode('utf-8')).hexdigest()[:24]}"
        payload = json.dumps(
            {
                "id": str(summary_id),
                "organization_id": str(organization_id),
                "business_id": str(business_id),
                "session_id": cleaned_sid,
                "primary_intent": primary_intent.value,
                "detected_language": detected_language.value,
                "summary_text": redacted_summary,
                "booking_preferences": dict(booking_preferences),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            separators=(",", ":"),
        )
        try:
            self._redis.execute(["SET", key, payload, "EX", self._ttl_seconds])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc
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
        cleaned_sid = session_id.strip()
        for _ in range(3):
            ctx, ver = self._load(cleaned_sid)
            if ctx is None:
                break
            if ctx.organization_id != organization_id or ctx.business_id != business_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session context isolation violation.",
                )
            ctx.escalated = True
            ctx.escalation_reference = escalation_reference
            ctx.escalation_status = "pending_human_review"
            ctx.last_updated_at = datetime.now(timezone.utc)
            if self._save_cas(cleaned_sid, ctx, ver):
                break

        record = {
            "id": str(uuid4()),
            "organization_id": str(organization_id),
            "business_id": str(business_id),
            "session_id": cleaned_sid,
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
        key = f"svario:ctx_esc:{hashlib.sha256(escalation_reference.encode('utf-8')).hexdigest()[:24]}"
        try:
            self._redis.execute(["SET", key, json.dumps(record, separators=(",", ":")), "EX", self._ttl_seconds])
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc
        return record


_context_manager = ConversationContextManager()


def get_conversation_context_manager(
    settings: Settings = Depends(get_settings),
) -> ContextStoreProtocol:
    """Return the configured conversation context store (Redis in prod, in-memory in dev/test)."""
    resolved = settings if isinstance(settings, Settings) else get_settings()
    redis_client = get_redis_client(resolved)
    if redis_client is not None:
        return RedisConversationContextManager(redis_client)
    if resolved.is_production:
        raise raise_redis_unavailable()
    return _context_manager
