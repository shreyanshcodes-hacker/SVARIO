"""Stage 3B-3 Multi-Worker Integration & Distributed-State Reliability Tests.

Runs two completely independent FastAPI application instances (Worker A & Worker B)
communicating over HTTP with a shared Upstash-REST-compatible test server.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.agents.context import RedisConversationContextManager, get_conversation_context_manager
from app.agents.orchestrator import AgentOrchestrator, get_agent_orchestrator
from app.core.auth import SupabaseJWTVerifier, get_jwt_verifier
from app.core.config import Settings, get_settings
from app.core.redis_provider import (
    UpstashRestRedisClient,
    close_redis_client,
    set_redis_client_for_tests,
)
from app.main import create_app
from app.modules.onboarding.repository import InMemoryOnboardingRepository
from app.modules.onboarding.schemas import (
    BusinessHoursResponse,
    BusinessProfileResponse,
    LanguageCode,
    OnboardingBundleResponse,
    WeekdayHoursItem,
)
from app.modules.onboarding.service import OnboardingService, get_onboarding_service
from app.modules.organizations.repository import InMemoryOrganizationRepository
from app.modules.organizations.schemas import OrganizationIndustry, OrganizationRole
from app.modules.organizations.service import OrganizationService, get_organization_service
from app.modules.voice.public_access import PublicVoicePolicyRegistry, get_public_voice_policy_registry
from app.modules.voice.rate_limit import RedisRateLimiter, get_voice_rate_limiter
from app.modules.voice.service import VoiceSessionService, get_voice_session_service
from app.modules.websites.public_voice import (
    PublicWebsiteVoiceBridgeService,
    RedisPublicSessionStore,
    get_public_website_voice_bridge_service,
    get_public_website_voice_session_store,
)
from app.modules.websites.repository import InMemoryBookingWebsiteRepository
from app.modules.websites.schemas import (
    BookingWebsiteButtonStyle,
    BookingWebsiteFontFamily,
    BookingWebsiteTemplateId,
    BookingWebsiteTheme,
    PublicBookingWebsiteResponse,
    PublicBusinessHour,
    PublicBusinessProfile,
    PublicReceptionistInfo,
    PublicSalonService,
)
from app.modules.websites.service import BookingWebsiteService, get_booking_website_service

TEST_UPSTASH_TOKEN = "stage3b3-local-upstash-test-token-do-not-leak"


class _UpstashRestTestServer:
    """Deterministic local HTTP server implementing Upstash Redis REST POST /."""

    def __init__(self, expected_token: str = TEST_UPSTASH_TOKEN) -> None:
        self.expected_token = expected_token
        self.lock = threading.Lock()
        self.kv: Dict[str, Tuple[str, Optional[float]]] = {}
        self.lists: Dict[str, List[str]] = {}
        self.zsets: Dict[str, Dict[str, float]] = {}
        self.counters: Dict[str, int] = {}
        self.ttls: Dict[str, int] = {}
        self.now_ms: int = 1_700_000_000_000
        self.outage_mode: bool = False
        self.delay_seconds: float = 0.0

        server_ref = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return None

            def do_POST(self) -> None:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {server_ref.expected_token}":
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b'{"error":"unauthorized"}')
                    return

                if server_ref.delay_seconds > 0:
                    time.sleep(server_ref.delay_seconds)

                if server_ref.outage_mode:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'{"error":"simulated_redis_outage"}')
                    return

                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8")
                cmd = json.loads(raw_body)
                try:
                    result = server_ref._execute(cmd)
                    body = json.dumps({"result": result}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    body = json.dumps({"error": str(exc)}).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._httpd.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def advance_seconds(self, seconds: int) -> None:
        with self.lock:
            self.now_ms += seconds * 1000

    def _is_expired(self, key: str) -> bool:
        entry = self.kv.get(key)
        if entry is None:
            return False
        _, exp = entry
        if exp is not None and (self.now_ms / 1000.0) >= exp:
            self.kv.pop(key, None)
            return True
        return False

    def _execute(self, command: List[Any]) -> Any:
        cmd = str(command[0]).upper()
        with self.lock:
            if cmd == "PING":
                return "PONG"
            if cmd == "GET":
                key = str(command[1])
                if self._is_expired(key):
                    return None
                entry = self.kv.get(key)
                return entry[0] if entry is not None else None
            if cmd == "SET":
                key = str(command[1])
                val = str(command[2])
                exp: Optional[float] = None
                if len(command) >= 5 and str(command[3]).upper() == "EX":
                    ttl = int(command[4])
                    self.ttls[key] = ttl
                    exp = (self.now_ms / 1000.0) + ttl
                self.kv[key] = (val, exp)
                return "OK"
            if cmd == "DEL":
                key = str(command[1])
                existed = 1 if key in self.kv else 0
                self.kv.pop(key, None)
                self.lists.pop(key, None)
                self.zsets.pop(key, None)
                return existed
            if cmd == "EXPIRE":
                key = str(command[1])
                ttl = int(command[2])
                self.ttls[key] = ttl
                if key in self.kv:
                    val, _ = self.kv[key]
                    self.kv[key] = (val, (self.now_ms / 1000.0) + ttl)
                return 1
            if cmd == "RPUSH":
                key = str(command[1])
                self.lists.setdefault(key, []).append(str(command[2]))
                return len(self.lists[key])
            if cmd == "EVAL":
                script = str(command[1])
                if "ZREMRANGEBYSCORE" in script:
                    zkey = str(command[3])
                    skey = str(command[4])
                    window_ms = int(command[5]) * 1000
                    limit = int(command[6])
                    cutoff = self.now_ms - window_ms
                    zset = self.zsets.setdefault(zkey, {})
                    for member in [m for m, sc in zset.items() if sc <= cutoff]:
                        zset.pop(member, None)
                    if len(zset) >= limit:
                        oldest_ms = min(zset.values()) if zset else self.now_ms
                        retry = max(1, int(((oldest_ms + window_ms - self.now_ms) + 999) // 1000))
                        return [0, retry]
                    seq = self.counters.get(skey, 0) + 1
                    self.counters[skey] = seq
                    zset[f"{self.now_ms}:{seq}"] = float(self.now_ms)
                    self.ttls[zkey] = (window_ms + 1000) // 1000
                    self.ttls[skey] = (window_ms + 1000) // 1000
                    return [1, 0]
                if "cjson.decode" in script:
                    key = str(command[3])
                    expected_ver = int(command[4])
                    payload = str(command[5])
                    ttl = int(command[6])
                    self._is_expired(key)
                    cur = self.kv.get(key)
                    if cur is not None:
                        decoded = json.loads(cur[0])
                        if int(decoded.get("version", 0)) != expected_ver:
                            return 0
                    elif expected_ver != 0:
                        return 0
                    self.ttls[key] = ttl
                    self.kv[key] = (payload, (self.now_ms / 1000.0) + ttl)
                    return 1
            raise ValueError(f"Unsupported command: {cmd}")


class _SharedSupabaseAuthority:
    """Shared authoritative Supabase state queried by both Worker A and Worker B."""

    def __init__(self, org_id: UUID, biz_id: UUID, slug: str = "riya-salon") -> None:
        self.org_id = org_id
        self.biz_id = biz_id
        self.slug = slug
        self.published = True
        self.receptionist_enabled = True

    def current_site(self) -> PublicBookingWebsiteResponse:
        if not self.published:
            raise HTTPException(status_code=404, detail="Booking website not found.")
        return PublicBookingWebsiteResponse(
            slug=self.slug,
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
            show_ai_receptionist=self.receptionist_enabled,
            business=PublicBusinessProfile(
                display_name="Riya Salon",
                phone="+919876543210",
                timezone="Asia/Kolkata",
            ),
            hours=[
                PublicBusinessHour(
                    weekday=1, is_closed=False, opens_at="10:00", closes_at="20:00", is_overnight=False
                )
            ],
            services=[
                PublicSalonService(
                    id=uuid4(),
                    name="Signature Haircut",
                    category="Hair",
                    description="Precision cut & blow dry",
                    duration_minutes=45,
                    price=599.0,
                    currency="INR",
                )
            ],
            receptionist=PublicReceptionistInfo(
                enabled=self.receptionist_enabled,
                assistant_name="Riya AI",
                greeting="Welcome to Riya Salon!",
            ),
        )


def _build_worker_instance(
    *,
    redis_server: _UpstashRestTestServer,
    authority: _SharedSupabaseAuthority,
    jwt_public_key: Any,
    voice_rate_limit: int = 4,
    public_rate_limit: int = 50,
    redis_timeout: float = 1.0,
) -> Dict[str, Any]:
    """Build an isolated FastAPI worker with its own DI container, Redis client, and Python memory."""
    settings = Settings(
        SVARIO_ENV="development",
        SUPABASE_URL="https://test-project.supabase.co",
        SUPABASE_JWT_ISSUER="https://test-project.supabase.co/auth/v1",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHMS="ES256",
        OPENAI_API_KEY="sk-proj-stage3b3-test-key-123456",
        VOICE_SESSION_RATE_LIMIT_PER_MINUTE=voice_rate_limit,
        VOICE_PUBLIC_TOKEN_SECRET="stage3b3-worker-hmac-secret-key-0123456789abcdef",
        UPSTASH_REDIS_REST_URL=redis_server.base_url,
        UPSTASH_REDIS_REST_TOKEN=TEST_UPSTASH_TOKEN,
        REDIS_TIMEOUT_SECONDS=redis_timeout,
    )

    worker_redis = UpstashRestRedisClient(
        rest_url=redis_server.base_url,
        rest_token=TEST_UPSTASH_TOKEN,
        timeout_seconds=redis_timeout,
    )
    verifier = SupabaseJWTVerifier(settings=settings, key_resolver=lambda _t, _h: jwt_public_key)
    org_repo = InMemoryOrganizationRepository()
    org_service = OrganizationService(repository=org_repo)
    onboarding_repo = InMemoryOnboardingRepository(org_repo=org_repo)
    onboarding_service = OnboardingService(repository=onboarding_repo)

    public_rl = RedisRateLimiter(
        redis_client=worker_redis,
        namespace="public_website",
        window_seconds=60,
        default_max_requests=public_rate_limit,
        detail_message="Too many requests. Please wait a moment and try again.",
        include_retry_after_header=False,
    )
    voice_rl = RedisRateLimiter(
        redis_client=worker_redis,
        namespace="voice",
        window_seconds=60,
        default_max_requests=voice_rate_limit,
        include_retry_after_header=True,
    )
    session_store = RedisPublicSessionStore(worker_redis)
    context_mgr = RedisConversationContextManager(worker_redis)
    policy_registry = PublicVoicePolicyRegistry()

    async def _mock_mint(_cfg: Settings, _payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": f"sess_{uuid4().hex[:12]}",
            "value": "ek_stage3b3_ephemeral",
            "expires_at": int((datetime.now(timezone.utc) + timedelta(minutes=2)).timestamp()),
        }

    orchestrator = AgentOrchestrator(context_manager=context_mgr, rate_limiter=voice_rl)
    voice_service = VoiceSessionService(
        settings=settings,
        onboarding_service=onboarding_service,
        rate_limiter=voice_rl,
        public_registry=policy_registry,
        upstream_mint=_mock_mint,
        orchestrator=orchestrator,
    )

    website_repo = InMemoryBookingWebsiteRepository()
    website_service = BookingWebsiteService(
        settings=settings,
        onboarding_service=onboarding_service,
        website_repo=website_repo,
        rate_limiter=public_rl,
    )

    # Wire authoritative Supabase resolver (shared across workers)
    async def _get_public_by_slug(*, slug: str, client_ip: str = "unknown") -> PublicBookingWebsiteResponse:
        public_rl.check(client_ip)
        if slug != authority.slug:
            raise HTTPException(status_code=404, detail="Booking website not found.")
        return authority.current_site()

    website_service.get_public_website_by_slug = _get_public_by_slug  # type: ignore[method-assign]
    website_repo.get_published_tenant_ids = lambda _s: _async_return((authority.org_id, authority.biz_id))  # type: ignore[method-assign]

    bridge = PublicWebsiteVoiceBridgeService(
        settings=settings,
        website_service=website_service,
        voice_service=voice_service,
        session_store=session_store,
    )

    app = create_app(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_jwt_verifier] = lambda: verifier
    app.dependency_overrides[get_organization_service] = lambda: org_service
    app.dependency_overrides[get_onboarding_service] = lambda: onboarding_service
    app.dependency_overrides[get_voice_rate_limiter] = lambda: voice_rl
    app.dependency_overrides[get_conversation_context_manager] = lambda: context_mgr
    app.dependency_overrides[get_public_voice_policy_registry] = lambda: policy_registry
    app.dependency_overrides[get_agent_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_voice_session_service] = lambda: voice_service
    app.dependency_overrides[get_booking_website_service] = lambda: website_service
    app.dependency_overrides[get_public_website_voice_session_store] = lambda: session_store
    app.dependency_overrides[get_public_website_voice_bridge_service] = lambda: bridge

    return {
        "app": app,
        "client": TestClient(app),
        "redis": worker_redis,
        "session_store": session_store,
        "context_mgr": context_mgr,
        "policy_registry": policy_registry,
        "org_repo": org_repo,
        "settings": settings,
    }


async def _async_return(val: Any) -> Any:
    return val


@pytest.fixture
def two_worker_cluster() -> Any:
    server = _UpstashRestTestServer()
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_key = priv_key.public_key()
    org_id = uuid4()
    biz_id = uuid4()
    authority = _SharedSupabaseAuthority(org_id=org_id, biz_id=biz_id)

    worker_a = _build_worker_instance(
        redis_server=server,
        authority=authority,
        jwt_public_key=pub_key,
    )
    worker_b = _build_worker_instance(
        redis_server=server,
        authority=authority,
        jwt_public_key=pub_key,
    )
    try:
        yield {
            "server": server,
            "authority": authority,
            "worker_a": worker_a,
            "worker_b": worker_b,
            "priv_key": priv_key,
        }
    finally:
        worker_a["redis"].close()
        worker_b["redis"].close()
        set_redis_client_for_tests(None)
        close_redis_client()
        server.close()


# =============================================================================
# 1. Session Continuity, Revocation, Expiry & Tenant Isolation Across Workers
# =============================================================================


def test_stage3b3_cross_worker_session_continuity_revocation_and_security(
    two_worker_cluster: Dict[str, Any],
) -> None:
    server: _UpstashRestTestServer = two_worker_cluster["server"]
    wa: TestClient = two_worker_cluster["worker_a"]["client"]
    wb: TestClient = two_worker_cluster["worker_b"]["client"]

    # 1. Worker A creates a public voice session
    create_resp = wa.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
    assert create_resp.status_code == 201
    sess_data = create_resp.json()
    session_id = sess_data["session_id"]
    visitor_token = sess_data["visitor_session_token"]

    # Raw visitor token must never appear in Redis keys or values
    for k, (v, _) in server.kv.items():
        assert visitor_token not in k
        assert visitor_token not in v
    expected_key = f"svario:pub_sess:{hashlib.sha256(visitor_token.encode()).hexdigest()}"
    assert expected_key in server.kv
    assert 1 <= server.ttls[expected_key] <= 600

    # 2. Worker B executes tool using Worker A's visitor token
    tool_resp = wb.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": session_id,
            "call_id": "call_b_1",
            "visitor_session_token": visitor_token,
            "tool_name": "get_salon_services",
            "arguments": {},
        },
    )
    assert tool_resp.status_code == 200
    assert tool_resp.json()["status"] == "succeeded"

    # 3. Tampered visitor token rejected on both workers
    bad_tok_resp = wb.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": session_id,
            "call_id": "call_bad_1",
            "visitor_session_token": visitor_token + "tamper",
            "tool_name": "get_salon_services",
            "arguments": {},
        },
    )
    assert bad_tok_resp.status_code == 403

    # 4. Worker B revokes session -> Worker A immediately rejects token
    two_worker_cluster["worker_b"]["session_store"].revoke(visitor_token)
    after_revoke = wa.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": session_id,
            "call_id": "call_after_revoke",
            "visitor_session_token": visitor_token,
            "tool_name": "get_salon_services",
            "arguments": {},
        },
    )
    assert after_revoke.status_code == 403

    # 5. New session expires after TTL on both workers
    create_2 = wa.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
    assert create_2.status_code == 201
    s2 = create_2.json()
    server.advance_seconds(601)
    assert (
        wa.post(
            "/api/v1/public/websites/riya-salon/voice/tools/execute",
            json={
                "session_id": s2["session_id"],
                "call_id": "call_exp_a",
                "visitor_session_token": s2["visitor_session_token"],
                "tool_name": "get_salon_services",
                "arguments": {},
            },
        ).status_code
        == 403
    )
    assert (
        wb.post(
            "/api/v1/public/websites/riya-salon/voice/tools/execute",
            json={
                "session_id": s2["session_id"],
                "call_id": "call_exp_b",
                "visitor_session_token": s2["visitor_session_token"],
                "tool_name": "get_salon_services",
                "arguments": {},
            },
        ).status_code
        == 403
    )


# =============================================================================
# 2. Distributed Rate Limiting Across Workers
# =============================================================================


def test_stage3b3_distributed_rate_limiting_across_workers(
    two_worker_cluster: Dict[str, Any],
) -> None:
    server: _UpstashRestTestServer = two_worker_cluster["server"]
    wa: TestClient = two_worker_cluster["worker_a"]["client"]
    wb: TestClient = two_worker_cluster["worker_b"]["client"]

    # Combined traffic across Worker A + Worker B shares limit = 4 per 60s
    def _hit(idx: int) -> Tuple[int, Optional[str]]:
        c = wa if idx % 2 == 0 else wb
        resp = c.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
        return resp.status_code, resp.headers.get("retry-after")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_hit, range(12)))

    statuses = [r[0] for r in results]
    assert statuses.count(201) == 4
    assert statuses.count(429) == 8
    assert all(r[1] is not None for r in results if r[0] == 429)

    # Window expiry restores quota
    server.advance_seconds(61)
    res_after = wb.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
    assert res_after.status_code == 201


# =============================================================================
# 3. Conversation Context Continuity & Privacy Across Workers
# =============================================================================


def test_stage3b3_conversation_context_continuity_and_privacy(
    two_worker_cluster: Dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    server: _UpstashRestTestServer = two_worker_cluster["server"]
    ctx_a: RedisConversationContextManager = two_worker_cluster["worker_a"]["context_mgr"]
    ctx_b: RedisConversationContextManager = two_worker_cluster["worker_b"]["context_mgr"]
    org_id: UUID = two_worker_cluster["authority"].org_id
    biz_id: UUID = two_worker_cluster["authority"].biz_id

    caplog.set_level(logging.INFO)
    secret_query = "My private hair dye allergy note xyz"

    ctx_a.initialize_session(
        session_id="sess_mw_ctx",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    ctx_b.start_new_turn(
        session_id="sess_mw_ctx",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
        user_query=secret_query,
    )

    loaded_a = ctx_a.get_or_create_context(
        session_id="sess_mw_ctx",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    assert loaded_a.turn_count == 1
    assert secret_query.lower() in loaded_a.recent_user_queries

    # Concurrent turns across both workers preserve all turns
    def _turn(idx: int) -> None:
        mgr = ctx_a if idx % 2 == 0 else ctx_b
        mgr.start_new_turn(
            session_id="sess_mw_ctx",
            organization_id=org_id,
            business_id=biz_id,
            industry=OrganizationIndustry.SALON,
            user_query=f"turn {idx}",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_turn, range(6)))

    final_ctx = ctx_b.get_or_create_context(
        session_id="sess_mw_ctx",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    assert final_ctx.turn_count == 7

    # Cross-tenant rejected
    with pytest.raises(HTTPException) as cross:
        ctx_b.get_or_create_context(
            session_id="sess_mw_ctx",
            organization_id=uuid4(),
            business_id=biz_id,
            industry=OrganizationIndustry.SALON,
        )
    assert cross.value.status_code == 403

    # No private conversation content in logs
    assert secret_query not in caplog.text

    # Expired context is cleared after 1800s inactivity
    server.advance_seconds(1801)
    fresh = ctx_a.get_or_create_context(
        session_id="sess_mw_ctx",
        organization_id=org_id,
        business_id=biz_id,
        industry=OrganizationIndustry.SALON,
    )
    assert fresh.turn_count == 0


# =============================================================================
# 4. Authoritative Supabase Revocation Across Workers
# =============================================================================


def test_stage3b3_supabase_authoritative_revocation_across_workers(
    two_worker_cluster: Dict[str, Any],
) -> None:
    authority: _SharedSupabaseAuthority = two_worker_cluster["authority"]
    wa: TestClient = two_worker_cluster["worker_a"]["client"]
    wb: TestClient = two_worker_cluster["worker_b"]["client"]

    # Worker A creates session while published & enabled
    s = wa.post("/api/v1/public/websites/riya-salon/voice/sessions", json={}).json()

    # Worker B executes tool cleanly
    ok = wb.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": s["session_id"],
            "call_id": "c1",
            "visitor_session_token": s["visitor_session_token"],
            "tool_name": "get_salon_services",
            "arguments": {},
        },
    )
    assert ok.status_code == 200

    # Website unpublished -> Worker A immediately rejects despite stale registry
    authority.published = False
    unpub = wa.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": s["session_id"],
            "call_id": "c2",
            "visitor_session_token": s["visitor_session_token"],
            "tool_name": "get_salon_services",
            "arguments": {},
        },
    )
    assert unpub.status_code == 404

    # Re-publish, disable receptionist -> Worker B immediately rejects with 403
    authority.published = True
    authority.receptionist_enabled = False
    disabled = wb.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": s["session_id"],
            "call_id": "c3",
            "visitor_session_token": s["visitor_session_token"],
            "tool_name": "get_salon_services",
            "arguments": {},
        },
    )
    assert disabled.status_code == 403

    # Re-enable, client tenant override still rejected
    authority.receptionist_enabled = True
    override = wa.post(
        "/api/v1/public/websites/riya-salon/voice/tools/execute",
        json={
            "session_id": s["session_id"],
            "call_id": "c4",
            "visitor_session_token": s["visitor_session_token"],
            "tool_name": "get_salon_services",
            "arguments": {"organization_id": str(uuid4())},
        },
    )
    assert override.status_code == 200
    assert override.json()["status"] == "rejected"


# =============================================================================
# 5. Redis Outage, Timeout, Recovery, Startup & Readiness
# =============================================================================


def test_stage3b3_redis_outage_timeout_recovery_and_dashboard_isolation(
    two_worker_cluster: Dict[str, Any],
) -> None:
    server: _UpstashRestTestServer = two_worker_cluster["server"]
    wa: TestClient = two_worker_cluster["worker_a"]["client"]
    wb: TestClient = two_worker_cluster["worker_b"]["client"]
    priv_key = two_worker_cluster["priv_key"]

    # Production startup fails closed when Redis config is missing
    with pytest.raises(RuntimeError):
        create_app(
            Settings(
                SVARIO_ENV="production",
                SUPABASE_URL="https://prod.supabase.co",
                SUPABASE_ANON_KEY="live-anon-key",
                VOICE_PUBLIC_TOKEN_SECRET="prod-secret-0123456789abcdef0123456789",
            )
        )

    # Create authenticated dashboard user JWT on Worker A
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    member_jwt = jwt.encode(
        {
            "sub": str(user_id),
            "email": "owner@svario.ai",
            "role": "authenticated",
            "iss": "https://test-project.supabase.co/auth/v1",
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
        },
        priv_key,
        algorithm="ES256",
        headers={"kid": "k1", "typ": "JWT"},
    )

    # Simulate Redis outage
    server.outage_mode = True
    set_redis_client_for_tests(two_worker_cluster["worker_a"]["redis"])
    assert wa.get("/health/ready").status_code == 503
    outage_pub = wa.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
    assert outage_pub.status_code == 503
    assert TEST_UPSTASH_TOKEN not in outage_pub.text

    # Unrelated authenticated dashboard operation & /health still work during Redis outage
    assert wa.get("/health").status_code == 200
    assert (
        wa.get("/api/v1/organizations", headers={"Authorization": f"Bearer {member_jwt}"}).status_code
        == 200
    )

    # Simulate Redis timeout (> 1.0s worker timeout)
    server.outage_mode = False
    server.delay_seconds = 1.3
    timeout_resp = wb.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
    assert timeout_resp.status_code == 503
    assert TEST_UPSTASH_TOKEN not in timeout_resp.text

    # Recovery
    server.delay_seconds = 0.0
    assert wa.get("/health/ready").status_code == 200
    assert wa.get("/health/ready").json() == {"status": "ready", "redis": "ok"}
    recovered = wb.post("/api/v1/public/websites/riya-salon/voice/sessions", json={})
    assert recovered.status_code == 201
