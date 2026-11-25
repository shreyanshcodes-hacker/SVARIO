"""Centralized Redis provider (Upstash REST over httpx) with fail-closed production validation."""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, Sequence, runtime_checkable
import httpx
from fastapi import HTTPException, status
from app.core.config import Settings, get_settings

logger = logging.getLogger("svario.redis")


class RedisUnavailableError(RuntimeError):
    """Raised when the distributed Redis backend is unreachable or returns an error."""


@runtime_checkable
class RedisClientProtocol(Protocol):
    """Minimal synchronous Redis command interface used by Stage 3B-2 stores."""

    def execute(self, command: Sequence[Any]) -> Any: ...

    def ping(self) -> bool: ...

    def close(self) -> None: ...


def validate_production_redis_config(settings: Settings) -> None:
    """Validate that Upstash HTTPS REST Redis is configured when SVARIO_ENV=production."""
    if not settings.is_production:
        return

    upstash_url = (settings.upstash_redis_rest_url or "").strip()
    upstash_token = (settings.upstash_redis_rest_token or "").strip()

    if not upstash_url or not upstash_url.startswith("https://"):
        raise RuntimeError(
            "Startup aborted: SVARIO_ENV=production requires UPSTASH_REDIS_REST_URL using https://."
        )
    if (
        not upstash_token
        or "placeholder" in upstash_token.lower()
        or upstash_token.startswith("your-")
    ):
        raise RuntimeError(
            "Startup aborted: UPSTASH_REDIS_REST_TOKEN must be a valid non-placeholder token in production."
        )


class UpstashRestRedisClient:
    """Thread-safe Upstash Redis REST client backed by a shared httpx.Client."""

    def __init__(
        self,
        *,
        rest_url: str,
        rest_token: str,
        timeout_seconds: float = 2.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = rest_url.strip().rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {rest_token.strip()}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout_seconds, connect=min(1.0, timeout_seconds)),
        )

    def execute(self, command: Sequence[Any]) -> Any:
        """Execute a single Redis command via Upstash REST POST /."""
        try:
            response = self._client.post("/", json=list(command))
        except httpx.HTTPError as exc:
            logger.warning("redis_request_failed error_type=%s", type(exc).__name__)
            raise RedisUnavailableError("Distributed state store is unavailable.") from exc

        if response.status_code >= 500 or response.status_code in (401, 403):
            logger.warning("redis_http_error status=%s", response.status_code)
            raise RedisUnavailableError("Distributed state store returned an error.")

        if response.status_code >= 400:
            logger.warning("redis_client_error status=%s", response.status_code)
            raise RedisUnavailableError("Distributed state store rejected the command.")

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("redis_invalid_json")
            raise RedisUnavailableError("Distributed state store returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise RedisUnavailableError("Distributed state store returned an invalid response.")

        if payload.get("error"):
            logger.warning("redis_command_error")
            raise RedisUnavailableError("Distributed state store command failed.")

        return payload.get("result")

    def ping(self) -> bool:
        try:
            return str(self.execute(["PING"])).upper() == "PONG"
        except RedisUnavailableError:
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


_shared_redis_client: Optional[RedisClientProtocol] = None


def init_redis_client(settings: Settings) -> Optional[RedisClientProtocol]:
    """Initialize and cache the shared Upstash REST Redis client if configured."""
    global _shared_redis_client
    validate_production_redis_config(settings)

    if settings.is_upstash_redis_configured:
        client = UpstashRestRedisClient(
            rest_url=settings.upstash_redis_rest_url or "",
            rest_token=settings.upstash_redis_rest_token or "",
            timeout_seconds=settings.redis_timeout_seconds,
        )
        _shared_redis_client = client
        return client

    _shared_redis_client = None
    return None


def get_redis_client(settings: Optional[Settings] = None) -> Optional[RedisClientProtocol]:
    """Return the active shared Redis client, initializing lazily if configured."""
    global _shared_redis_client
    if _shared_redis_client is not None:
        return _shared_redis_client
    resolved = settings or get_settings()
    if resolved.is_redis_configured:
        return init_redis_client(resolved)
    return None


def set_redis_client_for_tests(client: Optional[RedisClientProtocol]) -> None:
    """Override the shared Redis client in tests."""
    global _shared_redis_client
    _shared_redis_client = client


def close_redis_client(expected_client: Optional[RedisClientProtocol] = None) -> None:
    """Close and clear the shared Redis client on shutdown (app-instance safe)."""
    global _shared_redis_client
    target = expected_client if expected_client is not None else _shared_redis_client
    if target is not None:
        target.close()
    if expected_client is None or _shared_redis_client is expected_client:
        _shared_redis_client = None


def raise_redis_unavailable() -> HTTPException:
    """Construct a controlled HTTP 503 error without leaking Redis details."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Service temporarily unavailable. Please try again shortly.",
    )
