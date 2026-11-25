"""Structural protocols for Stage 3B-1 state stores, rate limiters, and policy registries."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class RateLimiterProtocol(Protocol):
    """Structural protocol satisfied by both public website and voice rate limiters."""

    def check_and_record(self, actor_key: str, max_requests_per_window: int) -> None: ...


@runtime_checkable
class PublicSessionStoreProtocol(Protocol):
    """Structural protocol for public website visitor voice session stores."""

    def clear(self) -> None: ...

    def put(self, token: str, record: Any) -> None: ...

    def verify(self, *, token: str, slug: str, session_id: str) -> Any: ...


@runtime_checkable
class PolicyRegistryProtocol(Protocol):
    """Structural protocol for public voice policy bundle registries."""

    def clear(self) -> None: ...

    def register_bundle(self, bundle: Any) -> None: ...

    def get_bundle(self, organization_id: UUID, business_id: UUID) -> Optional[Any]: ...


@runtime_checkable
class ContextStoreProtocol(Protocol):
    """Structural protocol for session-scoped conversation context managers."""

    def clear(self) -> None: ...

    def initialize_session(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: Any,
        initial_language: Any = ...,
    ) -> Any: ...

    def get_or_create_context(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: Any,
        initial_language: Any = ...,
    ) -> Any: ...

    def start_new_turn(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        industry: Any,
        user_query: str,
    ) -> Any: ...

    def record_tool_call(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        max_tool_calls_per_turn: int = 3,
    ) -> Any: ...

    def update_from_intent(
        self,
        *,
        session_id: str,
        organization_id: UUID,
        business_id: UUID,
        intent: Any,
        confidence: float,
        detected_language: Any,
        entities: Dict[str, Any],
        clarification_question: Optional[str] = None,
    ) -> Any: ...

    def save_summary_record(
        self,
        *,
        organization_id: UUID,
        business_id: UUID,
        session_id: str,
        primary_intent: Any,
        detected_language: Any,
        redacted_summary: str,
        booking_preferences: Dict[str, str],
        persist_enabled: bool = True,
    ) -> Optional[UUID]: ...

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
    ) -> Dict[str, Any]: ...

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
    ) -> Any: ...
