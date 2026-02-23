from config.pricing import ModelPricing
from orchestrator.model_registry import ModelRegistry
from utils.cost_calculator import CostCalculator


def test_all_enabled_registry_models_have_pricing():
    registry = ModelRegistry.from_yaml()
    missing: list[str] = []

    for candidate in registry.list_enabled_models():
        pricing = ModelPricing.get_model_pricing(candidate.provider, candidate.model_name)
        if pricing is None:
            missing.append(f"{candidate.provider}:{candidate.model_name}")

    assert missing == [], f"Missing pricing entries: {missing}"


def test_all_enabled_registry_model_prices_match_pricing_table():
    registry = ModelRegistry.from_yaml()
    mismatches: list[str] = []

    for candidate in registry.list_enabled_models():
        pricing = ModelPricing.get_model_pricing(candidate.provider, candidate.model_name)
        if pricing is None:
            mismatches.append(f"{candidate.provider}:{candidate.model_name}=missing")
            continue

        if (
            float(candidate.input_cost_per_1m) != float(pricing["input"])
            or float(candidate.output_cost_per_1m) != float(pricing["output"])
        ):
            mismatches.append(
                (
                    f"{candidate.provider}:{candidate.model_name} "
                    f"registry=({candidate.input_cost_per_1m},{candidate.output_cost_per_1m}) "
                    f"pricing=({pricing['input']},{pricing['output']})"
                )
            )

    assert mismatches == [], f"Registry/pricing mismatch: {mismatches}"


def test_unknown_model_pricing_fallback_is_zero_cost():
    calc = CostCalculator(model_type="openai", model_name="unknown-model-name")
    costs = calc.calculate_cost(prompt_tokens=1000, completion_tokens=500)
    assert costs == {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}
