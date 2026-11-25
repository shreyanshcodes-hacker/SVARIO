"""Stage 3B-2 Security & Reliability Tests — Redis Provider, Sessions, Rate Limiter, Context & Policy Authority."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.agents.context import RedisConversationContextManager
from app.agents.schemas import AgentIntent
from app.core.config import Settings, get_settings
from app.core.redis_provider import (
    RedisUnavailableError,
    UpstashRestRedisClient,
    close_redis_client,
    set_redis_client_for_tests,
    validate_production_redis_config,
)
from app.main import create_app
from app.modules.onboarding.schemas import LanguageCode
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.voice.rate_limit import RedisRateLimiter
from app.modules.websites.public_voice import (
    RedisPublicSessionStore,
    _BoundPublicVoiceSession,
)


class _FakeDistributedRedis:
    """Thread-safe in-memory Redis simulator supporting GET/SET/DEL/EXPIRE/RPUSH/PING/EVAL."""

    def __init__(self, *, fail_all: bool = False) -> None:
        self._lock = threading.Lock()
        self._kv: Dict[str, Tuple[str, Optional[float]]] = {}
        self._lists: Dict[str, List[str]] = {}
        self._zsets: Dict[str, Dict[str, float]] = {}
        self._counters: Dict[str, int] = {}
        self._ttls: Dict[str, int] = {}
        self._now_ms: int = 1_700_000_000_000
        self.fail_all = fail_all

    def advance_seconds(self, seconds: int) -> None:
        with self._lock:
            self._now_ms += seconds * 1000

    def _is_expired(self, key: str) -> bool:
        entry = self._kv.get(key)
        if entry is None:
            return False
        _, exp = entry
        if exp is not None and (self._now_ms / 1000.0) >= exp:
            self._kv.pop(key, None)
            return True
        return False

    def ping(self) -> bool:
        return not self.fail_all

    def close(self) -> None:
        return None

    def execute(self, command: Sequence[Any]) -> Any:
        if self.fail_all:
            raise RedisUnavailableError("Simulated Redis outage")

        cmd = str(command[0]).upper()
        with self._lock:
            if cmd == "PING":
                return "PONG"
            if cmd == "GET":
                key = str(command[1])
                if self._is_expired(key):
                    return None
                entry = self._kv.get(key)
                return entry[0] if entry is not None else None
            if cmd == "SET":
                key = str(command[1])
                val = str(command[2])
                exp: Optional[float] = None
                if len(command) >= 5 and str(command[3]).upper() == "EX":
                    ttl = int(command[4])
                    self._ttls[key] = ttl
                    exp = (self._now_ms / 1000.0) + ttl
                self._kv[key] = (val, exp)
                return "OK"
            if cmd == "DEL":
                key = str(command[1])
                existed = 1 if key in self._kv else 0
                self._kv.pop(key, None)
                self._lists.pop(key, None)
                self._zsets.pop(key, None)
                return existed
            if cmd == "EXPIRE":
                key = str(command[1])
                ttl = int(command[2])
                self._ttls[key] = ttl
                if key in self._kv:
                    val, _ = self._kv[key]
                    self._kv[key] = (val, (self._now_ms / 1000.0) + ttl)
                return 1
            if cmd == "RPUSH":
                key = str(command[1])
                self._lists.setdefault(key, []).append(str(command[2]))
                return len(self._lists[key])
            if cmd == "EVAL":
                script = str(command[1])
                numkeys = int(command[2])
                if "ZREMRANGEBYSCORE" in script:
                    zkey = str(command[3])
                    skey = str(command[4])
                    window_ms = int(command[5]) * 1000
                    limit = int(command[6])
                    cutoff = self._now_ms - window_ms
                    zset = self._zsets.setdefault(zkey, {})
                    for member in [m for m, score in zset.items() if score <= cutoff]:
                        zset.pop(member, None)
                    if len(zset) >= limit:
                        oldest_ms = min(zset.values()) if zset else self._now_ms
                        retry = max(1, int(((oldest_ms + window_ms - self._now_ms) + 999) // 1000))
                        return [0, retry]
                    seq = self._counters.get(skey, 0) + 1
                    self._counters[skey] = seq
                    zset[f"{self._now_ms}:{seq}"] = float(self._now_ms)
                    self._ttls[zkey] = (window_ms + 1000) // 1000
                    self._ttls[skey] = (window_ms + 1000) // 1000
                    return [1, 0]
                if "cjson.decode" in script:
                    key = str(command[3])
                    expected_ver = int(command[4])
                    payload = str(command[5])
                    ttl = int(command[6])
                    self._is_expired(key)
                    cur = self._kv.get(key)
                    if cur is not None:
                        try:
                            decoded = json.loads(cur[0])
                            if int(decoded.get("version", 0)) != expected_ver:
                                return 0
                        except Exception:
                            return 0
                    elif expected_ver != 0:
                        return 0
                    self._ttls[key] = ttl
                    self._kv[key] = (payload, (self._now_ms / 1000.0) + ttl)
                    return 1
            raise AssertionError(f"Unsupported fake Redis command: {cmd}")


# =============================================================================
# 1. Redis Configuration, TLS, Timeouts, Lifecycle & Health Readiness
# =============================================================================


def test_redis_config_validation_and_lifecycle() -> None:
    # Valid Upstash HTTPS TLS
    ok_upstash = Settings(
        SVARIO_ENV="production",
        UPSTASH_REDIS_REST_URL="https://example.upstash.io",
        UPSTASH_REDIS_REST_TOKEN="upstash-secret-token-value",
    )
    validate_production_redis_config(ok_upstash)

    # Missing in production
    with pytest.raises(RuntimeError):
        validate_production_redis_config(Settings(SVARIO_ENV="production"))

    # Insecure http:// Upstash URL rejected
    with pytest.raises(RuntimeError):
        validate_production_redis_config(
            Settings(
                SVARIO_ENV="production",
                UPSTASH_REDIS_REST_URL="http://insecure.upstash.io",
                UPSTASH_REDIS_REST_TOKEN="tok",
            )
        )

    # Placeholder token rejected without leaking token value
    secret_tok = "your-placeholder-upstash-token-999"
    with pytest.raises(RuntimeError) as exc:
        validate_production_redis_config(
            Settings(
                SVARIO_ENV="production",
                UPSTASH_REDIS_REST_URL="https://example.upstash.io",
                UPSTASH_REDIS_REST_TOKEN=secret_tok,
            )
        )
    assert secret_tok not in str(exc.value)


def test_upstash_client_timeout_outage_and_readiness_check() -> None:
    def _timeout_handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    mock_http = httpx.Client(transport=httpx.MockTransport(_timeout_handler), base_url="https://example.upstash.io")
    client = UpstashRestRedisClient(
        rest_url="https://example.upstash.io",
        rest_token="super-secret-upstash-token",
        http_client=mock_http,
    )
    with pytest.raises(RedisUnavailableError) as exc:
        client.execute(["PING"])
    assert "super-secret-upstash-token" not in str(exc.value)
    assert client.ping() is False

    # Readiness check: ok vs 503
    fake = _FakeDistributedRedis()
    set_redis_client_for_tests(fake)
    try:
        app = create_app(Settings(SVARIO_ENV="development"))
        tc = TestClient(app)
        assert tc.get("/health/ready").status_code == 200
        assert tc.get("/health/ready").json()["redis"] == "ok"

        fake.fail_all = True
        r_down = tc.get("/health/ready")
        assert r_down.status_code == 503
    finally:
        set_redis_client_for_tests(None)
        close_redis_client()


# =============================================================================
# 2. Distributed Public Voice Session Store
# =============================================================================


def test_redis_session_store_cross_worker_sha256_ttl_revocation_and_outage() -> None:
    fake = _FakeDistributedRedis()
    worker_a = RedisPublicSessionStore(fake)
    worker_b = RedisPublicSessionStore(fake)

    raw_token = "raw-visitor-secret-token-xyz"
    org_id = uuid4()
    biz_id = uuid4()
    rec = _BoundPublicVoiceSession(
        slug="luxe-salon",
        session_id="sess_abc",
        organization_id=org_id,
        business_id=biz_id,
        internal_public_token="internal_tok",
        has_persistent_db_access=True,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    worker_a.put(raw_token, rec)

    # Raw token must NEVER appear in Redis keys or values
    expected_key = f"svario:pub_sess:{hashlib.sha256(raw_token.encode()).hexdigest()}"
    assert expected_key in fake._kv
    assert all(raw_token not in k and raw_token not in v[0] for k, v in fake._kv.items())
    assert 1 <= fake._ttls[expected_key] <= 600

    # Worker B verifies session created on Worker A
    verified = worker_b.verify(token=raw_token, slug="luxe-salon", session_id="sess_abc")
    assert verified.organization_id == org_id
    assert verified.business_id == biz_id

    # Wrong slug / session rejected
    with pytest.raises(HTTPException) as bad_slug:
        worker_b.verify(token=raw_token, slug="other-salon", session_id="sess_abc")
    assert bad_slug.value.status_code == 403

    # Revocation deletes key and blocks subsequent verify
    worker_b.revoke(raw_token)
    with pytest.raises(HTTPException) as revoked:
        worker_a.verify(token=raw_token, slug="luxe-salon", session_id="sess_abc")
    assert revoked.value.status_code == 403

    # Malformed stored state rejected & cleaned up
    fake._kv[expected_key] = ("{not-valid-json", None)
    with pytest.raises(HTTPException) as malformed:
        worker_b.verify(token=raw_token, slug="luxe-salon", session_id="sess_abc")
    assert malformed.value.status_code == 403
    assert expected_key not in fake._kv

    # Outage returns controlled 503
    fake.fail_all = True
    with pytest.raises(HTTPException) as outage:
        worker_b.verify(token=raw_token, slug="luxe-salon", session_id="sess_abc")
    assert outage.value.status_code == 503


# =============================================================================
# 3. Distributed Atomic Rate Limiter
# =============================================================================


def test_redis_rate_limiter_atomic_across_workers_and_fails_closed() -> None:
    fake = _FakeDistributedRedis()
    limiter_a = RedisRateLimiter(redis_client=fake, namespace="voice", window_seconds=60, default_max_requests=5)
    limiter_b = RedisRateLimiter(redis_client=fake, namespace="voice", window_seconds=60, default_max_requests=5)

    def _hit(idx: int) -> int:
        limiter = limiter_a if idx % 2 == 0 else limiter_b
        try:
            limiter.check_and_record("ip:203.0.113.10", 5)
            return 201
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(_hit, range(20)))

    assert results.count(201) == 5
    assert results.count(429) == 15

    # Advance past window -> allowed again
    fake.advance_seconds(61)
    limiter_b.check_and_record("ip:203.0.113.10", 5)

    # Redis outage fails closed with 503
    fake.fail_all = True
    with pytest.raises(HTTPException) as outage:
        limiter_a.check_and_record("ip:203.0.113.10", 5)
    assert outage.value.status_code == 503


# =============================================================================
# 4. Distributed Conversation Context
# =============================================================================


def test_redis_context_manager_cross_worker_isolation_ttl_and_malformed() -> None:
    fake = _FakeDistributedRedis()
    ctx_a = RedisConversationContextManager(fake)
    ctx_b = RedisConversationContextManager(fake)

    org_id = uuid4()
    biz_id = uuid4()
    other_org = uuid4()

    ctx_a.initialize_session(
        session_id="sess_ctx_1",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    ctx_b.start_new_turn(
        session_id="sess_ctx_1",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
        user_query="Do you have haircut slots?",
    )
    loaded = ctx_a.get_or_create_context(
        session_id="sess_ctx_1",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    assert loaded.turn_count == 1
    assert "do you have haircut slots?" in loaded.recent_user_queries

    # Verify 30-min (1800s) TTL
    ctx_key = ctx_a._ctx_key("sess_ctx_1")
    assert fake._ttls[ctx_key] == 1800

    # Cross-tenant isolation enforced
    with pytest.raises(HTTPException) as cross:
        ctx_b.get_or_create_context(
            session_id="sess_ctx_1",
            organization_id=other_org,
            business_id=biz_id,
            industry=OrganizationIndustry.SALON,
        )
    assert cross.value.status_code == 403

    # Malformed context handled safely
    fake._kv[ctx_key] = ("{bad", None)
    with pytest.raises(HTTPException) as bad_ctx:
        ctx_b.get_or_create_context(
            session_id="sess_ctx_1",
            organization_id=org_id,
            business_id=biz_id,
            industry=OrganizationIndustry.SALON,
        )
    assert bad_ctx.value.status_code == 500
    assert ctx_key not in fake._kv

    # Outage fails closed with 503
    fake.fail_all = True
    with pytest.raises(HTTPException) as outage:
        ctx_a.get_or_create_context(
            session_id="sess_ctx_1",
            organization_id=org_id,
            business_id=biz_id,
            industry=OrganizationIndustry.SALON,
        )
    assert outage.value.status_code == 503


def test_sliding_window_lua_keys_unique_members_and_rejected_quota() -> None:
    fake = _FakeDistributedRedis()
    limiter = RedisRateLimiter(
        redis_client=fake,
        namespace="public_website",
        window_seconds=60,
        default_max_requests=3,
    )
    zkey, skey = limiter._keys_for("203.0.113.77")
    assert zkey != skey
    assert skey == f"{zkey}:seq"

    # 3 requests within the exact same millisecond produce 3 unique members
    for _ in range(3):
        limiter.check("203.0.113.77")
    assert len(fake._zsets[zkey]) == 3
    assert fake._counters[skey] == 3
    assert fake._ttls[zkey] == 61
    assert fake._ttls[skey] == 61

    # Rejected 429 requests must NOT consume quota or increment seq
    for _ in range(4):
        with pytest.raises(HTTPException) as exc:
            limiter.check("203.0.113.77")
        assert exc.value.status_code == 429
    assert len(fake._zsets[zkey]) == 3
    assert fake._counters[skey] == 3

    # At exact boundary (+60s -> score == cutoff), old entries are pruned and 1 request succeeds
    fake.advance_seconds(60)
    limiter.check("203.0.113.77")
    assert len(fake._zsets[zkey]) == 1
    assert fake._counters[skey] == 4


def test_redis_context_concurrent_cas_updates_have_no_lost_writes() -> None:
    fake = _FakeDistributedRedis()
    ctx_a = RedisConversationContextManager(fake)
    ctx_b = RedisConversationContextManager(fake)
    org_id = uuid4()
    biz_id = uuid4()

    ctx_a.initialize_session(
        session_id="sess_cas_1",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )

    def _run_turn(idx: int) -> None:
        mgr = ctx_a if idx % 2 == 0 else ctx_b
        mgr.start_new_turn(
            session_id="sess_cas_1",
            organization_id=org_id,
            business_id=biz_id,
            industry=OrganizationIndustry.SALON,
            user_query=f"query {idx}",
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(_run_turn, range(10)))

    final_ctx = ctx_a.get_or_create_context(
        session_id="sess_cas_1",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    assert final_ctx.turn_count == 10


@pytest.mark.asyncio
async def test_policy_authority_rejects_unpublished_or_disabled_despite_stale_registry() -> None:
    from unittest.mock import AsyncMock, MagicMock
    from app.modules.websites.public_voice import PublicWebsiteVoiceBridgeService
    from app.modules.websites.schemas import (
        BookingWebsiteButtonStyle,
        BookingWebsiteFontFamily,
        BookingWebsiteTemplateId,
        BookingWebsiteTheme,
        PublicBookingWebsiteResponse,
        PublicBusinessProfile,
        PublicReceptionistInfo,
        PublicWebsiteVoiceToolRequest,
    )
    from app.modules.voice.public_access import PublicVoicePolicyRegistry

    fake = _FakeDistributedRedis()
    session_store = RedisPublicSessionStore(fake)
    org_id = uuid4()
    biz_id = uuid4()
    token = "visitor-tok-policy-check"
    session_store.put(
        token,
        _BoundPublicVoiceSession(
            slug="riya-salon",
            session_id="sess_pol_1",
            organization_id=org_id,
            business_id=biz_id,
            internal_public_token="internal_tok",
            has_persistent_db_access=False,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ),
    )

    # Stale policy registry still has an entry for (org_id, biz_id)
    stale_registry = PublicVoicePolicyRegistry()
    mock_voice_service = MagicMock()
    mock_voice_service._public_registry = stale_registry
    mock_voice_service.execute_voice_tool = AsyncMock()

    # 1. Supabase reports receptionist disabled -> immediate 403
    disabled_site = PublicBookingWebsiteResponse(
        slug="riya-salon",
        template_id=BookingWebsiteTemplateId.LUXE_STUDIO,
        published_at=datetime.now(timezone.utc),
        primary_color="#7657F6",
        secondary_color="#36C6D3",
        accent_color="#D4AF37",
        background_color="#0B1020",
        text_color="#F5F7FC",
        theme=BookingWebsiteTheme.DARK,
        font_family=BookingWebsiteFontFamily.INTER,
        button_style=BookingWebsiteButtonStyle.ROUNDED,
        show_services=True,
        show_hours=True,
        show_ai_receptionist=False,
        business=PublicBusinessProfile(display_name="Riya Salon", timezone="Asia/Kolkata"),
        hours=[],
        services=[],
        receptionist=PublicReceptionistInfo(enabled=False),
    )
    mock_website_service = MagicMock()
    mock_website_service.get_public_website_by_slug = AsyncMock(return_value=disabled_site)

    bridge = PublicWebsiteVoiceBridgeService(
        settings=Settings(SVARIO_ENV="development"),
        website_service=mock_website_service,
        voice_service=mock_voice_service,
        session_store=session_store,
    )

    with pytest.raises(HTTPException) as exc_disabled:
        await bridge.execute_public_voice_tool(
            slug="riya-salon",
            client_ip="198.51.100.1",
            payload=PublicWebsiteVoiceToolRequest(
                session_id="sess_pol_1",
                call_id="call_1",
                visitor_session_token=token,
                tool_name="get_salon_services",
                arguments={},
            ),
        )
    assert exc_disabled.value.status_code == 403
    mock_voice_service.execute_voice_tool.assert_not_called()

    # 2. Client-supplied tenant override in tool arguments is rejected even when enabled
    enabled_site = disabled_site.model_copy(
        update={
            "show_ai_receptionist": True,
            "receptionist": PublicReceptionistInfo(enabled=True),
        }
    )
    mock_website_service.get_public_website_by_slug = AsyncMock(return_value=enabled_site)
    override_resp = await bridge.execute_public_voice_tool(
        slug="riya-salon",
        client_ip="198.51.100.1",
        payload=PublicWebsiteVoiceToolRequest(
            session_id="sess_pol_1",
            call_id="call_2",
            visitor_session_token=token,
            tool_name="get_salon_services",
            arguments={"organization_id": str(uuid4())},
        ),
    )
    assert override_resp.status == "rejected"
    assert override_resp.output["error"] == "forbidden_tenant_override"


@pytest.mark.asyncio
async def test_signoff_1_unpublished_website_overrides_stale_policy() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock
    from app.modules.websites.public_voice import (
        PublicWebsiteVoiceBridgeService,
        _build_allowlisted_bundle_from_public_site,
    )
    from app.modules.websites.schemas import (
        BookingWebsiteButtonStyle,
        BookingWebsiteFontFamily,
        BookingWebsiteTemplateId,
        BookingWebsiteTheme,
        PublicBookingWebsiteResponse,
        PublicBusinessProfile,
        PublicReceptionistInfo,
        PublicWebsiteVoiceToolRequest,
    )
    from app.modules.voice.public_access import PublicVoicePolicyRegistry

    fake = _FakeDistributedRedis()
    session_store = RedisPublicSessionStore(fake)
    org_id = uuid4()
    biz_id = uuid4()
    token = "visitor-tok-unpub-check"
    session_store.put(
        token,
        _BoundPublicVoiceSession(
            slug="riya-salon",
            session_id="sess_unpub_1",
            organization_id=org_id,
            business_id=biz_id,
            internal_public_token="internal_tok",
            has_persistent_db_access=True,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ),
    )

    published_site = PublicBookingWebsiteResponse(
        slug="riya-salon",
        template_id=BookingWebsiteTemplateId.LUXE_STUDIO,
        published_at=datetime.now(timezone.utc),
        primary_color="#7657F6",
        secondary_color="#36C6D3",
        accent_color="#D4AF37",
        background_color="#0B1020",
        text_color="#F5F7FC",
        theme=BookingWebsiteTheme.DARK,
        font_family=BookingWebsiteFontFamily.INTER,
        button_style=BookingWebsiteButtonStyle.ROUNDED,
        show_services=True,
        show_hours=True,
        show_ai_receptionist=True,
        business=PublicBusinessProfile(display_name="Riya Salon", timezone="Asia/Kolkata"),
        hours=[],
        services=[],
        receptionist=PublicReceptionistInfo(enabled=True),
    )

    # Populate worker's PublicVoicePolicyRegistry with a previously authorized policy
    stale_registry = PublicVoicePolicyRegistry()
    stale_registry.register_bundle(
        _build_allowlisted_bundle_from_public_site(
            published_site, organization_id=org_id, business_id=biz_id
        )
    )
    assert stale_registry.get_bundle(org_id, biz_id) is not None

    mock_voice_service = MagicMock()
    mock_voice_service._public_registry = stale_registry
    mock_voice_service.execute_voice_tool = AsyncMock()

    # Authoritative Supabase resolver returns website with published = False
    unpublished_site = SimpleNamespace(
        slug="riya-salon",
        published=False,
        show_ai_receptionist=True,
        receptionist=PublicReceptionistInfo(enabled=True),
    )
    mock_website_service = MagicMock()
    mock_website_service.get_public_website_by_slug = AsyncMock(return_value=unpublished_site)

    bridge = PublicWebsiteVoiceBridgeService(
        settings=Settings(SVARIO_ENV="development"),
        website_service=mock_website_service,
        voice_service=mock_voice_service,
        session_store=session_store,
    )

    with pytest.raises(HTTPException) as exc:
        await bridge.execute_public_voice_tool(
            slug="riya-salon",
            client_ip="198.51.100.1",
            payload=PublicWebsiteVoiceToolRequest(
                session_id="sess_unpub_1",
                call_id="call_unpub_1",
                visitor_session_token=token,
                tool_name="get_salon_services",
                arguments={},
            ),
        )

    assert exc.value.status_code == 403
    mock_voice_service.execute_voice_tool.assert_not_called()


@pytest.mark.asyncio
async def test_signoff_2_internal_session_binding_integrity() -> None:
    from unittest.mock import AsyncMock, MagicMock
    from app.modules.onboarding.repository import InMemoryOnboardingRepository
    from app.modules.onboarding.service import OnboardingService
    from app.modules.organizations.repository import InMemoryOrganizationRepository
    from app.modules.voice.public_access import PublicVoicePolicyRegistry, mint_public_voice_token
    from app.modules.voice.service import VoiceSessionService
    from app.modules.websites.public_voice import (
        PublicWebsiteVoiceBridgeService,
        _build_allowlisted_bundle_from_public_site,
    )
    from app.modules.websites.schemas import (
        BookingWebsiteButtonStyle,
        BookingWebsiteFontFamily,
        BookingWebsiteTemplateId,
        BookingWebsiteTheme,
        PublicBookingWebsiteResponse,
        PublicBusinessProfile,
        PublicReceptionistInfo,
        PublicWebsiteVoiceToolRequest,
    )

    settings = Settings(
        SVARIO_ENV="development",
        VOICE_PUBLIC_TOKEN_SECRET="signoff-test-hmac-secret-key-0123456789abcdef",
    )
    fake = _FakeDistributedRedis()
    session_store = RedisPublicSessionStore(fake)
    org_id = uuid4()
    biz_id = uuid4()
    other_org_id = uuid4()
    other_biz_id = uuid4()

    enabled_site = PublicBookingWebsiteResponse(
        slug="riya-salon",
        template_id=BookingWebsiteTemplateId.LUXE_STUDIO,
        published_at=datetime.now(timezone.utc),
        primary_color="#7657F6",
        secondary_color="#36C6D3",
        accent_color="#D4AF37",
        background_color="#0B1020",
        text_color="#F5F7FC",
        theme=BookingWebsiteTheme.DARK,
        font_family=BookingWebsiteFontFamily.INTER,
        button_style=BookingWebsiteButtonStyle.ROUNDED,
        show_services=True,
        show_hours=True,
        show_ai_receptionist=True,
        business=PublicBusinessProfile(display_name="Riya Salon", timezone="Asia/Kolkata"),
        hours=[],
        services=[],
        receptionist=PublicReceptionistInfo(enabled=True),
    )

    org_repo = InMemoryOrganizationRepository()
    onboarding_service = OnboardingService(repository=InMemoryOnboardingRepository(org_repo=org_repo))
    mock_orchestrator = MagicMock()
    mock_orchestrator.execute_realtime_tool = AsyncMock()

    voice_service = VoiceSessionService(
        settings=settings,
        onboarding_service=onboarding_service,
        rate_limiter=RedisRateLimiter(redis_client=fake, namespace="voice", window_seconds=60, default_max_requests=10),
        public_registry=PublicVoicePolicyRegistry(),
        orchestrator=mock_orchestrator,
    )

    mock_website_service = MagicMock()
    mock_website_service.get_public_website_by_slug = AsyncMock(return_value=enabled_site)

    bridge = PublicWebsiteVoiceBridgeService(
        settings=settings,
        website_service=mock_website_service,
        voice_service=voice_service,
        session_store=session_store,
    )

    # 1. Mismatched / tampered internal public token
    valid_token, _, _ = mint_public_voice_token(
        settings=settings,
        organization_id=org_id,
        business_id=biz_id,
        ttl_seconds=300,
    )
    tampered_internal = valid_token[:-4] + ("AAAA" if not valid_token.endswith("AAAA") else "BBBB")
    visitor_tok_tampered = "visitor-tok-tampered-internal"
    session_store.put(
        visitor_tok_tampered,
        _BoundPublicVoiceSession(
            slug="riya-salon",
            session_id="sess_bind_1",
            organization_id=org_id,
            business_id=biz_id,
            internal_public_token=tampered_internal,
            has_persistent_db_access=True,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ),
    )

    with pytest.raises(HTTPException) as exc_tampered:
        await bridge.execute_public_voice_tool(
            slug="riya-salon",
            client_ip="198.51.100.1",
            payload=PublicWebsiteVoiceToolRequest(
                session_id="sess_bind_1",
                call_id="call_bind_1",
                visitor_session_token=visitor_tok_tampered,
                tool_name="get_salon_services",
                arguments={},
            ),
        )
    assert exc_tampered.value.status_code == 403
    mock_orchestrator.execute_realtime_tool.assert_not_called()

    # 2. Mismatched organization/business tenant binding (internal token minted for another tenant)
    other_tenant_token, _, _ = mint_public_voice_token(
        settings=settings,
        organization_id=other_org_id,
        business_id=other_biz_id,
        ttl_seconds=300,
    )
    visitor_tok_cross_tenant = "visitor-tok-cross-tenant"
    session_store.put(
        visitor_tok_cross_tenant,
        _BoundPublicVoiceSession(
            slug="riya-salon",
            session_id="sess_bind_2",
            organization_id=org_id,
            business_id=biz_id,
            internal_public_token=other_tenant_token,
            has_persistent_db_access=True,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        ),
    )

    with pytest.raises(HTTPException) as exc_cross:
        await bridge.execute_public_voice_tool(
            slug="riya-salon",
            client_ip="198.51.100.1",
            payload=PublicWebsiteVoiceToolRequest(
                session_id="sess_bind_2",
                call_id="call_bind_2",
                visitor_session_token=visitor_tok_cross_tenant,
                tool_name="get_salon_services",
                arguments={},
            ),
        )
    assert exc_cross.value.status_code == 403
    mock_orchestrator.execute_realtime_tool.assert_not_called()
