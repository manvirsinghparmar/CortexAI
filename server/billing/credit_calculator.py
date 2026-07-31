"""Deterministic AI-credit calculations.

Credits are an integer accounting unit. Input and output components are
calculated and rounded up separately before fixed charges are added.
Provider reasoning tokens belong to output tokens before they reach this
module.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any

CORTEX_CREDITS_PER_TAVILY_CREDIT = 5_000
TAVILY_ADVANCED_SEARCH_CREDIT_ESTIMATE = 2
# Research preflight reserves the normal Advanced Search cost. Settlement uses
# the provider-reported usage instead of treating this as a flat fee.
ADVANCED_WEB_SEARCH_CREDITS = (
    CORTEX_CREDITS_PER_TAVILY_CREDIT * TAVILY_ADVANCED_SEARCH_CREDIT_ESTIMATE
)


@dataclass(frozen=True)
class CreditCharge:
    input_tokens: int
    output_tokens: int
    input_credits: int
    output_credits: int
    fixed_credits: int
    total_credits: int
    estimated: bool = False


@dataclass(frozen=True)
class ResearchCreditUsage:
    provider_credits_used: int
    cortex_credits: int
    estimated: bool = False


def calculate_research_credit_charge(provider_credits_used: int) -> int:
    """Convert Tavily API credits into Cortex AI credits."""
    if (
        isinstance(provider_credits_used, bool)
        or not isinstance(provider_credits_used, int)
        or provider_credits_used < 0
    ):
        raise ValueError("provider_credits_used must be a nonnegative integer")
    return provider_credits_used * CORTEX_CREDITS_PER_TAVILY_CREDIT


def research_credit_usage_from_metadata(
    metadata: Mapping[str, Any] | None,
) -> ResearchCreditUsage:
    """Resolve one turn's research charge from orchestration metadata.

    Older responses that only expose ``research_used`` retain a conservative
    two-credit fallback. Cached/reused research is always free for the turn.
    """
    if not isinstance(metadata, Mapping) or bool(metadata.get("research_reused")):
        return ResearchCreditUsage(0, 0, False)

    raw_credits = metadata.get("research_provider_credits_used")
    estimated = bool(metadata.get("research_provider_credits_estimated"))
    if isinstance(raw_credits, bool) or not isinstance(raw_credits, int) or raw_credits < 0:
        if not bool(metadata.get("research_used")):
            return ResearchCreditUsage(0, 0, False)
        raw_credits = TAVILY_ADVANCED_SEARCH_CREDIT_ESTIMATE
        estimated = True

    return ResearchCreditUsage(
        provider_credits_used=raw_credits,
        cortex_credits=calculate_research_credit_charge(raw_credits),
        estimated=estimated,
    )


def calculate_credit_charge(
    *,
    input_tokens: int,
    output_tokens: int,
    input_multiplier: float | Decimal,
    output_multiplier: float | Decimal,
    fixed_credits: int = 0,
    estimated: bool = False,
) -> CreditCharge:
    """Return the exact whole-credit charge for one billable operation."""
    for label, value in (
        ("input_tokens", input_tokens),
        ("output_tokens", output_tokens),
        ("fixed_credits", fixed_credits),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{label} must be a nonnegative integer")

    input_rate = _positive_decimal(input_multiplier, "input_multiplier")
    output_rate = _positive_decimal(output_multiplier, "output_multiplier")
    raw_input = Decimal(input_tokens) * input_rate
    raw_output = Decimal(output_tokens) * output_rate
    input_credits = int(raw_input.to_integral_value(rounding=ROUND_CEILING))
    output_credits = int(raw_output.to_integral_value(rounding=ROUND_CEILING))
    total = input_credits + output_credits + fixed_credits
    return CreditCharge(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_credits=input_credits,
        output_credits=output_credits,
        fixed_credits=fixed_credits,
        total_credits=total,
        estimated=estimated,
    )


def _positive_decimal(value: float | Decimal, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive number")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} must be a positive number") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{label} must be a positive number")
    return result
