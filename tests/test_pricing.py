import pytest

from config.pricing import ModelPricing
from utils.cost_calculator import CostCalculator


@pytest.mark.parametrize(
    ("provider", "model", "expected_input", "expected_output"),
    [
        ("openai", "gpt-5.1", 1.25, 10.00),
        ("openai", "gpt-5.2-codex", 1.75, 14.00),
        ("gemini", "gemini-2.5-flash-lite", 0.10, 0.40),
        ("gemini", "gemini-2.5-pro", 1.25, 10.00),
        ("deepseek", "deepseek-chat", 0.28, 0.42),
        ("grok", "grok-4-1-fast-non-reasoning", 0.20, 0.50),
    ],
)
def test_key_model_pricing_values(provider, model, expected_input, expected_output):
    pricing = ModelPricing.get_model_pricing(provider, model)
    assert pricing is not None
    assert pricing["input"] == pytest.approx(expected_input)
    assert pricing["output"] == pytest.approx(expected_output)


def test_get_model_pricing_provider_case_insensitive():
    upper = ModelPricing.get_model_pricing("OPENAI", "gpt-4o-mini")
    lower = ModelPricing.get_model_pricing("openai", "gpt-4o-mini")
    assert upper == lower
    assert upper == {"input": 0.15, "output": 0.60}


def test_all_pricing_entries_have_required_shape_and_non_negative_values():
    all_pricing = ModelPricing.list_all_pricing()
    assert set(all_pricing.keys()) == {"openai", "gemini", "deepseek", "grok"}

    for provider, models in all_pricing.items():
        assert models, f"{provider} pricing should not be empty"
        for model_name, prices in models.items():
            assert set(prices.keys()) == {"input", "output"}, f"Invalid keys for {model_name}"
            assert isinstance(prices["input"], int | float)
            assert isinstance(prices["output"], int | float)
            assert prices["input"] >= 0.0
            assert prices["output"] >= 0.0


def test_list_all_pricing_filtering_behavior():
    openai_only = ModelPricing.list_all_pricing("openai")
    assert set(openai_only.keys()) == {"openai"}
    assert "gpt-4o-mini" in openai_only["openai"]

    unknown = ModelPricing.list_all_pricing("unknown-provider")
    assert unknown == {"unknown-provider": {}}


def test_cost_calculator_calculates_expected_cost_from_pricing_table():
    calc = CostCalculator(model_type="openai", model_name="gpt-5.1")
    costs = calc.calculate_cost(prompt_tokens=1_000_000, completion_tokens=500_000)
    assert costs["input_cost"] == pytest.approx(1.25)
    assert costs["output_cost"] == pytest.approx(5.00)
    assert costs["total_cost"] == pytest.approx(6.25)


def test_cost_calculator_cumulative_tracking_is_consistent():
    calc = CostCalculator(model_type="gemini", model_name="gemini-2.5-flash-lite")
    calc.update_cumulative_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    calc.update_cumulative_cost(prompt_tokens=500_000, completion_tokens=0)

    totals = calc.get_cumulative_cost()
    assert totals["total_input_cost"] == pytest.approx(0.15)
    assert totals["total_output_cost"] == pytest.approx(0.40)
    assert totals["total_cost"] == pytest.approx(0.55)
