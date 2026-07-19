"""POST /v1/optimize — optimize a prompt before sending to chat/compare."""

import asyncio
import os
import time
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from server import persistence as persistence_service
from server.billing.enforcement_service import ReservedRequestUsage
from server.billing.errors import enforcement_http_exception
from server.dependencies import AuthResult, get_auth
from server.routes.session_auth import SessionScopedAuthGuard
from server.schemas.requests import UserContextRequest
from utils.logger import get_logger
from utils.prompt_optimizer import PromptOptimizer

router = APIRouter(prefix="/v1", tags=["Optimize"])
logger = get_logger(__name__)
_SESSION_AUTH_GUARD = SessionScopedAuthGuard(
    route_label="Optimize",
    rejection_event="optimize.route.rejected.auth_mode",
    logger=logger,
)
API_DB_ENABLED = persistence_service.API_DB_ENABLED
_resolve_identity = persistence_service.resolve_identity
_reserve_subscription_usage = persistence_service.reserve_subscription_usage
_finalize_subscription_usage = persistence_service.finalize_subscription_usage
_release_subscription_usage = persistence_service.release_subscription_usage

# Singleton optimizer (created once, reused across requests)
_optimizer: PromptOptimizer | None = None


def _get_optimizer() -> PromptOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = PromptOptimizer()
    return _optimizer


OptimizationStatus = Literal[
    "optimized",
    "kept_original",
    "disabled",
    "timeout",
    "failed",
    "rejected",
]


def _optimizer_timeout_seconds() -> float:
    raw_value = os.getenv("PROMPT_OPTIMIZER_TIMEOUT_MS", "5000")
    try:
        timeout_ms = int(raw_value)
    except (TypeError, ValueError):
        timeout_ms = 5000
    return max(timeout_ms, 1) / 1000


def _optimizer_route_max_retries() -> int:
    raw_value = os.getenv("PROMPT_OPTIMIZER_ROUTE_MAX_RETRIES", "2")
    try:
        max_retries = int(raw_value)
    except (TypeError, ValueError):
        max_retries = 2
    return max(max_retries, 1)


def _status_from_optimizer_result(
    result: dict, original_prompt: str, optimized: str
) -> OptimizationStatus:
    error = result.get("error") if isinstance(result, dict) else None
    if not error and optimized.strip() != original_prompt.strip():
        return "optimized"
    if not error:
        return "kept_original"

    error_code = str(error.get("code") or "") if isinstance(error, dict) else ""
    error_message = str(error.get("message") or "") if isinstance(error, dict) else ""
    if error_code == "optimization_rejected" or "answer the prompt" in error_message.lower():
        return "rejected"
    return "failed"


def _fallback_reason_from_status(
    status: OptimizationStatus, result: dict | None = None
) -> str | None:
    if status == "optimized":
        return None
    if status == "kept_original":
        fallback_reason = result.get("fallback_reason") if isinstance(result, dict) else None
        if fallback_reason:
            return str(fallback_reason)
        return "already_clear"
    if status == "disabled":
        return "optimization_disabled"
    if status == "timeout":
        return "timeout"
    if status == "rejected":
        return "optimizer_output_rejected"

    error = result.get("error") if isinstance(result, dict) else None
    if isinstance(error, dict):
        return str(error.get("code") or "optimization_failed")
    return "optimization_failed"


def _reserve_optimization_usage(
    *,
    auth: AuthResult,
    request_id: str,
) -> ReservedRequestUsage:
    try:
        resolution = _resolve_identity(auth=auth, request_id=request_id)
        return _reserve_subscription_usage(
            user_id=resolution.user_id,
            request_id=request_id,
            operation_type="optimize",
            model_targets=(),
            research_enabled=False,
            optimization_enabled=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        http_error = enforcement_http_exception(exc)
        log = logger.exception if http_error.status_code >= 500 else logger.warning
        log(
            "Prompt optimization subscription preflight denied",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise http_error from exc


def _finalize_optimization_usage(reservation: ReservedRequestUsage) -> None:
    try:
        _finalize_subscription_usage(
            reservation=reservation,
            successful_targets=(),
            research_performed=False,
            optimization_performed=True,
        )
    except Exception as exc:
        logger.exception("Prompt optimization subscription finalization failed")
        raise enforcement_http_exception(exc) from exc


def _release_optimization_usage_safely(
    reservation: ReservedRequestUsage | None,
    *,
    reason: str,
) -> None:
    if reservation is None:
        return
    try:
        _release_subscription_usage(reservation=reservation, reason=reason)
    except Exception:
        logger.exception("Prompt optimization subscription release failed")


# ── Request / Response schemas (local to this route for simplicity) ──────────

class OptimizeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The raw user prompt to optimize")
    context_hint: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional compact conversation hint used only to resolve references in follow-up prompts.",
    )
    context: UserContextRequest | None = Field(
        default=None,
        description="Optional compact conversation context used only to resolve references in the latest prompt.",
    )


class OptimizeResponse(BaseModel):
    original_prompt: str
    optimized_prompt: str
    was_optimized: bool
    server_optimization_enabled: bool
    optimization_status: OptimizationStatus
    fallback_reason: str | None = None


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_prompt(
    http_request: Request,
    request: OptimizeRequest,
    auth: AuthResult = Depends(get_auth),
):
    """
    Optimize a prompt using the configured AI provider.

    When ENABLE_PROMPT_OPTIMIZATION=false in .env, returns the original prompt
    with was_optimized=false.  The UI toggle still calls this endpoint — the
    server flag acts as a server-side safety gate.
    """
    req_id = str(getattr(http_request.state, "request_id", "") or uuid4())
    started_at = time.monotonic()
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
    server_enabled = os.getenv("ENABLE_PROMPT_OPTIMIZATION", "false").lower() == "true"

    if not server_enabled:
        logger.info(
            "Prompt optimization skipped because server flag is disabled",
            extra={
                "extra_fields": {
                    "event": "optimize.route.completed",
                    "request_id": req_id,
                    "optimization_status": "disabled",
                    "fallback_reason": "optimization_disabled",
                    "duration_ms": int((time.monotonic() - started_at) * 1000),
                }
            },
        )
        return OptimizeResponse(
            original_prompt=request.prompt,
            optimized_prompt=request.prompt,
            was_optimized=False,
            server_optimization_enabled=False,
            optimization_status="disabled",
            fallback_reason="optimization_disabled",
        )

    billing_reservation: ReservedRequestUsage | None = None
    if API_DB_ENABLED:
        billing_reservation = _reserve_optimization_usage(
            auth=auth,
            request_id=req_id,
        )

    optimizer_invoked = False
    try:
        optimizer = _get_optimizer()
        timeout_seconds = _optimizer_timeout_seconds()
        max_retries = _optimizer_route_max_retries()
        payload = {
            "prompt": request.prompt,
            "max_retries": max_retries,
            "deadline_at": time.monotonic() + timeout_seconds,
        }
        if request.context_hint:
            payload["context_hint"] = request.context_hint
        if request.context:
            payload["context"] = request.context.model_dump(exclude_none=True)

        optimizer_invoked = True
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(optimizer.optimize_prompt, payload),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            logger.warning(
                "Prompt optimization timed out",
                extra={
                    "extra_fields": {
                        "event": "optimize.route.completed",
                        "request_id": req_id,
                        "provider": getattr(optimizer, "provider", None),
                        "model": getattr(optimizer, "model", None),
                        "optimization_status": "timeout",
                        "fallback_reason": "timeout",
                        "max_retries": max_retries,
                        "timeout_ms": int(timeout_seconds * 1000),
                        "duration_ms": duration_ms,
                    }
                },
            )
            return OptimizeResponse(
                original_prompt=request.prompt,
                optimized_prompt=request.prompt,
                was_optimized=False,
                server_optimization_enabled=True,
                optimization_status="timeout",
                fallback_reason="timeout",
            )

        if not isinstance(result, dict):
            result = {
                "optimized_prompt": request.prompt,
                "error": {
                    "code": "optimization_failed",
                    "message": "Optimizer returned an invalid response",
                },
            }

        optimized = str(result.get("optimized_prompt") or request.prompt)
        status = _status_from_optimizer_result(result, request.prompt, optimized)
        was_optimized = status == "optimized"
        fallback_reason = _fallback_reason_from_status(status, result)
        duration_ms = int((time.monotonic() - started_at) * 1000)

        logger.info(
            "Prompt optimization completed",
            extra={
                "extra_fields": {
                    "event": "optimize.route.completed",
                    "request_id": req_id,
                    "provider": getattr(optimizer, "provider", None),
                    "model": getattr(optimizer, "model", None),
                    "optimization_status": status,
                    "fallback_reason": fallback_reason,
                    "was_optimized": was_optimized,
                    "prompt_quality": result.get("prompt_quality"),
                    "attempt_count": result.get("attempt_count"),
                    "retry_reasons": result.get("retry_reasons"),
                    "unchanged_retry_used": result.get("unchanged_retry_used"),
                    "max_retries": max_retries,
                    "timeout_ms": int(timeout_seconds * 1000),
                    "duration_ms": duration_ms,
                }
            },
        )

        return OptimizeResponse(
            original_prompt=request.prompt,
            optimized_prompt=optimized,
            was_optimized=was_optimized,
            server_optimization_enabled=True,
            optimization_status=status,
            fallback_reason=fallback_reason,
        )
    finally:
        if billing_reservation is not None:
            if optimizer_invoked:
                _finalize_optimization_usage(billing_reservation)
            else:
                _release_optimization_usage_safely(
                    billing_reservation,
                    reason="optimizer_setup_failed_before_invocation",
                )
