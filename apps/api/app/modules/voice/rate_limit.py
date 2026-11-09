"""Sliding-window rate limiter for Stage 3 voice session creation (`POST /api/v1/voice/sessions`)."""

import time
from collections import defaultdict, deque
from typing import Deque, Dict
from fastapi import HTTPException, status


class VoiceSessionRateLimiter:
    """In-memory sliding-window rate limiter protecting Realtime session creation."""

    def __init__(self, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        """Clear all rate limit buckets (used in test suites)."""
        self._buckets.clear()

    def check_and_record(self, actor_key: str, max_requests_per_window: int) -> None:
        """Verify `actor_key` is within `max_requests_per_window` and record the attempt."""
        now = time.monotonic()
        cutoff = now - float(self._window_seconds)
        bucket = self._buckets[actor_key]

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests_per_window:
            retry_after = max(1, int(self._window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Voice session rate limit exceeded ({max_requests_per_window} sessions "
                    f"per {self._window_seconds}s). Please wait before starting a new voice session."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)


_voice_rate_limiter = VoiceSessionRateLimiter(window_seconds=60)


def get_voice_rate_limiter() -> VoiceSessionRateLimiter:
    """Return the shared voice session rate limiter singleton."""
    return _voice_rate_limiter
