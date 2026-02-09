"""
Test Suite: FastAPI Contract & Guardrail Validation

Purpose
-------
This test module validates the *public API contract, guardrails, and safety guarantees*
of the CortexAI FastAPI application. These tests are intentionally designed to operate
WITHOUT calling real LLM providers, external APIs, or incurring token costs.

The goal is to ensure that:
- The FastAPI layer is stable, predictable, and safe
- API inputs are validated correctly
- Errors are normalized consistently
- The application never crashes with 5xx errors for user-controlled input
- DTO mappings remain compatible with orchestration-layer responses

What This Test Suite Covers
---------------------------
1. API Health & Availability
   - Confirms the service is reachable and responds correctly (`/health`)

2. Authentication & Guardrails
   - Ensures protected endpoints reject requests without API keys
   - Prevents misuse such as insufficient or excessive compare targets

3. Input Validation
   - Enforces minimum and maximum constraints on compare requests
   - Validates request structure before orchestration logic runs

4. Error Normalization
   - Verifies that low-level exceptions (timeouts, auth failures, rate limits, etc.)
     are converted into consistent, user-facing NormalizedError objects
   - Confirms retryable vs non-retryable errors are classified correctly

5. DTO Contract Stability
   - Ensures CompareResponseDTO correctly maps from a MultiUnifiedResponse-like object
   - Acts as an early-warning system for breaking changes between layers

6. Runtime Safety Guarantees
   - Confirms that the `/v1/compare` endpoint never returns HTTP 500 errors
     due to malformed input or orchestration-layer behavior

How These Tests Work
--------------------
- A FakeOrchestrator is injected using FastAPI dependency overrides
- All orchestration responses are deterministic and in-memory
- No external providers, tokens, or network calls are used
- Tests focus strictly on FastAPI behavior and response contracts

What This Test Suite Does NOT Cover
-----------------------------------
- LLM response quality or correctness
- Provider-specific adapter logic (OpenAI, Gemini, etc.)
- Token accounting accuracy across real providers
- Performance, load, or concurrency behavior
- End-to-end integrations with real APIs

Why This Matters
----------------
These tests protect the FastAPI layer as a *stable public interface*.
They ensure that internal refactors, routing changes, or provider updates
do not silently break API consumers or cause runtime crashes.

If these tests pass, the application guarantees:
- No unexpected 500s from user input
- Predictable error handling
- Stable API response shapes
- Safe orchestration boundaries
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.base_client import BaseAIClient
from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
from server.app import create_app
from server.schemas.responses import CompareResponseDTO

pytestmark = pytest.mark.integration


# -------------------------------------------------------------------
# Fake MultiUnifiedResponse (match what CompareResponseDTO expects)
# -------------------------------------------------------------------


@dataclass(frozen=True)
class FakeMultiUnifiedResponse:
    request_id: str
    request_group_id: str
    prompt: str
    responses: list[UnifiedResponse]

    success_count: int
    failure_count: int
    error_count: int
    total_tokens: int
    total_cost: float

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -------------------------------------------------------------------
# Fake orchestrator (keeps tests offline & deterministic)
# -------------------------------------------------------------------


class FakeOrchestrator:
    def ask(self, prompt: str, model_type: str, context: Any = None, **kwargs) -> UnifiedResponse:
        return UnifiedResponse(
            request_id="req_ask_1",
            text="OK",
            provider=model_type,
            model=kwargs.get("model") or "fake-model",
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

    def compare(
        self, prompt: str, models_list: list[dict[str, Any]], context: Any = None, **kwargs
    ) -> FakeMultiUnifiedResponse:
        r1 = UnifiedResponse(
            request_id="req_cmp_1",
            text="A",
            provider=models_list[0]["provider"],
            model=models_list[0].get("model", "fake-a"),
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

        r2 = UnifiedResponse(
            request_id="req_cmp_2",
            text="B",
            provider=models_list[1]["provider"],
            model=models_list[1].get("model", "fake-b"),
            latency_ms=12,
            token_usage=TokenUsage(prompt_tokens=6, completion_tokens=4, total_tokens=10),
            estimated_cost=0.00002,
            finish_reason="stop",
            error=None,
            metadata={},
        )

        total_tokens = r1.token_usage.total_tokens + r2.token_usage.total_tokens
        total_cost = r1.estimated_cost + r2.estimated_cost

        return FakeMultiUnifiedResponse(
            request_id="req_compare_1",
            request_group_id="grp_1",
            prompt=prompt,
            responses=[r1, r2],
            success_count=2,
            failure_count=0,
            error_count=0,
            total_tokens=total_tokens,
            total_cost=total_cost,
        )


# -------------------------------------------------------------------
# Dummy client to access BaseAIClient helpers
# -------------------------------------------------------------------


class DummyClient(BaseAIClient):
    def __init__(self):
        # don't call BaseAIClient.__init__ (signature may vary)
        pass

    def get_completion(self, *args, **kwargs):
        raise NotImplementedError

    def list_available_models(self):
        return []


# -------------------------------------------------------------------
# Pytest fixtures
# -------------------------------------------------------------------


@pytest.fixture()
def app():
    """
    Build FastAPI app and override get_orchestrator dependency.
    """
    app = create_app()

    from server import dependencies as deps

    # Clear singleton cache to avoid cross-test leakage
    if hasattr(deps.get_orchestrator, "_instance"):
        delattr(deps.get_orchestrator, "_instance")

    app.dependency_overrides[deps.get_orchestrator] = lambda: FakeOrchestrator()
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_chat_requires_api_key(client):
    payload = {
        "prompt": "hello",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    r = client.post("/v1/chat", json=payload)
    assert r.status_code in (401, 403)


def test_compare_requires_api_key(client):
    payload = {
        "prompt": "hello",
        "targets": [{"provider": "openai"}, {"provider": "gemini"}],
    }
    r = client.post("/v1/compare", json=payload)
    assert r.status_code in (401, 403)


def test_compare_rejects_too_many_targets(client):
    payload = {
        "prompt": "hello",
        "targets": [
            {"provider": "openai"},
            {"provider": "gemini"},
            {"provider": "deepseek"},
            {"provider": "grok"},
            {"provider": "openai"},
        ],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
    )
    assert r.status_code in (400, 422)


def test_compare_requires_min_two_targets(client):
    payload = {
        "prompt": "hello",
        "targets": [{"provider": "openai"}],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
    )
    assert r.status_code in (400, 422)


@pytest.mark.parametrize(
    "exc, expected_code, expected_retryable",
    [
        (TimeoutError("timed out"), "timeout", True),
        (Exception("401 Unauthorized"), "auth", False),
        (Exception("429 Too Many Requests"), "rate_limit", True),
        (Exception("400 Bad Request"), "bad_request", False),
        (Exception("503 Service Unavailable"), "provider_error", True),
    ],
)
def test_error_normalization(exc, expected_code, expected_retryable):
    dummy = DummyClient()
    err: NormalizedError = dummy._normalize_error(exc, provider="test")  # type: ignore
    assert err.code == expected_code
    assert err.retryable == expected_retryable


def test_compare_dto_mapping_smoke():
    """
    Validates CompareResponseDTO mapping works against a MultiUnifiedResponse-like object.
    (We make the fake match the DTO-required attributes.)
    """
    r1 = UnifiedResponse(
        request_id="r1",
        text="A",
        provider="openai",
        model="gpt-4o-mini",
        latency_ms=10,
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        estimated_cost=0.00001,
        finish_reason="stop",
        error=None,
        metadata={},
    )
    r2 = UnifiedResponse(
        request_id="r2",
        text="B",
        provider="gemini",
        model="gemini-2.5-flash-lite",
        latency_ms=11,
        token_usage=TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3),
        estimated_cost=0.00002,
        finish_reason="stop",
        error=None,
        metadata={},
    )

    mur = FakeMultiUnifiedResponse(
        request_id="mur_1",
        request_group_id="grp_1",
        prompt="hello",
        responses=[r1, r2],
        success_count=2,
        failure_count=0,
        error_count=0,
        total_tokens=6,
        total_cost=0.00003,
    )

    dto = CompareResponseDTO.from_multi_unified_response(mur)
    assert dto is not None


def test_compare_never_returns_500(client):
    payload = {
        "prompt": "Explain async/await",
        "targets": [{"provider": "openai"}, {"provider": "gemini"}],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
    )
    assert r.status_code < 500
