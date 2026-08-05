"""FastAPI-facing helpers for generation policy resolution."""

from __future__ import annotations

import os

from fastapi import HTTPException, status

from models.unified_response import UnifiedResponse
from orchestrator.completion_status import attach_generation_budget
from orchestrator.generation_policy import (
    GenerationBudgetResolution,
    GenerationPolicyError,
    resolve_generation_budget,
)
from orchestrator.model_registry import ModelRegistry


def generation_budget_policy_enabled() -> bool:
    """Return the rollout switch for provider-aware generation budgets."""
    return os.getenv("GENERATION_BUDGET_POLICY_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def estimated_tokens_from_text(value: str) -> int:
    return max(1, (len(str(value or "")) + 3) // 4)


def resolve_request_budget(
    *,
    provider: str,
    model: str,
    generation: object | None,
    legacy_max_tokens: int | None,
    input_text: str,
    registry: ModelRegistry | None = None,
) -> GenerationBudgetResolution:
    if not generation_budget_policy_enabled():
        # Operational rollback: keep the historical Quick/2K ceiling without
        # changing request schemas or provider adapters.
        generation = None
        legacy_max_tokens = min(int(legacy_max_tokens), 2_048) if legacy_max_tokens else None
    try:
        return resolve_generation_budget(
            provider=provider,
            model=model,
            generation=generation,
            legacy_max_tokens=legacy_max_tokens,
            estimated_input_tokens=estimated_tokens_from_text(input_text),
            registry=registry,
        )
    except GenerationPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_generation_budget",
                "message": str(exc),
                "provider": str(provider or ""),
                "model": str(model or ""),
            },
        ) from exc


def annotate_response(
    response: UnifiedResponse,
    resolution: GenerationBudgetResolution,
) -> UnifiedResponse:
    return attach_generation_budget(response, resolution)
