"""FastAPI-facing helpers for generation policy resolution."""

from __future__ import annotations

import os
from dataclasses import replace

from fastapi import HTTPException, status

from config.cache_optimization import credit_aware_generation_budget_enabled
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
        legacy_max_tokens = min(int(legacy_max_tokens), 2_048) if legacy_max_tokens else 2_048
        try:
            resolved = resolve_generation_budget(
                provider=provider,
                model=model,
                generation=None,
                legacy_max_tokens=legacy_max_tokens,
                estimated_input_tokens=estimated_tokens_from_text(input_text),
                input_text=input_text,
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
        return replace(resolved, profile="quick", policy_version="generation-budget-v1-rollback")
    try:
        return resolve_generation_budget(
            provider=provider,
            model=model,
            generation=generation,
            legacy_max_tokens=legacy_max_tokens,
            estimated_input_tokens=estimated_tokens_from_text(input_text),
            input_text=input_text,
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


def constrain_budget_to_reservation(
    resolution: GenerationBudgetResolution,
    reservation: object | None,
    *,
    provider: str,
    model: str,
) -> GenerationBudgetResolution:
    """Apply the preflight-affordable ceiling to provider execution metadata."""

    if not credit_aware_generation_budget_enabled() or reservation is None:
        return resolution
    estimates = tuple(getattr(reservation, "model_estimates", ()) or ())
    match = next(
        (
            item
            for item in estimates
            if str(getattr(item, "provider", "")) == str(provider)
            and str(getattr(item, "model", "")) == str(model)
        ),
        None,
    )
    if match is None and len(estimates) == 1:
        match = estimates[0]
    affordable = int(getattr(match, "output_tokens", 0) or 0) if match else 0
    if affordable <= 0 or affordable >= resolution.effective_max_output_tokens:
        return resolution
    return replace(resolution, effective_max_output_tokens=affordable)
