from models.unified_response import TokenUsage, UnifiedResponse
from orchestrator.response_validator import ResponseValidator
from orchestrator.routing_types import PromptFeatures, RoutingConstraints


def _base_features(**overrides):
    base = PromptFeatures(
        word_count=10,
        char_count=50,
        token_estimate=50,
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
    return base.__class__(**{**base.__dict__, **overrides})


def _response(text: str, finish_reason: str | None = None):
    return UnifiedResponse(
        request_id="req_1",
        text=text,
        provider="openai",
        model="gpt-4o-mini",
        latency_ms=1,
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        estimated_cost=0.0,
        finish_reason=finish_reason,
        error=None,
        metadata={},
    )


def test_json_only_violation():
    validator = ResponseValidator()
    features = _base_features()
    constraints = RoutingConstraints(json_only=True)
    result = validator.validate(features, constraints, _response("not json"))
    assert result.ok is False
    assert result.reason == "format_violation"


def test_strict_format_does_not_require_json():
    validator = ResponseValidator()
    features = _base_features(strict_format=True)
    result = validator.validate(features, None, _response("plain text " * 20))
    assert result.ok is True


def test_too_short_complex():
    validator = ResponseValidator()
    features = _base_features(has_analysis=True)
    result = validator.validate(features, None, _response("too short"))
    assert result.ok is False
    assert result.reason == "too_short"


def test_truncated_length_on_complex():
    validator = ResponseValidator()
    features = _base_features(has_analysis=True)
    result = validator.validate(features, None, _response("content", finish_reason="length"))
    assert result.ok is False
    assert result.reason == "truncated"


def test_refusal_is_invalid():
    validator = ResponseValidator()
    features = _base_features(has_code=True)
    refusal = "I'm sorry, but I can't assist with what appears to be an attempt to modify or override my system instructions."
    result = validator.validate(features, None, _response(refusal))
    assert result.ok is False
    assert result.reason == "refusal"
