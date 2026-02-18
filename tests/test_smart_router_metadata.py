from orchestrator.fallback_manager import FallbackManager
from orchestrator.model_registry import ModelRegistry
from orchestrator.model_selector import ModelSelector, ReliabilityStore
from orchestrator.prompt_analyzer import PromptAnalyzer
from orchestrator.response_validator import ResponseValidator
from orchestrator.smart_router import SmartRouter
from orchestrator.tier_decider import TierDecider


def _build_router() -> SmartRouter:
    registry = ModelRegistry.from_yaml()
    thresholds = registry.routing_defaults().get("thresholds", {})
    return SmartRouter(
        registry=registry,
        selector=ModelSelector(reliability_store=ReliabilityStore(), token_buffer=200),
        validator=ResponseValidator(thresholds=thresholds),
        fallback_manager=FallbackManager(),
        analyzer=PromptAnalyzer(),
        decider=TierDecider(thresholds=thresholds),
    )


def test_route_metadata_includes_features_and_category_for_coding_prompt():
    router = _build_router()

    _, _, _, metadata = router.route_once_plan(
        prompt="Write Python code to parse JSON with error handling",
        context=None,
        routing_mode="smart",
        constraints=None,
    )

    assert metadata["prompt_category"] == "coding"
    assert metadata["features"]["intent"] == "code"


def test_route_metadata_detects_financial_prompt_category():
    router = _build_router()

    _, _, _, metadata = router.route_once_plan(
        prompt="Compare stock market returns and crypto portfolio volatility",
        context=None,
        routing_mode="smart",
        constraints=None,
    )

    assert metadata["prompt_category"] == "financial"
