"""Deterministic AI-credit calculations.

Credits are an integer accounting unit. Input and output components are
calculated and rounded up separately before fixed charges are added.
Provider reasoning tokens belong to output tokens before they reach this
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING

ADVANCED_WEB_SEARCH_CREDITS = 15_000


@dataclass(frozen=True)
class CreditCharge:
    input_tokens: int
    output_tokens: int
    input_credits: int
    output_credits: int
    fixed_credits: int
    total_credits: int
    estimated: bool = False


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
