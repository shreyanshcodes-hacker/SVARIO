"""Provider-independent SMS interface and Stage 12B NoopSmsProvider.

Stage 12B enforces NoopSmsProvider exclusively — zero network calls or real SMS
transmissions are permitted in this stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Protocol
from uuid import uuid4
import httpx
from app.modules.notifications.schemas import (
    SmsErrorCategory,
    SmsSendRequest,
    SmsSendResult,
)


def classify_transport_error(exc: Exception) -> SmsErrorCategory:
    """Conservatively classify HTTP transport errors for SMS gateways.

    - Pre-transmission connection failures (`ConnectTimeout`, `ConnectError`,
      `PoolTimeout`) are proven not to have sent the request -> `TRANSIENT`.
    - Post-connect read/write/protocol failures (`ReadTimeout`, `WriteTimeout`,
      `RemoteProtocolError`, `ReadError`, `WriteError`) may have already been
      accepted by the SMS provider -> `AMBIGUOUS_TIMEOUT` (never auto-retried).
    """
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ConnectError, httpx.PoolTimeout)):
        return SmsErrorCategory.TRANSIENT
    if isinstance(
        exc,
        (
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.RemoteProtocolError,
            httpx.ReadError,
            httpx.WriteError,
            TimeoutError,
        ),
    ):
        return SmsErrorCategory.AMBIGUOUS_TIMEOUT
    return SmsErrorCategory.AMBIGUOUS_TIMEOUT


class SmsProviderError(Exception):
    """Classified error raised by an SMS provider adapter."""

    def __init__(
        self,
        message: str,
        *,
        category: SmsErrorCategory,
        error_code: str = "provider_error",
    ) -> None:
        super().__init__(message)
        self.category = category
        self.error_code = error_code


class SmsProviderProtocol(Protocol):
    """Provider-agnostic SMS adapter contract (future: MSG91, Exotel, Gupshup)."""

    @property
    def provider_name(self) -> str: ...

    async def send_sms(self, request: SmsSendRequest) -> SmsSendResult: ...


@dataclass(frozen=True)
class SimulatedSmsDispatchRecord:
    """In-memory audit record of a simulated NoopSmsProvider dispatch."""

    reminder_id: str
    recipient_type: str
    template_key: str
    message_body: str
    provider_message_id: str
    dispatched_at: datetime


class NoopSmsProvider:
    """Zero-network SMS provider for Stage 12B development, staging, and tests."""

    def __init__(self) -> None:
        self._dispatched: List[SimulatedSmsDispatchRecord] = []

    @property
    def provider_name(self) -> str:
        return "noop"

    @property
    def dispatched_records(self) -> List[SimulatedSmsDispatchRecord]:
        return list(self._dispatched)

    def clear(self) -> None:
        self._dispatched.clear()

    async def send_sms(self, request: SmsSendRequest) -> SmsSendResult:
        """Simulate SMS acceptance without making any network requests."""
        msg_id = f"noop-{uuid4().hex[:12]}"
        self._dispatched.append(
            SimulatedSmsDispatchRecord(
                reminder_id=str(request.reminder_id),
                recipient_type=request.recipient_type.value,
                template_key=request.template_key,
                message_body=request.message_body,
                provider_message_id=msg_id,
                dispatched_at=datetime.now(timezone.utc),
            )
        )
        return SmsSendResult(
            provider_name=self.provider_name,
            provider_message_id=msg_id,
            provider_status="simulated_accepted",
            simulated=True,
        )


def build_sms_provider(settings: Any) -> SmsProviderProtocol:
    """Fail-closed SMS provider factory for `noop` and `msg91`.

    Rules:
    - When `SMS_REMINDERS_ENABLED` is False, NEVER instantiate `Msg91SmsProvider`;
      always return `NoopSmsProvider` so disabled mode makes zero provider calls
      and never requires live credentials.
    - When `SMS_REMINDERS_ENABLED` is True:
      * `noop` -> `NoopSmsProvider()`
      * `msg91` -> validates base MSG91/DLT config and returns `Msg91SmsProvider`
      * anything else -> fails closed with `SmsConfigurationError`
    """
    from app.modules.notifications.msg91 import Msg91SmsProvider, SmsConfigurationError

    provider_name = (getattr(settings, "sms_provider", None) or "").strip().lower()
    if provider_name not in {"noop", "msg91"}:
        raise SmsConfigurationError(
            f"Unsupported SMS_PROVIDER '{provider_name}'. Allowed values: 'noop', 'msg91'."
        )

    if not getattr(settings, "sms_reminders_enabled", False):
        return NoopSmsProvider()

    if provider_name == "noop":
        return NoopSmsProvider()

    adapter = Msg91SmsProvider(settings)
    adapter.validate_base_configuration()
    return adapter
