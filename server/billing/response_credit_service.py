"""Resolve customer-facing AI-credit usage for response payloads and history."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

from orchestrator.model_registry import ModelRegistry
from server.billing.credit_calculator import (
    calculate_credit_charge,
    research_credit_usage_from_metadata,
)
from server.billing.credit_estimator import fallback_actual_tokens


@dataclass(frozen=True)
class ResponseCreditUsage:
    ai_credits: int
    credit_usage_estimated: bool
    research_ai_credits: int
    research_credit_usage_estimated: bool


@lru_cache(maxsize=1)
def _credit_registry() -> ModelRegistry:
    return ModelRegistry.from_yaml()


def calculate_response_credit_usage(
    *,
    provider: str,
    model: str,
    requested_model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    output_text: str = "",
    is_error: bool = False,
    metadata: Mapping[str, Any] | None = None,
    include_research_charge: bool = True,
) -> ResponseCreditUsage:
    """Calculate the exact response-card snapshot from persisted response inputs."""
    model_credits = 0
    model_usage_estimated = False
    if not is_error:
        candidate = _credit_registry().find_model(provider, requested_model or model)
        if candidate is None and requested_model and requested_model != model:
            candidate = _credit_registry().find_model(provider, model)
        if candidate is None:
            model_usage_estimated = True
        else:
            resolved_input_tokens = max(0, int(input_tokens or 0))
            resolved_output_tokens = max(0, int(output_tokens or 0))
            model_usage_estimated = resolved_input_tokens == 0 and resolved_output_tokens == 0
            if model_usage_estimated:
                resolved_input_tokens, resolved_output_tokens = fallback_actual_tokens(
                    input_text="",
                    output_text=output_text,
                )
            charge = calculate_credit_charge(
                input_tokens=resolved_input_tokens,
                output_tokens=resolved_output_tokens,
                input_multiplier=candidate.input_credit_multiplier,
                output_multiplier=candidate.output_credit_multiplier,
                estimated=model_usage_estimated,
            )
            model_credits = charge.total_credits

    research_usage = research_credit_usage_from_metadata(metadata)
    displayed_credits = model_credits
    if include_research_charge:
        displayed_credits += research_usage.cortex_credits

    return ResponseCreditUsage(
        ai_credits=displayed_credits,
        credit_usage_estimated=model_usage_estimated,
        research_ai_credits=research_usage.cortex_credits,
        research_credit_usage_estimated=research_usage.estimated,
    )


def resolve_response_credit_usage(
    response: object,
    *,
    include_research_charge: bool = True,
) -> ResponseCreditUsage:
    """Resolve a response-card snapshot from a UnifiedResponse-like object."""
    token_usage = getattr(response, "token_usage", None)
    metadata = getattr(response, "metadata", None)
    return calculate_response_credit_usage(
        provider=str(getattr(response, "provider", "") or ""),
        model=str(getattr(response, "model", "") or ""),
        requested_model=str(getattr(response, "requested_model", "") or ""),
        input_tokens=max(0, int(getattr(token_usage, "prompt_tokens", 0) or 0)),
        output_tokens=max(0, int(getattr(token_usage, "completion_tokens", 0) or 0)),
        output_text=str(getattr(response, "text", "") or ""),
        is_error=bool(getattr(response, "is_error", False)),
        metadata=metadata if isinstance(metadata, Mapping) else None,
        include_research_charge=include_research_charge,
    )
