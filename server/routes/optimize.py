"""POST /v1/optimize — optimize a prompt before sending to chat/compare."""

import asyncio
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

from server.dependencies import AuthResult, get_auth, get_orchestrator
from server.routes.session_auth import SessionScopedAuthGuard
from orchestrator.core import CortexOrchestrator
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
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
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
