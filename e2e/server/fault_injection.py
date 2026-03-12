"""Request-scoped fallback fault injection used only by the Playwright E2E suite.

The patch is deliberately isolated to the E2E bootstrap process so production code
never needs to know about synthetic failures.
"""

from __future__ import annotations

import contextvars
import logging
import os
from dataclasses import dataclass

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from orchestrator.core import CortexOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class FaultSpec:
    """Parsed representation of one synthetic fault request."""

    kind: str
    attempt: int
    provider: str | None = None
    model: str | None = None
    consumed: bool = False
    current_attempt: int = 0


_fault_state: contextvars.ContextVar[FaultSpec | None] = contextvars.ContextVar(
    "cortexai_e2e_fault_state",
    default=None,
)


def _fault_enabled() -> bool:
    raw = str(os.getenv("E2E_ENABLE_FAULT_INJECTION", "false")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _parse_fault_spec(raw_value: str | None) -> FaultSpec | None:
    """Parse the `X-E2E-Fault` header into a structured fault description."""
    raw = str(raw_value or "").strip()
    if not raw:
        return None

    parts: dict[str, str] = {}
    for item in raw.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = value.strip()

    if parts.get("type") != "fail_attempt":
        return None

    try:
        attempt = int(parts.get("attempt", "0"))
    except Exception:
        attempt = 0

    provider = parts.get("provider")
    model = parts.get("model")
    return FaultSpec(
        kind="fail_attempt",
        attempt=max(attempt, 0),
        provider=provider.lower() if provider else None,
        model=model,
    )


class FaultHeaderMiddleware(BaseHTTPMiddleware):
    """Expose one parsed fault spec to the current request via a context variable."""

    async def dispatch(self, request: Request, call_next):
        spec = _parse_fault_spec(request.headers.get("X-E2E-Fault"))
        token = _fault_state.set(spec)
        try:
            return await call_next(request)
        finally:
            _fault_state.reset(token)


def install_fault_injection(app: FastAPI) -> None:
    """Monkeypatch the orchestrator candidate invocation path for deterministic fallback tests."""
    if not _fault_enabled():
        logger.info("E2E fault injection disabled")
        return

    if getattr(CortexOrchestrator, "_e2e_fault_patch_installed", False):
        return

    original_invoke = CortexOrchestrator._invoke_candidate

    def patched_invoke(self, candidate, messages, provider_api_keys=None, **kwargs):
        spec = _fault_state.get()
        if spec is not None:
            current_attempt = spec.current_attempt
            spec.current_attempt += 1

            provider_matches = spec.provider is None or candidate.provider == spec.provider
            model_matches = spec.model is None or candidate.model_name == spec.model
            if (
                not spec.consumed
                and spec.kind == "fail_attempt"
                and current_attempt == spec.attempt
                and provider_matches
                and model_matches
            ):
                spec.consumed = True
                logger.warning(
                    "Injecting E2E fallback fault for %s/%s at attempt %s",
                    candidate.provider,
                    candidate.model_name,
                    current_attempt,
                )
                return self._error_response(
                    provider=candidate.provider,
                    model=candidate.model_name,
                    message="E2E fault injection: forced first-attempt provider failure",
                    code="provider_error",
                    retryable=True,
                    details={
                        "e2e_fault": "fail_attempt",
                        "attempt": current_attempt,
                        "provider": candidate.provider,
                        "model": candidate.model_name,
                    },
                )

        return original_invoke(
            self,
            candidate,
            messages,
            provider_api_keys=provider_api_keys,
            **kwargs,
        )

    CortexOrchestrator._invoke_candidate = patched_invoke
    CortexOrchestrator._e2e_fault_patch_installed = True
    app.add_middleware(FaultHeaderMiddleware)
    logger.info("Installed E2E fault injection middleware and candidate patch")