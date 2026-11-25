"""Sliding-window rate limiters (in-memory for dev/test + Redis Lua atomic for production)."""

import hashlib
import threading
import time
import zlib
from collections import deque
from typing import Deque, Dict, Optional
from fastapi import Depends, HTTPException, status
from app.core.config import Settings, get_settings
from app.core.redis_provider import (
    RedisClientProtocol,
    RedisUnavailableError,
    get_redis_client,
    raise_redis_unavailable,
)
from app.core.state_protocols import RateLimiterProtocol

_SLIDING_WINDOW_LUA = """
local t = redis.call('TIME')
local now_ms = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local window_ms = tonumber(ARGV[1]) * 1000
local limit = tonumber(ARGV[2])
local cutoff = now_ms - window_ms
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_after = tonumber(ARGV[1])
  if #oldest >= 2 then
    local oldest_ms = tonumber(oldest[2])
    retry_after = math.max(1, math.ceil((oldest_ms + window_ms - now_ms) / 1000))
  end
  return {0, retry_after}
end
local seq = redis.call('INCR', KEYS[2])
redis.call('ZADD', KEYS[1], now_ms, tostring(now_ms) .. ':' .. tostring(seq))
redis.call('PEXPIRE', KEYS[1], window_ms + 1000)
redis.call('PEXPIRE', KEYS[2], window_ms + 1000)
return {1, 0}
""".strip()


class RedisRateLimiter:
    """Distributed atomic Lua sliding-window rate limiter backed by Redis."""

    def __init__(
        self,
        *,
        redis_client: RedisClientProtocol,
        namespace: str,
        window_seconds: int = 60,
        default_max_requests: int = 60,
        detail_message: Optional[str] = None,
        include_retry_after_header: bool = True,
    ) -> None:
        self._redis = redis_client
        self._namespace = namespace.strip() or "default"
        self._window_seconds = window_seconds
        self._default_max_requests = default_max_requests
        self._detail_message = detail_message
        self._include_retry_after_header = include_retry_after_header

    def _keys_for(self, actor_key: str) -> tuple[str, str]:
        normalized = (actor_key or "unknown").strip() or "unknown"
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        return (
            f"svario:rl:{self._namespace}:{digest}",
            f"svario:rl:{self._namespace}:{digest}:seq",
        )

    def check_and_record(
        self,
        actor_key: str,
        max_requests_per_window: Optional[int] = None,
    ) -> None:
        limit = (
            self._default_max_requests
            if max_requests_per_window is None
            else max_requests_per_window
        )
        zset_key, seq_key = self._keys_for(actor_key)
        try:
            result = self._redis.execute(
                [
                    "EVAL",
                    _SLIDING_WINDOW_LUA,
                    2,
                    zset_key,
                    seq_key,
                    str(self._window_seconds),
                    str(limit),
                ]
            )
        except RedisUnavailableError as exc:
            raise raise_redis_unavailable() from exc

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            raise raise_redis_unavailable()

        allowed = int(result[0])
        retry_after = max(1, int(result[1]))
        if allowed != 1:
            detail = self._detail_message or (
                f"Voice session rate limit exceeded ({limit} sessions "
                f"per {self._window_seconds}s). Please wait before starting a new voice session."
            )
            headers = {"Retry-After": str(retry_after)} if self._include_retry_after_header else None
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
                headers=headers,
            )

    def check(self, client_ip: str) -> None:
        """PublicWebsiteRateLimiter-compatible check method."""
        self.check_and_record(client_ip, self._default_max_requests)


class VoiceSessionRateLimiter:
    """In-memory sliding-window rate limiter protecting Realtime session creation."""

    def __init__(
        self,
        window_seconds: int = 60,
        *,
        max_tracked_keys: int = 10_000,
        num_lock_shards: int = 64,
    ) -> None:
        self._window_seconds = window_seconds
        self._max_tracked_keys = max(1, max_tracked_keys)
        self._buckets: Dict[str, Deque[float]] = {}
        self._shard_locks = [threading.Lock() for _ in range(max(1, num_lock_shards))]
        self._sweep_lock = threading.Lock()
        self._last_sweep_at = time.monotonic()

    def _lock_for(self, key: str) -> threading.Lock:
        idx = zlib.crc32(key.encode("utf-8", errors="ignore")) % len(self._shard_locks)
        return self._shard_locks[idx]

    def reset(self) -> None:
        """Clear all rate limit buckets (used in test suites)."""
        with self._sweep_lock:
            self._buckets.clear()
            self._last_sweep_at = time.monotonic()

    def _sweep_stale_keys(self, now: float) -> None:
        """Reclaim expired/empty buckets without resetting active windows."""
        if not self._sweep_lock.acquire(blocking=False):
            return
        try:
            cutoff = now - float(self._window_seconds)
            for key in list(self._buckets.keys()):
                with self._lock_for(key):
                    bucket = self._buckets.get(key)
                    if bucket is None:
                        continue
                    while bucket and bucket[0] <= cutoff:
                        bucket.popleft()
                    if not bucket:
                        self._buckets.pop(key, None)

            # Hard cap fallback if active unique keys exceed max_tracked_keys within one window
            if len(self._buckets) > self._max_tracked_keys:
                excess = len(self._buckets) - self._max_tracked_keys
                for key in list(self._buckets.keys())[:excess]:
                    with self._lock_for(key):
                        self._buckets.pop(key, None)

            self._last_sweep_at = now
        finally:
            self._sweep_lock.release()

    def check_and_record(self, actor_key: str, max_requests_per_window: int) -> None:
        """Verify `actor_key` is within `max_requests_per_window` and record the attempt."""
        now = time.monotonic()
        normalized_key = (actor_key or "unknown").strip() or "unknown"
        cutoff = now - float(self._window_seconds)

        with self._lock_for(normalized_key):
            bucket = self._buckets.get(normalized_key)
            if bucket is None:
                bucket = deque()
                self._buckets[normalized_key] = bucket

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_requests_per_window:
                retry_after = max(1, int(self._window_seconds - (now - bucket[0])))
                if not bucket:
                    self._buckets.pop(normalized_key, None)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Voice session rate limit exceeded ({max_requests_per_window} sessions "
                        f"per {self._window_seconds}s). Please wait before starting a new voice session."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.append(now)

        if (
            len(self._buckets) >= self._max_tracked_keys
            or (now - self._last_sweep_at) >= float(self._window_seconds)
        ):
            self._sweep_stale_keys(now)


_voice_rate_limiter = VoiceSessionRateLimiter(window_seconds=60)


def get_voice_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> RateLimiterProtocol:
    """Return the configured voice session rate limiter (Redis in prod, in-memory in dev/test)."""
    resolved = settings if isinstance(settings, Settings) else get_settings()
    redis_client = get_redis_client(resolved)
    if redis_client is not None:
        return RedisRateLimiter(
            redis_client=redis_client,
            namespace="voice",
            window_seconds=60,
            default_max_requests=resolved.voice_session_rate_limit_per_minute,
            include_retry_after_header=True,
        )
    if resolved.is_production:
        raise raise_redis_unavailable()
    return _voice_rate_limiter
