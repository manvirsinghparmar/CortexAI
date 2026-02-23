"""API rate limiting helpers."""

from __future__ import annotations

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, status


class InMemoryRateLimiter:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = int(window_seconds)
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, key: str, *, limit: int) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            events = self._events.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while events and events[0] < cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, int(self.window_seconds - (now - events[0])))
                return False, retry_after

            events.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_LIMITER = InMemoryRateLimiter(window_seconds=60)


def default_requests_per_minute() -> int:
    raw = os.getenv("REQUESTS_PER_MINUTE", "60")
    try:
        return max(0, int(raw))
    except Exception:
        return 60


def enforce_rate_limit(*, subject_key: str, requests_per_minute: int | None = None) -> None:
    rpm = default_requests_per_minute() if requests_per_minute is None else int(requests_per_minute)
    if rpm <= 0:
        return

    allowed, retry_after = _LIMITER.check_and_record(subject_key, limit=rpm)
    if allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "rate_limited",
            "message": f"Rate limit exceeded ({rpm} requests/minute)",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def reset_rate_limit_state() -> None:
    _LIMITER.reset()
