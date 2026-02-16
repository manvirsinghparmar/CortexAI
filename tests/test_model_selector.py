from orchestrator.model_selector import ModelSelector
from orchestrator.routing_types import ModelCandidate, PromptFeatures, RoutingConstraints, Tier


def _features(**overrides) -> PromptFeatures:
    base = PromptFeatures(
        word_count=30,
        char_count=200,
        token_estimate=120,
        has_code=False,
        has_math=False,
        has_analysis=False,
        has_creative=False,
        has_factual=False,
        strict_format=False,
        has_logs_stacktrace=False,
        context_token_estimate=0,
        context_messages=0,
        is_follow_up=False,
        needs_latest_info=False,
        needs_accuracy=False,
        intent="general",
        has_strict_constraints=False,
    )
    return PromptFeatures(**{**base.__dict__, **overrides})


def test_prefers_coding_tag_for_code_prompt():
    selector = ModelSelector()
    features = _features(has_code=True, intent="code")
    candidates = [
        ModelCandidate(
            provider="gemini",
            model_name="cheap-non-reasoning",
            tier=Tier.T2,
            input_cost_per_1m=0.1,
            output_cost_per_1m=0.2,
            context_limit=128000,
            tags=["cheap", "non_reasoning"],
            enabled=True,
        ),
        ModelCandidate(
            provider="openai",
            model_name="coding-model",
            tier=Tier.T2,
            input_cost_per_1m=0.3,
            output_cost_per_1m=0.6,
            context_limit=128000,
            tags=["coding", "reasoning"],
            enabled=True,
        ),
    ]
    result = selector.select(features, candidates)
    assert result.primary_candidate.model_name == "coding-model"


def test_respects_max_cost_constraint_when_possible():
    selector = ModelSelector()
    features = _features(token_estimate=80)
    constraints = RoutingConstraints(max_cost_usd=0.0002)
    candidates = [
        ModelCandidate(
            provider="openai",
            model_name="expensive",
            tier=Tier.T1,
            input_cost_per_1m=10.0,
            output_cost_per_1m=20.0,
            context_limit=128000,
            tags=["balanced"],
            enabled=True,
        ),
        ModelCandidate(
            provider="gemini",
            model_name="affordable",
            tier=Tier.T1,
            input_cost_per_1m=0.1,
            output_cost_per_1m=0.2,
            context_limit=128000,
            tags=["cheap", "non_reasoning"],
            enabled=True,
        ),
    ]
    result = selector.select(features, candidates, constraints=constraints)
    assert result.primary_candidate.model_name == "affordable"
