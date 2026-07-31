"""Conservative preflight estimates and missing-usage fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from orchestrator.routing_types import ModelCandidate
from server.billing.credit_calculator import (
    ADVANCED_WEB_SEARCH_CREDITS,
    CreditCharge,
    calculate_credit_charge,
)

DEFAULT_MAX_OUTPUT_TOKENS = 2_048


@dataclass(frozen=True)
class CreditEstimate:
    charge: CreditCharge
    input_tokens: int
    output_tokens: int


def estimate_text_tokens(text: str) -> int:
    """Use a deterministic conservative approximation when no tokenizer is available."""
    normalized = str(text or "")
    return max(1, ceil(len(normalized.encode("utf-8")) / 3)) if normalized else 0


def estimate_model_credits(
    candidate: ModelCandidate,
    *,
    input_text: str,
    max_output_tokens: int | None,
    include_research: bool = False,
) -> CreditEstimate:
    output_tokens = max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS
    if isinstance(output_tokens, bool) or output_tokens <= 0:
        raise ValueError("max_output_tokens must be positive")
    input_tokens = estimate_text_tokens(input_text)
    charge = calculate_credit_charge(
        input_tokens=input_tokens,
        output_tokens=int(output_tokens),
        input_multiplier=candidate.input_credit_multiplier,
        output_multiplier=candidate.output_credit_multiplier,
        fixed_credits=ADVANCED_WEB_SEARCH_CREDITS if include_research else 0,
        estimated=True,
    )
    return CreditEstimate(
        charge=charge,
        input_tokens=input_tokens,
        output_tokens=int(output_tokens),
    )


def fallback_actual_tokens(
    *,
    input_text: str,
    output_text: str,
) -> tuple[int, int]:
    """Conservatively estimate actual tokens when a provider omits usage."""
    return estimate_text_tokens(input_text), estimate_text_tokens(output_text)
