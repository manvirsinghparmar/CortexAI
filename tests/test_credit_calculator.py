from decimal import Decimal

import pytest

from orchestrator.model_registry import ModelRegistry
from server.billing.credit_calculator import (
    ADVANCED_WEB_SEARCH_CREDITS,
    CORTEX_CREDITS_PER_TAVILY_CREDIT,
    TAVILY_ADVANCED_SEARCH_CREDIT_ESTIMATE,
    calculate_credit_charge,
    calculate_research_credit_charge,
    research_credit_usage_from_metadata,
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


def test_research_preflight_reserves_the_normal_advanced_search_cost():
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
    assert ADVANCED_WEB_SEARCH_CREDITS == (
        TAVILY_ADVANCED_SEARCH_CREDIT_ESTIMATE
        * CORTEX_CREDITS_PER_TAVILY_CREDIT
    )


@pytest.mark.parametrize(
    ("provider_credits", "expected_cortex_credits"),
    [(0, 0), (1, 5_000), (2, 10_000), (3, 15_000)],
)
def test_research_charge_scales_with_provider_usage(
    provider_credits,
    expected_cortex_credits,
):
    assert calculate_research_credit_charge(provider_credits) == expected_cortex_credits


def test_research_metadata_uses_reported_usage_and_never_charges_reuse():
    fresh = research_credit_usage_from_metadata(
        {
            "research_used": True,
            "research_reused": False,
            "research_provider_credits_used": 3,
            "research_provider_credits_estimated": False,
        }
    )
    reused = research_credit_usage_from_metadata(
        {
            "research_used": True,
            "research_reused": True,
            "research_provider_credits_used": 3,
        }
    )

    assert (fresh.provider_credits_used, fresh.cortex_credits, fresh.estimated) == (
        3,
        15_000,
        False,
    )
    assert (reused.provider_credits_used, reused.cortex_credits) == (0, 0)


def test_legacy_research_metadata_uses_marked_two_credit_fallback():
    usage = research_credit_usage_from_metadata(
        {"research_used": True, "research_reused": False}
    )
    assert usage.provider_credits_used == 2
    assert usage.cortex_credits == 10_000
    assert usage.estimated is True


def test_provider_usage_is_billable_even_when_no_sources_were_usable():
    usage = research_credit_usage_from_metadata(
        {
            "research_used": False,
            "research_reused": False,
            "research_provider_credits_used": 2,
            "research_provider_credits_estimated": False,
        }
    )
    assert usage.provider_credits_used == 2
    assert usage.cortex_credits == 10_000
    assert usage.estimated is False


@pytest.mark.parametrize("value", [-1, True, 1.5, "2"])
def test_research_calculator_rejects_invalid_provider_usage(value):
    with pytest.raises(ValueError, match="provider_credits_used"):
        calculate_research_credit_charge(value)


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
