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


def test_unknown_model_pricing_fallback_is_zero_cost():
    calc = CostCalculator(model_type="openai", model_name="unknown-model-name")
    costs = calc.calculate_cost(prompt_tokens=1000, completion_tokens=500)
    assert costs == {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}
