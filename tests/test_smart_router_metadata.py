from models.user_context import UserContext
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


def test_runtime_messages_raise_context_estimate_and_tier_for_web_injection():
    router = _build_router()
    prompt = "give me a short summary"

    _, tier_without_runtime, _, metadata_without_runtime = router.route_once_plan(
        prompt=prompt,
        context=None,
        routing_mode="smart",
        constraints=None,
    )
    assert metadata_without_runtime["features"]["context_token_estimate"] == 0

    runtime_messages = [
        {"role": "system", "content": "SYSTEM RULES\n" + ("A" * 6000)},
        {"role": "system", "content": "WEB RESEARCH SOURCES:\n" + ("B" * 6000)},
        {"role": "user", "content": prompt},
    ]
    _, tier_with_runtime, _, metadata_with_runtime = router.route_once_plan(
        prompt=prompt,
        context=None,
        routing_mode="smart",
        constraints=None,
        runtime_messages=runtime_messages,
    )

    assert tier_without_runtime.value in {"T0", "T1"}
    assert tier_with_runtime.value in {"T2", "T3"}
    assert metadata_with_runtime["features"]["context_token_estimate"] >= 2200


def test_runtime_messages_preserve_higher_history_context_estimate():
    router = _build_router()
    context = UserContext(
        conversation_history=[
            {"role": "user", "content": "A" * 4000},
            {"role": "assistant", "content": "B" * 4000},
        ]
    )
    prompt = "summarize this"
    _, _, _, metadata = router.route_once_plan(
        prompt=prompt,
        context=context,
        routing_mode="smart",
        constraints=None,
        runtime_messages=[
            {"role": "system", "content": "small"},
            {"role": "user", "content": prompt},
        ],
    )
    assert metadata["features"]["context_token_estimate"] >= 1800


def test_runtime_messages_increase_prompt_token_estimate_from_user_message():
    router = _build_router()
    prompt = "tiny prompt"
    long_user = "word " * 700
    _, _, _, metadata = router.route_once_plan(
        prompt=prompt,
        context=None,
        routing_mode="smart",
        constraints=None,
        runtime_messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": long_user},
        ],
    )
    assert metadata["features"]["token_estimate"] >= 700


def test_runtime_messages_empty_list_does_not_change_estimates():
    router = _build_router()
    prompt = "simple answer please"
    _, _, _, baseline = router.route_once_plan(
        prompt=prompt,
        context=None,
        routing_mode="smart",
        constraints=None,
    )
    _, _, _, with_empty_runtime = router.route_once_plan(
        prompt=prompt,
        context=None,
        routing_mode="smart",
        constraints=None,
        runtime_messages=[],
    )
    assert (
        with_empty_runtime["features"]["context_token_estimate"]
        == baseline["features"]["context_token_estimate"]
    )
    assert with_empty_runtime["features"]["token_estimate"] == baseline["features"]["token_estimate"]


def test_runtime_messages_high_context_adds_long_context_selection_reasons():
    router = _build_router()
    prompt = "brief summary"
    _, _, _, metadata = router.route_once_plan(
        prompt=prompt,
        context=None,
        routing_mode="smart",
        constraints=None,
        runtime_messages=[
            {"role": "system", "content": "SYSTEM\n" + ("X" * 7000)},
            {"role": "system", "content": "WEB RESEARCH SOURCES:\n" + ("Y" * 7000)},
            {"role": "user", "content": prompt},
        ],
    )
    plan = metadata.get("candidate_plan", [])
    assert plan
    assert any(
        any(
            reason.startswith("long_context_")
            for reason in item.get("why_selected", [])
        )
        for item in plan
    )
