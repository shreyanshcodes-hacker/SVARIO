"""Stage 3B-1 Tests — Structural Protocols, Rate-Limiter Memory-Leak Fixes & Concurrency."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.agents.context import ConversationContextManager
from app.core.state_protocols import (
    ContextStoreProtocol,
    PolicyRegistryProtocol,
    PublicSessionStoreProtocol,
    RateLimiterProtocol,
)
from app.modules.voice.public_access import PublicVoicePolicyRegistry
from app.modules.voice.rate_limit import VoiceSessionRateLimiter
from app.modules.websites.public_voice import (
    PublicWebsiteVoiceSessionStore,
    _BoundPublicVoiceSession,
)
from app.modules.websites.service import PublicWebsiteRateLimiter


# =============================================================================
# 1. Structural Protocol Compatibility
# =============================================================================


def test_stage3b1_protocol_structural_compatibility() -> None:
    session_store = PublicWebsiteVoiceSessionStore()
    policy_registry = PublicVoicePolicyRegistry()
    context_manager = ConversationContextManager()
    website_limiter = PublicWebsiteRateLimiter()
    voice_limiter = VoiceSessionRateLimiter()

    assert isinstance(session_store, PublicSessionStoreProtocol)
    assert isinstance(policy_registry, PolicyRegistryProtocol)
    assert isinstance(context_manager, ContextStoreProtocol)
    assert isinstance(website_limiter, RateLimiterProtocol)
    assert isinstance(voice_limiter, RateLimiterProtocol)


# =============================================================================
# 2. Memory-Leak Fixes: Empty Key Deletion, Stale Sweep & Active Preservation
# =============================================================================


def test_public_website_limiter_prunes_expired_keys_and_preserves_active_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 1000.0
    monkeypatch.setattr("app.modules.websites.service.time.monotonic", lambda: now)

    limiter = PublicWebsiteRateLimiter(
        max_requests=3,
        window_seconds=60,
        max_tracked_keys=50,
    )

    # One-off IPs at t=1000
    for i in range(25):
        limiter.check(f"198.51.100.{i}")
    assert len(limiter._hits) == 25

    # Advance 40s: active client hits twice at t=1040 (within 60s of 1040, old IPs expire at 1060+)
    now = 1040.0
    limiter.check("203.0.113.10")
    limiter.check("203.0.113.10")

    # Advance to t=1065: old 25 IPs from t=1000 are expired, but 203.0.113.10 (at t=1040) is STILL active
    now = 1065.0
    limiter.check("203.0.113.99")  # triggers sweep because (1065 - 1000) >= 60

    # All 25 expired one-off IPs must be deleted
    for i in range(25):
        assert f"198.51.100.{i}" not in limiter._hits

    # Active client 203.0.113.10 must STILL be preserved with its 2 active hits!
    assert "203.0.113.10" in limiter._hits
    assert len(limiter._hits["203.0.113.10"]) == 2

    # 3rd hit for active client succeeds; 4th hit triggers 429 (active window was NOT reset)
    limiter.check("203.0.113.10")
    with pytest.raises(HTTPException) as exc:
        limiter.check("203.0.113.10")
    assert exc.value.status_code == 429


def test_voice_limiter_prunes_expired_keys_and_bounds_one_off_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 2000.0
    monkeypatch.setattr("app.modules.voice.rate_limit.time.monotonic", lambda: now)

    limiter = VoiceSessionRateLimiter(window_seconds=60, max_tracked_keys=40)

    # Burst of 200 distinct one-off actors within the same window -> bounded <= 40
    for i in range(200):
        limiter.check_and_record(f"ip:192.0.2.{i}", max_requests_per_window=5)
    assert len(limiter._buckets) <= 40

    # Add an active actor at t=2040
    now = 2040.0
    limiter.check_and_record("ip:active-client", max_requests_per_window=2)

    # Advance past earlier window (t=2065) -> earlier keys purged, active-client preserved
    now = 2065.0
    limiter.check_and_record("ip:trigger-sweep", max_requests_per_window=2)
    assert "ip:active-client" in limiter._buckets
    assert len(limiter._buckets["ip:active-client"]) == 1

    # 2nd call succeeds, 3rd call raises 429 with Retry-After
    limiter.check_and_record("ip:active-client", max_requests_per_window=2)
    with pytest.raises(HTTPException) as exc:
        limiter.check_and_record("ip:active-client", max_requests_per_window=2)
    assert exc.value.status_code == 429
    assert "Retry-After" in (exc.value.headers or {})

    # Advance past active-client's window (t=2101) -> allowed again
    now = 2101.0
    limiter.check_and_record("ip:active-client", max_requests_per_window=2)


def test_public_website_limiter_bounds_large_number_of_one_off_ips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 5000.0
    monkeypatch.setattr("app.modules.websites.service.time.monotonic", lambda: now)

    limiter = PublicWebsiteRateLimiter(
        max_requests=60,
        window_seconds=60,
        max_tracked_keys=50,
    )
    for i in range(500):
        limiter.check(f"198.51.{i // 256}.{i % 256}")

    assert len(limiter._hits) <= 50


# =============================================================================
# 3. Concurrency Safety (Same Client & Distinct Clients)
# =============================================================================


def test_concurrent_same_client_cannot_bypass_rate_limit() -> None:
    website_limiter = PublicWebsiteRateLimiter(max_requests=5, window_seconds=60)
    voice_limiter = VoiceSessionRateLimiter(window_seconds=60)

    def _hit_website(_: int) -> int:
        try:
            website_limiter.check("203.0.113.55")
            return 200
        except HTTPException as exc:
            return exc.status_code

    def _hit_voice(_: int) -> int:
        try:
            voice_limiter.check_and_record("ip:203.0.113.55", max_requests_per_window=5)
            return 201
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=16) as pool:
        web_results = list(pool.map(_hit_website, range(25)))
        voice_results = list(pool.map(_hit_voice, range(25)))

    assert web_results.count(200) == 5
    assert web_results.count(429) == 20
    assert voice_results.count(201) == 5
    assert voice_results.count(429) == 20


def test_concurrent_different_clients_do_not_interfere() -> None:
    limiter = PublicWebsiteRateLimiter(max_requests=3, window_seconds=60)

    def _hit_client(client_idx: int) -> int:
        ip = f"198.51.100.{client_idx}"
        ok = 0
        for _ in range(3):
            limiter.check(ip)
            ok += 1
        return ok

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(_hit_client, range(20)))

    assert all(r == 3 for r in results)


# =============================================================================
# 4. Existing Session Store & Policy Registry Behavior Preserved
# =============================================================================


def test_session_store_and_policy_registry_behavior_preserved() -> None:
    store = PublicWebsiteVoiceSessionStore()
    org_id = uuid4()
    biz_id = uuid4()
    rec = _BoundPublicVoiceSession(
        slug="riya-salon",
        session_id="sess_123",
        organization_id=org_id,
        business_id=biz_id,
        internal_public_token="tok_internal",
        has_persistent_db_access=False,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    store.put("visitor_tok_abc", rec)

    verified = store.verify(token="visitor_tok_abc", slug="riya-salon", session_id="sess_123")
    assert verified.organization_id == org_id
    assert verified.business_id == biz_id

    with pytest.raises(HTTPException) as bad_slug:
        store.verify(token="visitor_tok_abc", slug="other-salon", session_id="sess_123")
    assert bad_slug.value.status_code == 403
