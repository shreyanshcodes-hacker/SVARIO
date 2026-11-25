"""Stage 12C.1: Production-ready MSG91 Flow API v5 SMS Provider Adapter.

Official MSG91 Flow API v5 contract verified against https://docs.msg91.com:
- Endpoint: `POST https://control.msg91.com/api/v5/flow`
- Headers:
  * `accept: application/json`
  * `content-type: application/json`
  * `authkey: <MSG91_API_KEY>`
- Request JSON:
  ```json
  {
    "template_id": "<approved_msg91_flow_id>",
    "short_url": "0",
    "recipients": [
      {"mobiles": "919898989898", "salon_name": "...", ...}
    ]
  }
  ```
- Response JSON:
  * Accepted: `{"type": "success", "message": "<request_id>"}` (or `"request_id": "..."`)
    Note: HTTP 200 + `type == "success"` means MSG91 accepted the request into its queue;
    it does NOT mean carrier delivery (`delivered` requires Stage 12C.2 DLR webhooks).
  * Error: HTTP 4xx/5xx OR HTTP 200 with `{"type": "error", "message": "..."}`.

Security & Privacy Guarantees:
- Never hardcodes credentials, sender headers, or DLT identifiers.
- Never logs API keys, authorization headers, phone numbers, message bodies, or raw responses.
- Fails closed on missing/invalid DLT configuration, template IDs, or phone numbers.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Mapping, Optional
import httpx
from app.core.config import Settings
from app.modules.notifications.providers import (
    SmsProviderError,
    classify_transport_error,
)
from app.modules.notifications.schemas import (
    SmsErrorCategory,
    SmsSendRequest,
    SmsSendResult,
    normalize_e164_phone,
)

logger = logging.getLogger("svario.notifications.msg91")

_SENDER_ID_REGEX = re.compile(r"^[A-Za-z0-9]{6}$")
_DLT_ENTITY_ID_REGEX = re.compile(r"^[0-9]{10,30}$")
_TEMPLATE_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
_CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x1f\x7f]")

_MAX_DLT_VAR_LEN = 30
_MAX_MESSAGE_LEN = 320

_REQUIRED_VARS_BY_TEMPLATE: Dict[str, tuple[str, ...]] = {
    "customer_30m": (
        "salon_name",
        "service_name",
        "appointment_date",
        "start_time",
        "staff_name",
        "booking_reference",
    ),
    "owner_30m": (
        "salon_name",
        "service_name",
        "appointment_date",
        "start_time",
        "customer_name",
        "staff_name",
        "booking_reference",
    ),
    "staff_30m": (
        "salon_name",
        "service_name",
        "appointment_date",
        "start_time",
        "customer_name",
        "booking_reference",
    ),
}


class SmsConfigurationError(ValueError):
    """Raised when SMS provider configuration is invalid or incomplete (fail-closed)."""


class Msg91SmsProvider:
    """Async MSG91 Flow API v5 adapter conforming to `SmsProviderProtocol`."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = (settings.msg91_api_key or "").strip()
        self._endpoint = (settings.msg91_api_base_url or "").strip().rstrip("/")
        self._sender_id = (settings.msg91_sender_id or "").strip()
        self._dlt_entity_id = (settings.msg91_dlt_entity_id or "").strip()
        self._default_country_code = settings.sms_default_country_code
        self._template_map: Dict[str, str] = {}
        if settings.msg91_template_id_customer_30m:
            self._template_map["customer_30m"] = settings.msg91_template_id_customer_30m.strip()
        if settings.msg91_template_id_owner_30m:
            self._template_map["owner_30m"] = settings.msg91_template_id_owner_30m.strip()
        if settings.msg91_template_id_staff_30m:
            self._template_map["staff_30m"] = settings.msg91_template_id_staff_30m.strip()

        self._timeout = httpx.Timeout(
            connect=settings.msg91_connect_timeout_seconds,
            read=settings.msg91_read_timeout_seconds,
            write=settings.msg91_write_timeout_seconds,
            pool=settings.msg91_connect_timeout_seconds,
        )

    @property
    def provider_name(self) -> str:
        return "msg91"

    def validate_base_configuration(self) -> None:
        """Fail-closed validation of core MSG91 credentials and DLT identity."""
        if not self._api_key or "placeholder" in self._api_key.lower():
            raise SmsConfigurationError("MSG91_API_KEY is missing or invalid.")
        if not self._endpoint or not self._endpoint.startswith("https://"):
            raise SmsConfigurationError("MSG91_API_BASE_URL must be a valid HTTPS URL.")
        if not self._sender_id or not _SENDER_ID_REGEX.match(self._sender_id):
            raise SmsConfigurationError(
                "MSG91_SENDER_ID must be a valid 6-character alphanumeric DLT header."
            )
        if not self._dlt_entity_id or not _DLT_ENTITY_ID_REGEX.match(self._dlt_entity_id):
            raise SmsConfigurationError(
                "MSG91_DLT_ENTITY_ID must be a valid numeric DLT Entity/PE ID."
            )

    def _validate_and_build_payload(self, request: SmsSendRequest) -> Dict[str, Any]:
        """Validate configuration, DLT template, phone, and variables before HTTP submission."""
        try:
            self.validate_base_configuration()
        except SmsConfigurationError as exc:
            raise SmsProviderError(
                str(exc),
                category=SmsErrorCategory.PERMANENT,
                error_code="msg91_invalid_configuration",
            ) from exc

        template_key = (request.template_key or "").strip()
        if template_key not in _REQUIRED_VARS_BY_TEMPLATE:
            raise SmsProviderError(
                "Unsupported SMS reminder template key.",
                category=SmsErrorCategory.PERMANENT,
                error_code="msg91_unsupported_template_key",
            )

        approved_template_id = self._template_map.get(template_key, "")
        if not approved_template_id or not _TEMPLATE_ID_REGEX.match(approved_template_id):
            raise SmsProviderError(
                "Approved MSG91 DLT template ID is missing or malformed.",
                category=SmsErrorCategory.PERMANENT,
                error_code="msg91_template_not_configured",
            )

        normalized_e164 = normalize_e164_phone(
            request.recipient_phone,
            default_country_code=self._default_country_code,
        )
        if not normalized_e164:
            raise SmsProviderError(
                "Recipient phone number is not valid E.164.",
                category=SmsErrorCategory.PERMANENT,
                error_code="msg91_invalid_phone",
            )
        # MSG91 Flow API v5 expects country code + subscriber digits without leading `+`
        msg91_mobile = normalized_e164.lstrip("+")

        if not request.message_body or len(request.message_body) > _MAX_MESSAGE_LEN:
            raise SmsProviderError(
                "Rendered SMS message body is empty or exceeds maximum length.",
                category=SmsErrorCategory.PERMANENT,
                error_code="msg91_invalid_message_length",
            )

        required_vars = _REQUIRED_VARS_BY_TEMPLATE[template_key]
        recipient_entry: Dict[str, str] = {"mobiles": msg91_mobile}
        for var_name in required_vars:
            raw_val = request.template_variables.get(var_name)
            if raw_val is None or not str(raw_val).strip():
                raise SmsProviderError(
                    f"Required DLT template variable '{var_name}' is missing.",
                    category=SmsErrorCategory.PERMANENT,
                    error_code="msg91_missing_template_variable",
                )
            cleaned_val = str(raw_val).strip()
            if _CONTROL_CHAR_REGEX.search(cleaned_val):
                raise SmsProviderError(
                    f"DLT template variable '{var_name}' contains invalid control characters.",
                    category=SmsErrorCategory.PERMANENT,
                    error_code="msg91_invalid_template_variable",
                )
            if len(cleaned_val) > _MAX_DLT_VAR_LEN:
                raise SmsProviderError(
                    f"DLT template variable '{var_name}' exceeds {_MAX_DLT_VAR_LEN} characters.",
                    category=SmsErrorCategory.PERMANENT,
                    error_code="msg91_template_variable_too_long",
                )
            recipient_entry[var_name] = cleaned_val

        return {
            "template_id": approved_template_id,
            "short_url": "0",
            "recipients": [recipient_entry],
        }

    @staticmethod
    def _parse_response(status_code: int, body: Any) -> SmsSendResult:
        """Validate HTTP status + MSG91 JSON envelope (handling HTTP 200 error bodies)."""
        # Explicit retryable HTTP statuses
        if status_code == 429:
            raise SmsProviderError(
                "MSG91 rate limit exceeded.",
                category=SmsErrorCategory.TRANSIENT,
                error_code="msg91_rate_limited",
            )
        if 500 <= status_code <= 599:
            raise SmsProviderError(
                f"MSG91 server error (HTTP {status_code}).",
                category=SmsErrorCategory.TRANSIENT,
                error_code=f"msg91_http_{status_code}",
            )

        # Explicit permanent client/auth/DLT HTTP errors
        if 400 <= status_code <= 499:
            code_suffix = str(body.get("code")) if isinstance(body, Mapping) and body.get("code") else str(status_code)
            raise SmsProviderError(
                f"MSG91 rejected request (HTTP {status_code}).",
                category=SmsErrorCategory.PERMANENT,
                error_code=f"msg91_rejected_{code_suffix}",
            )

        # 2xx status: must strictly validate JSON body (`type == "success"` + non-empty ID)
        if not isinstance(body, Mapping):
            raise SmsProviderError(
                "MSG91 returned non-object response body.",
                category=SmsErrorCategory.AMBIGUOUS_TIMEOUT,
                error_code="msg91_malformed_response",
            )

        resp_type = str(body.get("type") or "").strip().lower()
        if resp_type == "error":
            err_code = str(body.get("code") or "api_error").strip()
            raise SmsProviderError(
                "MSG91 returned error response.",
                category=SmsErrorCategory.PERMANENT,
                error_code=f"msg91_error_{err_code}",
            )

        if resp_type != "success":
            raise SmsProviderError(
                "MSG91 returned unrecognized response type.",
                category=SmsErrorCategory.AMBIGUOUS_TIMEOUT,
                error_code="msg91_malformed_response",
            )

        # MSG91 Flow v5 returns the queued request ID in `request_id` or `message`
        raw_id = body.get("request_id") or body.get("message")
        provider_msg_id = str(raw_id).strip() if raw_id is not None else ""
        if not provider_msg_id:
            raise SmsProviderError(
                "MSG91 success response missing request identifier.",
                category=SmsErrorCategory.AMBIGUOUS_TIMEOUT,
                error_code="msg91_missing_request_id",
            )

        return SmsSendResult(
            provider_name="msg91",
            provider_message_id=provider_msg_id,
            provider_status="accepted",
            simulated=False,
        )

    async def send_sms(self, request: SmsSendRequest) -> SmsSendResult:
        """Submit a validated transactional SMS reminder to MSG91 Flow API v5."""
        payload = self._validate_and_build_payload(request)
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authkey": self._api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload,
                )
        except Exception as exc:
            category = classify_transport_error(exc)
            error_code = (
                "msg91_connect_error"
                if category == SmsErrorCategory.TRANSIENT
                else "msg91_timeout_ambiguous"
            )
            logger.warning(
                "msg91_transport_error reminder_id=%s category=%s error_code=%s",
                request.reminder_id,
                category.value,
                error_code,
            )
            raise SmsProviderError(
                "MSG91 transport failure.",
                category=category,
                error_code=error_code,
            ) from exc

        try:
            parsed_body = resp.json()
        except Exception as exc:
            if 500 <= resp.status_code <= 599:
                raise SmsProviderError(
                    f"MSG91 server error (HTTP {resp.status_code}).",
                    category=SmsErrorCategory.TRANSIENT,
                    error_code=f"msg91_http_{resp.status_code}",
                ) from exc
            if 400 <= resp.status_code <= 499:
                raise SmsProviderError(
                    f"MSG91 rejected request (HTTP {resp.status_code}).",
                    category=SmsErrorCategory.PERMANENT,
                    error_code=f"msg91_http_{resp.status_code}",
                ) from exc
            raise SmsProviderError(
                "MSG91 returned invalid JSON.",
                category=SmsErrorCategory.AMBIGUOUS_TIMEOUT,
                error_code="msg91_malformed_response",
            ) from exc

        result = self._parse_response(resp.status_code, parsed_body)
        logger.info(
            "msg91_request_accepted reminder_id=%s recipient=%s template=%s",
            request.reminder_id,
            request.recipient_type.value,
            request.template_key,
        )
        return result
