from decimal import Decimal

import pytest

from orchestrator.model_registry import ModelRegistry
from server.billing.credit_calculator import (
    ADVANCED_WEB_SEARCH_CREDITS,
    calculate_credit_charge,
)
from server.billing.credit_estimator import estimate_model_credits, estimate_text_tokens


def test_input_and_output_credits_use_independent_multipliers_and_round_up():
    charge = calculate_credit_charge(
        input_tokens=3,
        output_tokens=2,
        input_multiplier=Decimal("0.25"),
        output_multiplier=Decimal("1.5"),
        fixed_credits=7,
    )

    assert charge.input_credits == 1
    assert charge.output_credits == 3
    assert charge.fixed_credits == 7
    assert charge.total_credits == 11


def test_reasoning_tokens_are_billed_as_output_tokens_by_contract():
    # Provider adapters aggregate reasoning into completion_tokens; the credit
    # calculator deliberately has no discounted reasoning category.
    charge = calculate_credit_charge(
        input_tokens=100,
        output_tokens=400,
        input_multiplier=1,
        output_multiplier=4,
    )
    assert charge.input_credits == 100
    assert charge.output_credits == 1_600
    assert charge.total_credits == 1_700


def test_fractional_input_and_output_components_each_round_up():
    charge = calculate_credit_charge(
        input_tokens=1,
        output_tokens=1,
        input_multiplier=Decimal("0.25"),
        output_multiplier=Decimal("0.25"),
    )

    assert charge.input_credits == 1
    assert charge.output_credits == 1
    assert charge.total_credits == 2


def test_research_fee_is_fixed_and_applied_once_per_estimate():
    candidate = ModelRegistry.from_yaml().find_model("openai", "gpt-4.1-mini")
    assert candidate is not None
    without_search = estimate_model_credits(
        candidate,
        input_text="hello",
        max_output_tokens=100,
    )
    with_search = estimate_model_credits(
        candidate,
        input_text="hello",
        max_output_tokens=100,
        include_research=True,
    )
    assert (
        with_search.charge.total_credits - without_search.charge.total_credits
        == ADVANCED_WEB_SEARCH_CREDITS
    )


def test_text_estimator_is_deterministic_and_conservative():
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("abcdef") == 2
    assert estimate_text_tokens("abcdef") == estimate_text_tokens("abcdef")


def test_every_enabled_model_is_calibrated_below_one_dollar_per_million_credits():
    for candidate in ModelRegistry.from_yaml().list_models(include_disabled=False):
        assert (
            candidate.input_cost_per_1m / candidate.input_credit_multiplier <= 1
        ), candidate.model_name
        assert (
            candidate.output_cost_per_1m / candidate.output_credit_multiplier <= 1
        ), candidate.model_name


@pytest.mark.parametrize(
    "field",
    ["input_tokens", "output_tokens", "fixed_credits"],
)
def test_credit_calculator_rejects_negative_accounting_inputs(field):
    values = {
        "input_tokens": 1,
        "output_tokens": 1,
        "fixed_credits": 0,
    }
    values[field] = -1
    with pytest.raises(ValueError, match=field):
        calculate_credit_charge(
            **values,
            input_multiplier=1,
            output_multiplier=1,
        )
