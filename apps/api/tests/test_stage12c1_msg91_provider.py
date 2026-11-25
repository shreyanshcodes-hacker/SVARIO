"""Stage 12C.1 — Isolated Mocked Tests for MSG91 Flow API v5 Provider Adapter.

NEVER contacts the real MSG91 API. All HTTP calls are strictly mocked or blocked.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import uuid4
import httpx
import pytest
from app.core.config import Settings
from app.modules.notifications.msg91 import Msg91SmsProvider, SmsConfigurationError
from app.modules.notifications.providers import (
    NoopSmsProvider,
    SmsProviderError,
    build_sms_provider,
)
from app.modules.notifications.schemas import (
    ReminderRecipientType,
    SmsErrorCategory,
    SmsSendRequest,
)


def _valid_msg91_settings(**overrides: Any) -> Settings:
    base: Dict[str, Any] = {
        "_env_file": None,
        "SVARIO_ENV": "test",
        "SMS_REMINDERS_ENABLED": True,
        "SMS_PROVIDER": "msg91",
        "MSG91_API_KEY": "test_mock_authkey_999",
        "MSG91_API_BASE_URL": "https://control.msg91.com/api/v5/flow",
        "MSG91_SENDER_ID": "SVARIO",
        "MSG91_DLT_ENTITY_ID": "1101234567890123456",
        "MSG91_TEMPLATE_ID_CUSTOMER_30M": "67890abcdef1234567890abc",
        "MSG91_TEMPLATE_ID_OWNER_30M": "67890abcdef1234567890def",
        "MSG91_TEMPLATE_ID_STAFF_30M": "67890abcdef1234567890fed",
    }
    base.update(overrides)
    return Settings(**base)


def _valid_customer_request(**overrides: Any) -> SmsSendRequest:
    base: Dict[str, Any] = {
        "reminder_id": uuid4(),
        "recipient_type": ReminderRecipientType.CUSTOMER,
        "recipient_phone": "+919876543210",
        "template_key": "customer_30m",
        "message_body": "Reminder: Your Basic Haircut appointment at Luxe Salon is in 30 minutes at 14:00 on 2026-12-02 with Riya. Ref: SV-SAL-1234.",
        "idempotency_key": "appt-1:customer:v1",
        "template_variables": {
            "salon_name": "Luxe Salon",
            "service_name": "Basic Haircut",
            "appointment_date": "2026-12-02",
            "start_time": "14:00",
            "staff_name": "Riya",
            "booking_reference": "SV-SAL-1234",
        },
    }
    base.update(overrides)
    return SmsSendRequest(**base)


class _MockHttpResponse:
    def __init__(self, status_code: int, json_body: Any = None, raw_text: Optional[str] = None):
        self.status_code = status_code
        self._json_body = json_body
        self._raw_text = raw_text

    def json(self) -> Any:
        if self._raw_text is not None:
            raise ValueError("Invalid JSON")
        return self._json_body


@pytest.mark.asyncio
async def test_valid_msg91_request_construction_and_success_parsing(monkeypatch, caplog):
    """Valid MSG91 Flow v5 request, authkey header, mobiles without '+', accepted status, PII-free logs."""
    captured: Dict[str, Any] = {}

    async def _mock_post(self, url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _MockHttpResponse(200, {"type": "success", "message": "346a7b8c9d0e1f2a3b4c"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)
    caplog.set_level(logging.INFO)

    provider = Msg91SmsProvider(_valid_msg91_settings())
    req = _valid_customer_request()
    res = await provider.send_sms(req)

    assert captured["url"] == "https://control.msg91.com/api/v5/flow"
    assert captured["headers"] == {
        "accept": "application/json",
        "content-type": "application/json",
        "authkey": "test_mock_authkey_999",
    }
    assert captured["json"] == {
        "template_id": "67890abcdef1234567890abc",
        "short_url": "0",
        "recipients": [
            {
                "mobiles": "919876543210",
                "salon_name": "Luxe Salon",
                "service_name": "Basic Haircut",
                "appointment_date": "2026-12-02",
                "start_time": "14:00",
                "staff_name": "Riya",
                "booking_reference": "SV-SAL-1234",
            }
        ],
    }

    assert res.provider_name == "msg91"
    assert res.provider_message_id == "346a7b8c9d0e1f2a3b4c"
    assert res.provider_status == "accepted"  # Accepted != delivered
    assert res.simulated is False

    # Verify zero secrets, phone numbers, or message bodies in logs
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "test_mock_authkey_999" not in logs
    assert "919876543210" not in logs
    assert "Basic Haircut" not in logs


@pytest.mark.asyncio
async def test_msg91_success_with_explicit_request_id_field(monkeypatch):
    async def _mock_post(self, url, headers=None, json=None):
        return _MockHttpResponse(200, {"type": "success", "request_id": "req-msg91-777"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)
    provider = Msg91SmsProvider(_valid_msg91_settings())
    res = await provider.send_sms(_valid_customer_request())
    assert res.provider_message_id == "req-msg91-777"
    assert res.provider_status == "accepted"


@pytest.mark.asyncio
async def test_missing_api_key_sender_and_dlt_fail_closed(monkeypatch):
    """Missing API key, sender ID, or DLT entity ID must fail closed with zero HTTP calls."""
    async def _forbid_http(*args, **kwargs):
        raise AssertionError("HTTP must not be called when configuration is invalid!")

    monkeypatch.setattr(httpx.AsyncClient, "post", _forbid_http)

    # 1. Missing API key
    s_no_key = _valid_msg91_settings(MSG91_API_KEY=None)
    with pytest.raises(SmsConfigurationError):
        build_sms_provider(s_no_key)
    with pytest.raises(SmsProviderError) as exc_key:
        await Msg91SmsProvider(s_no_key).send_sms(_valid_customer_request())
    assert exc_key.value.category == SmsErrorCategory.PERMANENT

    # 2. Missing / invalid sender ID
    s_bad_sender = _valid_msg91_settings(MSG91_SENDER_ID="BAD")
    with pytest.raises(SmsConfigurationError):
        build_sms_provider(s_bad_sender)
    with pytest.raises(SmsProviderError) as exc_sender:
        await Msg91SmsProvider(s_bad_sender).send_sms(_valid_customer_request())
    assert exc_sender.value.category == SmsErrorCategory.PERMANENT

    # 3. Missing / invalid DLT Entity ID
    s_no_dlt = _valid_msg91_settings(MSG91_DLT_ENTITY_ID=None)
    with pytest.raises(SmsConfigurationError):
        build_sms_provider(s_no_dlt)
    with pytest.raises(SmsProviderError) as exc_dlt:
        await Msg91SmsProvider(s_no_dlt).send_sms(_valid_customer_request())
    assert exc_dlt.value.category == SmsErrorCategory.PERMANENT


@pytest.mark.asyncio
async def test_invalid_phone_and_template_configuration_rejected_before_http(monkeypatch):
    """Invalid phone, missing template ID, unsupported template key, and oversized DLT vars fail closed."""
    async def _forbid_http(*args, **kwargs):
        raise AssertionError("HTTP must not be called on pre-send validation failure!")

    monkeypatch.setattr(httpx.AsyncClient, "post", _forbid_http)

    provider = Msg91SmsProvider(_valid_msg91_settings())

    # Invalid phone
    with pytest.raises(SmsProviderError) as exc_phone:
        await provider.send_sms(_valid_customer_request(recipient_phone="not-a-phone"))
    assert exc_phone.value.category == SmsErrorCategory.PERMANENT
    assert exc_phone.value.error_code == "msg91_invalid_phone"

    # Missing approved template ID for owner_30m
    provider_no_owner_tpl = Msg91SmsProvider(_valid_msg91_settings(MSG91_TEMPLATE_ID_OWNER_30M=None))
    with pytest.raises(SmsProviderError) as exc_tpl:
        await provider_no_owner_tpl.send_sms(_valid_customer_request(template_key="owner_30m"))
    assert exc_tpl.value.category == SmsErrorCategory.PERMANENT
    assert exc_tpl.value.error_code == "msg91_template_not_configured"

    # Unsupported template key
    with pytest.raises(SmsProviderError) as exc_unsup:
        await provider.send_sms(_valid_customer_request(template_key="promo_blast"))
    assert exc_unsup.value.category == SmsErrorCategory.PERMANENT

    # Oversized DLT variable (> 30 chars)
    bad_vars = dict(_valid_customer_request().template_variables)
    bad_vars["service_name"] = "A" * 35
    with pytest.raises(SmsProviderError) as exc_len:
        await provider.send_sms(_valid_customer_request(template_variables=bad_vars))
    assert exc_len.value.category == SmsErrorCategory.PERMANENT
    assert exc_len.value.error_code == "msg91_template_variable_too_long"


@pytest.mark.asyncio
async def test_retryable_vs_permanent_provider_errors(monkeypatch):
    """HTTP 429/503 are TRANSIENT; HTTP 401 and HTTP 200 type=error are PERMANENT."""
    provider = Msg91SmsProvider(_valid_msg91_settings())

    # HTTP 429 -> TRANSIENT
    async def _mock_429(self, url, headers=None, json=None):
        return _MockHttpResponse(429, {"type": "error", "message": "rate limit"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_429)
    with pytest.raises(SmsProviderError) as exc_429:
        await provider.send_sms(_valid_customer_request())
    assert exc_429.value.category == SmsErrorCategory.TRANSIENT

    # HTTP 503 -> TRANSIENT
    async def _mock_503(self, url, headers=None, json=None):
        return _MockHttpResponse(503, raw_text="Service Unavailable")

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_503)
    with pytest.raises(SmsProviderError) as exc_503:
        await provider.send_sms(_valid_customer_request())
    assert exc_503.value.category == SmsErrorCategory.TRANSIENT

    # HTTP 401 -> PERMANENT
    async def _mock_401(self, url, headers=None, json=None):
        return _MockHttpResponse(401, {"type": "error", "code": "401", "message": "Invalid authkey"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_401)
    with pytest.raises(SmsProviderError) as exc_401:
        await provider.send_sms(_valid_customer_request())
    assert exc_401.value.category == SmsErrorCategory.PERMANENT

    # MSG91 quirk: HTTP 200 with {"type": "error", "code": "203"} -> PERMANENT
    async def _mock_200_error(self, url, headers=None, json=None):
        return _MockHttpResponse(200, {"type": "error", "code": "203", "message": "Invalid sender ID"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_200_error)
    with pytest.raises(SmsProviderError) as exc_200_err:
        await provider.send_sms(_valid_customer_request())
    assert exc_200_err.value.category == SmsErrorCategory.PERMANENT
    assert exc_200_err.value.error_code == "msg91_error_203"


@pytest.mark.asyncio
async def test_connect_timeout_vs_read_timeout_and_malformed_responses(monkeypatch):
    """ConnectTimeout -> TRANSIENT; ReadTimeout & malformed 200 -> AMBIGUOUS_TIMEOUT."""
    provider = Msg91SmsProvider(_valid_msg91_settings())

    # ConnectTimeout -> TRANSIENT
    async def _mock_connect_timeout(self, url, headers=None, json=None):
        raise httpx.ConnectTimeout("connect timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_connect_timeout)
    with pytest.raises(SmsProviderError) as exc_ct:
        await provider.send_sms(_valid_customer_request())
    assert exc_ct.value.category == SmsErrorCategory.TRANSIENT

    # ReadTimeout -> AMBIGUOUS_TIMEOUT (never retried)
    async def _mock_read_timeout(self, url, headers=None, json=None):
        raise httpx.ReadTimeout("read timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_read_timeout)
    with pytest.raises(SmsProviderError) as exc_rt:
        await provider.send_sms(_valid_customer_request())
    assert exc_rt.value.category == SmsErrorCategory.AMBIGUOUS_TIMEOUT

    # Malformed non-JSON on HTTP 200 -> AMBIGUOUS_TIMEOUT
    async def _mock_bad_json(self, url, headers=None, json=None):
        return _MockHttpResponse(200, raw_text="<html>not json</html>")

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_bad_json)
    with pytest.raises(SmsProviderError) as exc_bad:
        await provider.send_sms(_valid_customer_request())
    assert exc_bad.value.category == SmsErrorCategory.AMBIGUOUS_TIMEOUT

    # HTTP 200 with type=success but missing request ID -> AMBIGUOUS_TIMEOUT
    async def _mock_missing_id(self, url, headers=None, json=None):
        return _MockHttpResponse(200, {"type": "success"})

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_missing_id)
    with pytest.raises(SmsProviderError) as exc_mid:
        await provider.send_sms(_valid_customer_request())
    assert exc_mid.value.category == SmsErrorCategory.AMBIGUOUS_TIMEOUT


@pytest.mark.asyncio
async def test_provider_selection_defaults_disabled_and_fail_closed(monkeypatch):
    """Disabled SMS never instantiates MSG91; noop makes 0 HTTP calls; invalid provider fails closed."""
    async def _forbid_http(*args, **kwargs):
        raise AssertionError("No HTTP requests allowed!")

    monkeypatch.setattr(httpx.AsyncClient, "post", _forbid_http)

    # Defaults unchanged
    defaults = Settings(_env_file=None)
    assert defaults.sms_reminders_enabled is False
    assert defaults.sms_provider == "noop"

    # SMS_PROVIDER=msg91 with SMS_REMINDERS_ENABLED=False does NOT instantiate MSG91 or fail on missing creds
    disabled_msg91 = Settings(_env_file=None, SMS_REMINDERS_ENABLED=False, SMS_PROVIDER="msg91")
    selected = build_sms_provider(disabled_msg91)
    assert isinstance(selected, NoopSmsProvider)

    # noop provider makes zero HTTP calls
    noop = build_sms_provider(Settings(_env_file=None, SMS_REMINDERS_ENABLED=True, SMS_PROVIDER="noop"))
    assert isinstance(noop, NoopSmsProvider)
    res = await noop.send_sms(_valid_customer_request())
    assert res.simulated is True

    # Invalid provider name fails closed
    with pytest.raises(SmsConfigurationError):
        build_sms_provider(Settings(_env_file=None, SMS_REMINDERS_ENABLED=True, SMS_PROVIDER="unknown_gw"))
    with pytest.raises(SmsConfigurationError):
        build_sms_provider(Settings(_env_file=None, SMS_REMINDERS_ENABLED=False, SMS_PROVIDER="unknown_gw"))
