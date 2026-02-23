"""Provider/model circuit breaker for failure isolation and fallback safety."""

from __future__ import annotations

import os
import threading
import time
from collections import deque

from models.unified_response import UnifiedResponse


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def failure_threshold() -> int:
    return max(1, _int_env("CIRCUIT_FAILURE_THRESHOLD", 5))


def window_seconds() -> int:
    return max(1, _int_env("CIRCUIT_WINDOW_SECONDS", 60))


def cooldown_seconds() -> int:
    return max(1, _int_env("CIRCUIT_COOLDOWN_SECONDS", 120))


def _key(provider: str, model: str) -> str:
    return f"{(provider or '').strip().lower()}:{(model or '').strip()}"


class CircuitBreakerStore:
    def __init__(self):
        self._state: dict[str, dict[str, object]] = {}
        self._lock = threading.Lock()

    def _prune(self, failures: deque[float], *, now: float, window_s: int) -> None:
        cutoff = now - window_s
        while failures and failures[0] < cutoff:
            failures.popleft()

    def allow(self, provider: str, model: str) -> bool:
        now = time.time()
        key = _key(provider, model)
        with self._lock:
            item = self._state.get(key)
            if not item:
                return True
            open_until = float(item.get("open_until") or 0.0)
            if open_until <= now:
                item["open_until"] = 0.0
                return True
            return False

    def record_success(self, provider: str, model: str) -> None:
        key = _key(provider, model)
        with self._lock:
            item = self._state.setdefault(key, {"failures": deque(), "open_until": 0.0})
            failures = item["failures"]
            if isinstance(failures, deque):
                failures.clear()
            item["open_until"] = 0.0

    def record_failure(self, provider: str, model: str) -> None:
        now = time.time()
        key = _key(provider, model)
        threshold = failure_threshold()
        window_s = window_seconds()
        cooldown_s = cooldown_seconds()
        with self._lock:
            item = self._state.setdefault(key, {"failures": deque(), "open_until": 0.0})
            failures = item["failures"]
            if not isinstance(failures, deque):
                failures = deque()
                item["failures"] = failures
            failures.append(now)
            self._prune(failures, now=now, window_s=window_s)
            if len(failures) >= threshold:
                item["open_until"] = now + cooldown_s
                failures.clear()

    def record_response(self, response: UnifiedResponse) -> None:
        if response.is_error:
            self.record_failure(response.provider, response.model)
        else:
            self.record_success(response.provider, response.model)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_BREAKER = CircuitBreakerStore()


def circuit_allows(provider: str, model: str) -> bool:
    return _BREAKER.allow(provider, model)


def record_success(provider: str, model: str) -> None:
    _BREAKER.record_success(provider, model)


def record_failure(provider: str, model: str) -> None:
    _BREAKER.record_failure(provider, model)


def record_response(response: UnifiedResponse) -> None:
    _BREAKER.record_response(response)


def reset_circuit_breakers() -> None:
    _BREAKER.reset()
