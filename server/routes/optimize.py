"""POST /v1/optimize — optimize a prompt before sending to chat/compare."""

import asyncio
import os
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

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
    raw_value = os.getenv("PROMPT_OPTIMIZER_TIMEOUT_MS", "6000")
    try:
        timeout_ms = int(raw_value)
    except (TypeError, ValueError):
        timeout_ms = 6000
    return max(timeout_ms, 1) / 1000


def _optimizer_route_max_retries() -> int:
    raw_value = os.getenv("PROMPT_OPTIMIZER_ROUTE_MAX_RETRIES", "1")
    try:
        max_retries = int(raw_value)
    except (TypeError, ValueError):
        max_retries = 1
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


# ── Request / Response schemas (local to this route for simplicity) ──────────

class OptimizeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The raw user prompt to optimize")
    context_hint: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional compact conversation hint used only to resolve references in follow-up prompts.",
    )
    context: UserContextRequest | None = Field(
        default=None,
        description="Optional compact conversation context. The UI sends this only for follow-up-like prompts.",
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
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
    server_enabled = os.getenv("ENABLE_PROMPT_OPTIMIZATION", "false").lower() == "true"

    if not server_enabled:
        return OptimizeResponse(
            original_prompt=request.prompt,
            optimized_prompt=request.prompt,
            was_optimized=False,
            server_optimization_enabled=False,
            optimization_status="disabled",
            fallback_reason="optimization_disabled",
        )

    optimizer = _get_optimizer()
    payload = {
        "prompt": request.prompt,
        "max_retries": _optimizer_route_max_retries(),
    }
    if request.context_hint:
        payload["context_hint"] = request.context_hint
    if request.context:
        payload["context"] = request.context.model_dump(exclude_none=True)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(optimizer.optimize_prompt, payload),
            timeout=_optimizer_timeout_seconds(),
        )
    except asyncio.TimeoutError:
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

    return OptimizeResponse(
        original_prompt=request.prompt,
        optimized_prompt=optimized,
        was_optimized=was_optimized,
        server_optimization_enabled=True,
        optimization_status=status,
        fallback_reason=_fallback_reason_from_status(status, result),
    )
