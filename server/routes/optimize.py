"""POST /v1/optimize — optimize a prompt before sending to chat/compare."""

import asyncio
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import Optional

from server.dependencies import AuthResult, get_auth, get_orchestrator
from orchestrator.core import CortexOrchestrator
from utils.logger import get_logger
from utils.prompt_optimizer import PromptOptimizer

router = APIRouter(prefix="/v1", tags=["Optimize"])
logger = get_logger(__name__)

# Singleton optimizer (created once, reused across requests)
_optimizer: Optional[PromptOptimizer] = None


def _get_optimizer() -> PromptOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = PromptOptimizer()
    return _optimizer


# ── Request / Response schemas (local to this route for simplicity) ──────────

class OptimizeRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The raw user prompt to optimize")


class OptimizeResponse(BaseModel):
    original_prompt: str
    optimized_prompt: str
    was_optimized: bool
    server_optimization_enabled: bool


def _auth_mode(auth: AuthResult) -> str:
    if auth.user_id is not None:
        return "session_cookie"
    if auth.is_cognito:
        return "cognito"
    if auth.api_key_or_none():
        return "api_key"
    return "unknown"


def _require_session_scoped_auth(*, auth: AuthResult, request_id: str) -> None:
    """
    Optimize route is session-scoped to user identity and must not use API-key auth.
    """
    if auth.user_id is not None or auth.is_cognito:
        return
    logger.warning(
        "Optimize route rejected non-session auth",
        extra={
            "extra_fields": {
                "event": "optimize.route.rejected.auth_mode",
                "request_id": request_id,
                "auth_mode": _auth_mode(auth),
            }
        },
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "session_auth_required",
            "message": (
                "Optimize routes require session-based auth "
                "(cortex_session cookie or Authorization: Bearer)."
            ),
        },
    )


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_prompt(
    http_request: Request,
    request: OptimizeRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    auth: AuthResult = Depends(get_auth),
):
    """
    Optimize a prompt using the configured AI provider.

    When ENABLE_PROMPT_OPTIMIZATION=false in .env, returns the original prompt
    with was_optimized=false.  The UI toggle still calls this endpoint — the
    server flag acts as a server-side safety gate.
    """
    req_id = str(getattr(http_request.state, "request_id", "") or uuid4())
    _require_session_scoped_auth(auth=auth, request_id=req_id)
    server_enabled = os.getenv("ENABLE_PROMPT_OPTIMIZATION", "false").lower() == "true"

    if not server_enabled:
        return OptimizeResponse(
            original_prompt=request.prompt,
            optimized_prompt=request.prompt,
            was_optimized=False,
            server_optimization_enabled=False,
        )

    optimizer = _get_optimizer()
    optimized, was_optimized = await asyncio.to_thread(
        optimizer.optimize,
        request.prompt,
        orchestrator,
    )

    return OptimizeResponse(
        original_prompt=request.prompt,
        optimized_prompt=optimized,
        was_optimized=was_optimized,
        server_optimization_enabled=True,
    )
