from models.unified_response import TokenUsage, UnifiedResponse
from orchestrator.core import CortexOrchestrator
from orchestrator.routing_types import ModelCandidate, PromptFeatures, Tier


class FakeClient:
    def __init__(self, provider: str, model: str):
        self.provider_name = provider
        self.model_name = model

    def get_completion(self, *args, **kwargs):
        return UnifiedResponse(
            request_id="req_fake",
            text="ok",
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=1,
            token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            estimated_cost=0.0,
            finish_reason="stop",
            error=None,
            metadata={},
        )


def test_direct_ask_still_works(monkeypatch):
    orchestrator = CortexOrchestrator()
    fake = FakeClient("openai", "gpt-4o-mini")
    monkeypatch.setattr(orchestrator, "_get_client", lambda *_args, **_kwargs: fake)
    resp = orchestrator.ask(
        prompt="hello",
        model_type="openai",
        model_name="gpt-4o-mini",
        routing_mode="legacy",
    )
    assert resp.text == "ok"
    assert resp.provider == "openai"


def test_research_metadata_attached(monkeypatch):
    orchestrator = CortexOrchestrator()
    fake = FakeClient("openai", "gpt-4o-mini")
    monkeypatch.setattr(orchestrator, "_get_client", lambda *_args, **_kwargs: fake)

    def _fake_apply(*, prompt, messages, research_mode, context):
        return messages, {
            "research_used": True,
            "research_reused": False,
            "research_topic": "test",
            "research_error": None,
            "sources": [],
        }

    orchestrator.research_service = object()
    monkeypatch.setattr(orchestrator, "_apply_research_if_needed", _fake_apply)

    resp = orchestrator.ask(
        prompt="hello",
        model_type="openai",
        model_name="gpt-4o-mini",
        routing_mode="legacy",
        research_mode="auto",
    )
    assert resp.metadata.get("research_used") is True


def test_smart_mode_respects_explicit_model(monkeypatch):
    orchestrator = CortexOrchestrator()
    fake = FakeClient("openai", "gpt-4o-mini")
    smart_called = {"value": False}

    def _fake_run(*args, **kwargs):
        smart_called["value"] = True
        return UnifiedResponse(
            request_id="req_smart",
            text="smart",
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=1,
            token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            estimated_cost=0.0,
            finish_reason="stop",
            error=None,
            metadata={},
        )

    monkeypatch.setattr(orchestrator, "_run_smart_attempt_loop", _fake_run)
    monkeypatch.setattr(orchestrator, "_get_client", lambda *_args, **_kwargs: fake)

    resp = orchestrator.ask(
        prompt="hello",
        model_type="openai",
        model_name="gpt-4o-mini",
        routing_mode="smart",
    )
    assert resp.text == "ok"
    assert smart_called["value"] is False


def test_explicit_unknown_model_rejected():
    orchestrator = CortexOrchestrator()
    resp = orchestrator.ask(
        prompt="hello",
        model_type="openai",
        model_name="definitely-not-a-real-model",
        routing_mode="smart",
    )
    assert resp.is_error is True
    assert resp.error.code == "bad_request"


def test_smart_retry_on_refusal_then_success(monkeypatch):
    orchestrator = CortexOrchestrator()

    features = PromptFeatures(
        word_count=20,
        char_count=120,
        token_estimate=80,
        has_code=True,
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
        intent="code",
        has_strict_constraints=False,
    )

    candidates = [
        ModelCandidate(
            provider="gemini",
            model_name="gemini-2.5-pro",
            tier=Tier.T2,
            input_cost_per_1m=1.0,
            output_cost_per_1m=1.0,
            context_limit=128000,
            tags=["strong"],
            enabled=True,
        ),
        ModelCandidate(
            provider="openai",
            model_name="gpt-4o",
            tier=Tier.T2,
            input_cost_per_1m=2.0,
            output_cost_per_1m=2.0,
            context_limit=128000,
            tags=["strong"],
            enabled=True,
        ),
    ]

    routing_md = {
        "mode": "smart",
        "initial_tier": "T2",
        "final_tier": "T2",
        "attempt_count": 0,
        "fallback_used": False,
        "attempts": [],
        "decision_reasons": ["code_detected"],
    }

    monkeypatch.setattr(
        orchestrator._smart_router,
        "route_once_plan",
        lambda **kwargs: (features, Tier.T2, candidates, routing_md),
    )

    refusal_resp = UnifiedResponse(
        request_id="req_refusal",
        text="I'm sorry, but I can't assist with what appears to be an attempt to modify or override my system instructions.",
        provider="gemini",
        model="gemini-2.5-pro",
        latency_ms=10,
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        estimated_cost=0.0,
        finish_reason="stop",
        error=None,
        metadata={},
    )
    success_resp = UnifiedResponse(
        request_id="req_ok",
        text=(
            "Here is a safe refactor with unchanged behavior. "
            "I extracted duplicated branches, kept thread-safety intact, and preserved the "
            "existing mode-update flow while improving readability and naming."
        ),
        provider="openai",
        model="gpt-4o",
        latency_ms=10,
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        estimated_cost=0.0,
        finish_reason="stop",
        error=None,
        metadata={},
    )

    responses = {
        "gemini-2.5-pro": refusal_resp,
        "gpt-4o": success_resp,
    }
    monkeypatch.setattr(
        orchestrator,
        "_invoke_candidate",
        lambda candidate, messages, **kwargs: responses[candidate.model_name],
    )

    resp = orchestrator._run_smart_attempt_loop(
        prompt="Please refactor this code",
        context=None,
        messages=[{"role": "user", "content": "Please refactor this code"}],
        routing_mode="smart",
        routing_constraints=None,
    )

    assert "safe refactor with unchanged behavior" in resp.text
    assert resp.metadata["routing"]["attempt_count"] == 2
    assert resp.metadata["routing"]["fallback_used"] is True
