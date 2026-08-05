import pytest
from pydantic import ValidationError

from models.unified_response import TokenUsage, UnifiedResponse
from orchestrator.completion_status import attach_generation_budget
from orchestrator.generation_policy import GenerationPolicyError, resolve_generation_budget
from server.generation_service import resolve_request_budget
from server.schemas.requests import ChatRequest
from server.schemas.responses import ChatResponseDTO


def test_legacy_request_keeps_quick_profile():
    resolved = resolve_generation_budget(
        provider="deepseek",
        model="deepseek-v4-flash",
    )

    assert resolved.profile == "quick"
    assert resolved.effective_max_output_tokens == 2048
    assert resolved.effective_reasoning_mode == "thinking"
    assert resolved.effective_reasoning_effort == "high"


def test_balanced_profile_removes_global_2048_clamp():
    resolved = resolve_generation_budget(
        provider="deepseek",
        model="deepseek-v4-flash",
        generation={"profile": "balanced", "reasoning": {"mode": "auto"}},
    )

    assert resolved.effective_max_output_tokens == 8192
    assert resolved.retry_profile == "deep"


def test_profile_is_clamped_to_model_native_limit():
    resolved = resolve_generation_budget(
        provider="openai",
        model="gpt-4o-mini",
        generation={"profile": "extended"},
    )

    assert resolved.requested_max_output_tokens == 65536
    assert resolved.effective_max_output_tokens == 16384


def test_explicit_limit_above_model_limit_is_rejected_not_silently_clamped():
    with pytest.raises(GenerationPolicyError, match="exceeds the allowed maximum"):
        resolve_generation_budget(
            provider="openai",
            model="gpt-4o-mini",
            generation={"max_output_tokens": 20000},
        )


def test_fable_reasoning_cannot_be_disabled():
    with pytest.raises(GenerationPolicyError, match="does not allow reasoning to be disabled"):
        resolve_generation_budget(
            provider="claude",
            model="claude-fable-5",
            generation={"profile": "balanced", "reasoning": {"mode": "off"}},
        )


def test_profile_effort_falls_back_to_model_supported_maximum():
    resolved = resolve_generation_budget(
        provider="claude",
        model="claude-sonnet-5",
        generation={"profile": "extended"},
    )

    assert resolved.effective_reasoning_effort == "high"


def test_explicit_unsupported_reasoning_effort_is_rejected():
    with pytest.raises(GenerationPolicyError, match="unsupported"):
        resolve_generation_budget(
            provider="claude",
            model="claude-sonnet-5",
            generation={
                "profile": "extended",
                "reasoning": {"effort": "max"},
            },
        )


def test_legacy_and_new_generation_fields_conflict():
    with pytest.raises(ValidationError, match="generation and max_tokens"):
        ChatRequest(
            prompt="hello",
            provider="deepseek",
            model="deepseek-v4-flash",
            max_tokens=1000,
            generation={"profile": "balanced"},
        )


def test_length_response_is_exposed_as_incomplete_with_retry_profile():
    budget = resolve_generation_budget(
        provider="deepseek",
        model="deepseek-v4-flash",
        generation={"profile": "balanced"},
    )
    response = UnifiedResponse(
        request_id="req-length",
        text="Partial answer",
        provider="deepseek",
        model="deepseek-v4-flash",
        latency_ms=10,
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=8192, total_tokens=8202),
        estimated_cost=0.0,
        finish_reason="length",
    )
    annotated = attach_generation_budget(response, budget)
    dto = ChatResponseDTO.from_unified_response(annotated)

    assert dto.completion_status == "incomplete"
    assert dto.stop_cause == "token_limit"
    assert dto.generation_budget is not None
    assert dto.generation_budget.effective_max_output_tokens == 8192
    assert dto.retry_with_more_room.available is True
    assert dto.retry_with_more_room.recommended_profile == "deep"


def test_empty_reasoning_length_response_stays_billable_and_incomplete():
    budget = resolve_generation_budget(
        provider="deepseek",
        model="deepseek-v4-flash",
        generation={"profile": "balanced"},
    )
    response = UnifiedResponse(
        request_id="req-reasoning-length",
        text="",
        provider="deepseek",
        model="deepseek-v4-flash",
        latency_ms=10,
        token_usage=TokenUsage(
            prompt_tokens=10,
            completion_tokens=8192,
            total_tokens=8202,
            reasoning_tokens=8192,
        ),
        estimated_cost=0.0,
        finish_reason="length",
    )

    annotated = attach_generation_budget(response, budget)
    assert annotated.is_success
    assert annotated.metadata["reasoning_budget_exhausted"] is True


def test_rollout_switch_restores_quick_budget(monkeypatch):
    monkeypatch.setenv("GENERATION_BUDGET_POLICY_ENABLED", "false")

    resolved = resolve_request_budget(
        provider="deepseek",
        model="deepseek-v4-flash",
        generation={"profile": "extended"},
        legacy_max_tokens=None,
        input_text="hello",
    )

    assert resolved.profile == "quick"
    assert resolved.effective_max_output_tokens == 2048
