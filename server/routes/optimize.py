"""POST /v1/optimize — optimize a prompt before sending to chat/compare."""

import asyncio
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional

from server.dependencies import get_orchestrator, get_api_key
from orchestrator.core import CortexOrchestrator
from utils.prompt_optimizer import PromptOptimizer

router = APIRouter(prefix="/v1", tags=["Optimize"])

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
    request: OptimizeRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key),
):
    """
    Optimize a prompt using the configured AI provider.

    When ENABLE_PROMPT_OPTIMIZATION=false in .env, returns the original prompt
    with was_optimized=false.  The UI toggle still calls this endpoint — the
    server flag acts as a server-side safety gate.
    """
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
