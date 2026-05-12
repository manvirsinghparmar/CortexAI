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
   - Ensures protected endpoints reject requests without valid credentials
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

import pytest
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi.testclient import TestClient

from config.provider_catalog import get_provider_catalog, get_provider_ids
from orchestrator.model_registry import ModelRegistry
from server.app import create_app
from models.unified_response import UnifiedResponse, TokenUsage, NormalizedError
from server.schemas.responses import CompareResponseDTO
from api.base_client import BaseAIClient


# -------------------------------------------------------------------
# Fake MultiUnifiedResponse (match what CompareResponseDTO expects)
# -------------------------------------------------------------------

@dataclass(frozen=True)
class FakeMultiUnifiedResponse:
    request_id: str
    request_group_id: str
    prompt: str
    responses: List[UnifiedResponse]

    success_count: int
    failure_count: int
    error_count: int
    total_tokens: int
    total_cost: float

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


# -------------------------------------------------------------------
# Fake orchestrator (keeps tests offline & deterministic)
# -------------------------------------------------------------------

class FakeOrchestrator:
    def __init__(self):
        self.last_ask_prompt = None
        self.last_ask_model_type = None
        self.last_compare_prompt = None
        self.last_ask_kwargs = {}
        self.last_compare_kwargs = {}

    @staticmethod
    def _metadata_for_research_mode(research_mode: str | None) -> dict[str, Any]:
        if str(research_mode or "").strip().lower() != "on":
            return {}
        return {
            "research_used": True,
            "research_reused": False,
            "sources": [{"title": "Example Source", "url": "https://example.com/report"}],
        }

    def ask(self, prompt: str, model_type: Optional[str] = None, context: Any = None, **kwargs) -> UnifiedResponse:
        self.last_ask_prompt = prompt
        self.last_ask_model_type = model_type
        self.last_ask_kwargs = dict(kwargs)
        return UnifiedResponse(
            request_id="req_ask_1",
            text="OK",
            provider=model_type or "openai",
            model=kwargs.get("model_name") or kwargs.get("model") or "fake-model",
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata=self._metadata_for_research_mode(kwargs.get("research_mode")),
        )

    def compare(
        self,
        prompt: str,
        models_list: List[Dict[str, Any]],
        context: Any = None,
        **kwargs
    ) -> FakeMultiUnifiedResponse:
        self.last_compare_prompt = prompt
        self.last_compare_kwargs = dict(kwargs)
        shared_metadata = self._metadata_for_research_mode(kwargs.get("research_mode"))
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
            metadata=shared_metadata,
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
            metadata=shared_metadata,
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
def app(monkeypatch):
    """
    Build FastAPI app and override get_orchestrator dependency.
    """
    monkeypatch.setenv("API_KEYS", "dev-key-1")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ALLOW_NON_POSTGRES_DATABASE_URL", "true")
    monkeypatch.setenv("ENABLE_DEV_SESSION_LOGIN", "false")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("FRONTEND_RUNTIME_API_BASE", raising=False)
    monkeypatch.delenv("FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN", raising=False)
    monkeypatch.delenv("FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN", raising=False)
    app = create_app()

    # Keep these tests DB-agnostic and deterministic.
    from server.routes import chat as chat_route
    from server.routes import compare as compare_route
    from server.routes import history as history_route
    chat_route.API_DB_ENABLED = False
    compare_route.API_DB_ENABLED = False
    history_route.API_DB_ENABLED = False

    from server import dependencies as deps
    session_user_id = UUID("11111111-1111-1111-1111-111111111111")
    monkeypatch.setattr(
        deps,
        "parse_session",
        lambda cookie: session_user_id if cookie else None,
    )

    # Clear singleton cache to avoid cross-test leakage
    if hasattr(deps.get_orchestrator, "_instance"):
        delattr(deps.get_orchestrator, "_instance")

    fake_orchestrator = FakeOrchestrator()
    app.state.fake_orchestrator = fake_orchestrator
    app.dependency_overrides[deps.get_orchestrator] = lambda: fake_orchestrator
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def _parse_runtime_config_payload(js_text: str) -> dict[str, Any]:
    prefix = "window.CORTEX_RUNTIME_CONFIG = "
    assert js_text.startswith(prefix)
    payload_text = js_text[len(prefix):].strip()
    if payload_text.endswith(";"):
        payload_text = payload_text[:-1]
    return json.loads(payload_text)


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_chat_requires_auth(client):
    payload = {
        "prompt": "hello",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    r = client.post("/v1/chat", json=payload)
    assert r.status_code in (401, 403)


def test_compare_requires_auth(client):
    payload = {
        "prompt": "hello",
        "targets": [{"provider": "openai"}, {"provider": "gemini"}],
    }
    r = client.post("/v1/compare", json=payload)
    assert r.status_code in (401, 403)


def test_chat_rejects_api_key_only_auth(client):
    payload = {
        "prompt": "hello",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    r = client.post("/v1/chat", json=payload, headers={"X-API-Key": "dev-key-1"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "session_auth_required"


def test_compare_rejects_api_key_only_auth(client):
    payload = {
        "prompt": "hello",
        "targets": [{"provider": "openai"}, {"provider": "gemini"}],
    }
    r = client.post("/v1/compare", json=payload, headers={"X-API-Key": "dev-key-1"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "session_auth_required"


def test_dev_login_is_disabled_by_default(client):
    r = client.post("/v1/auth/dev-login")
    assert r.status_code == 404


def test_dev_login_sets_session_cookie_when_enabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_SESSION_LOGIN", "true")
    r = client.post("/v1/auth/dev-login")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["email"] == "cli@cortexai.local"
    assert "cortex_session=" in (r.headers.get("set-cookie") or "")

    # TestClient persists cookies between requests, so /me should resolve.
    me = client.get("/v1/auth/me")
    assert me.status_code == 200


def test_dev_login_token_guard_when_configured(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_SESSION_LOGIN", "true")
    monkeypatch.setenv("DEV_SESSION_LOGIN_TOKEN", "local-dev-token")

    unauthorized = client.post("/v1/auth/dev-login")
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/v1/auth/dev-login",
        headers={"X-Dev-Login-Token": "local-dev-token"},
    )
    assert authorized.status_code == 200


def test_dev_login_rejected_in_production_runtime(client, monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_SESSION_LOGIN", "true")
    monkeypatch.setenv("APP_ENV", "production")

    r = client.post("/v1/auth/dev-login")
    assert r.status_code == 403


def test_runtime_config_js_defaults_to_request_origin(client):
    r = client.get("/runtime-config.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "no-store" in (r.headers.get("cache-control") or "")
    payload = _parse_runtime_config_payload(r.text)
    assert payload["apiBase"] == "http://testserver"
    assert payload["enableDevSessionLogin"] is False


def test_runtime_config_js_honors_frontend_env_overrides(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("FRONTEND_RUNTIME_API_BASE", "https://kudlo.triobrain.com/")
    monkeypatch.setenv("FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN", "true")
    monkeypatch.setenv("FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN", "local-token")

    r = client.get("/runtime-config.js")
    assert r.status_code == 200
    payload = _parse_runtime_config_payload(r.text)
    assert payload["apiBase"] == "https://kudlo.triobrain.com"
    assert payload["enableDevSessionLogin"] is True
    assert payload["devSessionLoginToken"] == "local-token"


def test_runtime_config_js_disables_dev_session_login_in_production(client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN", "true")

    r = client.get("/runtime-config.js")
    assert r.status_code == 200
    payload = _parse_runtime_config_payload(r.text)
    assert payload["enableDevSessionLogin"] is False


def test_chat_with_attachments_requires_db_mode(client):
    payload = {
        "prompt": "describe this file",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "attachments": [
            {"file_id": "11111111-1111-1111-1111-111111111111", "usage_role": "primary", "transform_mode": "auto"}
        ],
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 501
    assert r.json()["detail"]["code"] == "attachments_require_db"


def test_compare_with_attachments_requires_db_mode(client):
    payload = {
        "prompt": "compare this file",
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
        "attachments": [
            {"file_id": "22222222-2222-2222-2222-222222222222", "usage_role": "primary", "transform_mode": "auto"}
        ],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 501
    assert r.json()["detail"]["code"] == "attachments_require_db"


def test_providers_catalog_requires_auth(client):
    r = client.get("/v1/providers")
    assert r.status_code in (401, 403)


def test_models_catalog_requires_auth(client):
    r = client.get("/v1/models")
    assert r.status_code in (401, 403)


def test_providers_catalog_rejects_api_key_only_auth(client):
    r = client.get("/v1/providers", headers={"X-API-Key": "dev-key-1"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "session_auth_required"


def test_models_catalog_rejects_api_key_only_auth(client):
    r = client.get("/v1/models", headers={"X-API-Key": "dev-key-1"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "session_auth_required"


def test_providers_catalog_returns_catalog_and_model_counts(client):
    r = client.get("/v1/providers", cookies={"cortex_session": "test-session-cookie"})
    assert r.status_code == 200

    body = r.json()
    assert body["total"] == len(body["providers"])
    assert isinstance(body.get("timestamp"), str) and body["timestamp"]

    catalog = get_provider_catalog()
    registry = ModelRegistry.from_yaml()
    by_provider = {item["provider"]: item for item in body["providers"]}
    assert set(by_provider.keys()) == set(catalog.provider_ids())

    for spec in catalog.provider_specs():
        item = by_provider[spec.provider_id]
        assert item["label"] == spec.label
        assert item["api_key_env"] == spec.api_key_env
        assert item["default_model_env"] == spec.default_model_env
        assert item["default_model"] == spec.default_model
        assert item["byok_supported"] == spec.byok_supported
        assert item["capabilities"] == list(spec.capabilities)
        assert item["ui"] == dict(spec.ui)

        expected_all = registry.list_models(spec.provider_id, include_disabled=True)
        expected_enabled = registry.list_models(spec.provider_id, include_disabled=False)
        assert item["model_count"] == len(expected_all)
        assert item["enabled_model_count"] == len(expected_enabled)


def test_models_catalog_lists_enabled_models_by_default(client):
    r = client.get("/v1/models", cookies={"cortex_session": "test-session-cookie"})
    assert r.status_code == 200

    body = r.json()
    assert body["provider"] is None
    assert body["enabled_only"] is True
    assert body["total"] == len(body["models"])
    assert isinstance(body.get("timestamp"), str) and body["timestamp"]
    assert all(item["enabled"] is True for item in body["models"])

    required_keys = {
        "provider",
        "model",
        "tier",
        "input_cost_per_1m",
        "output_cost_per_1m",
        "context_limit",
        "tags",
        "enabled",
        "supports_image_input",
        "supported_attachment_mime_types",
        "max_attachment_bytes",
        "max_attachments_per_request",
    }
    for item in body["models"]:
        assert required_keys.issubset(item.keys())

    registry = ModelRegistry.from_yaml()
    expected_pairs = {
        (candidate.provider, candidate.model_name)
        for candidate in registry.list_models(include_disabled=False)
    }
    actual_pairs = {(item["provider"], item["model"]) for item in body["models"]}
    assert actual_pairs == expected_pairs


def test_models_catalog_filters_by_provider_case_insensitive(client):
    provider = get_provider_ids()[0]
    r = client.get(
        f"/v1/models?provider={provider.upper()}",
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200

    body = r.json()
    assert body["provider"] == provider
    assert body["enabled_only"] is True
    assert all(item["provider"] == provider for item in body["models"])

    registry = ModelRegistry.from_yaml()
    expected_names = sorted(
        candidate.model_name
        for candidate in registry.list_models(provider=provider, include_disabled=False)
    )
    actual_names = sorted(item["model"] for item in body["models"])
    assert actual_names == expected_names


def test_models_catalog_can_include_disabled(client):
    provider = get_provider_ids()[0]
    r_enabled = client.get(
        f"/v1/models?provider={provider}",
        cookies={"cortex_session": "test-session-cookie"},
    )
    r_all = client.get(
        f"/v1/models?provider={provider}&enabled_only=false",
        cookies={"cortex_session": "test-session-cookie"},
    )

    assert r_enabled.status_code == 200
    assert r_all.status_code == 200

    enabled_body = r_enabled.json()
    all_body = r_all.json()
    assert enabled_body["enabled_only"] is True
    assert all_body["enabled_only"] is False

    enabled_pairs = {(item["provider"], item["model"]) for item in enabled_body["models"]}
    all_pairs = {(item["provider"], item["model"]) for item in all_body["models"]}
    assert enabled_pairs.issubset(all_pairs)
    assert len(all_pairs) >= len(enabled_pairs)


def test_models_catalog_rejects_unsupported_provider(client):
    r = client.get(
        "/v1/models?provider=not-a-provider",
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "Unsupported provider 'not-a-provider'" in detail
    for provider in get_provider_ids():
        assert provider in detail


def test_optimize_rejects_api_key_only_auth(client):
    r = client.post(
        "/v1/optimize",
        json={"prompt": "make this prompt better"},
        headers={"X-API-Key": "dev-key-1"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "session_auth_required"


def test_optimize_accepts_session_cookie_auth(client):
    r = client.post(
        "/v1/optimize",
        json={"prompt": "make this prompt better"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["original_prompt"] == "make this prompt better"


def test_optimize_uses_schema_optimizer_when_enabled(client, monkeypatch):
    from server.routes import optimize as optimize_route

    class FakeOptimizer:
        def optimize_prompt(self, payload):
            assert payload == {"prompt": "make this prompt better"}
            return {
                "optimized_prompt": "Rewrite this prompt to be more specific and actionable.",
                "steps": ["clarified intent"],
            }

    monkeypatch.setenv("ENABLE_PROMPT_OPTIMIZATION", "true")
    monkeypatch.setattr(optimize_route, "_get_optimizer", lambda: FakeOptimizer())

    r = client.post(
        "/v1/optimize",
        json={"prompt": "make this prompt better"},
        cookies={"cortex_session": "test-session-cookie"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["optimized_prompt"] == "Rewrite this prompt to be more specific and actionable."
    assert body["was_optimized"] is True
    assert body["server_optimization_enabled"] is True


def test_optimize_falls_back_when_schema_optimizer_rejects_output(client, monkeypatch):
    from server.routes import optimize as optimize_route

    class FakeOptimizer:
        def optimize_prompt(self, payload):
            return {
                "optimized_prompt": payload["prompt"],
                "error": {
                    "code": "optimization_failed",
                    "message": "Optimizer response appears to answer the prompt instead of rewriting it",
                },
            }

    monkeypatch.setenv("ENABLE_PROMPT_OPTIMIZATION", "true")
    monkeypatch.setattr(optimize_route, "_get_optimizer", lambda: FakeOptimizer())

    r = client.post(
        "/v1/optimize",
        json={"prompt": "how osama was killed"},
        cookies={"cortex_session": "test-session-cookie"},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["optimized_prompt"] == "how osama was killed"
    assert body["was_optimized"] is False
    assert body["server_optimization_enabled"] is True


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
        cookies={"cortex_session": "test-session-cookie"},
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
        cookies={"cortex_session": "test-session-cookie"},
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


def test_provider_503_high_demand_error_is_classified_as_transient_capacity():
    dummy = DummyClient()
    err: NormalizedError = dummy._normalize_error(
        Exception(
            "503 UNAVAILABLE. {'error': {'message': 'This model is currently "
            "experiencing high demand. Please try again later.'}}"
        ),
        provider="gemini",
    )  # type: ignore

    assert err.code == "provider_error"
    assert err.retryable is True
    assert err.message == "This model is temporarily busy. Try again shortly or switch to another model."
    assert err.details["kind"] == "transient_capacity"
    assert err.details["status_code"] == 503


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
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code < 500


def test_chat_stream_returns_ndjson_events(client):
    payload = {
        "prompt": "hello",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    r = client.post(
        "/v1/chat/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert "application/x-ndjson" in r.headers.get("content-type", "")

    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    event_types = [e.get("type") for e in events]

    assert "start" in event_types
    assert "response_done" in event_types
    assert "done" in event_types


def test_chat_normalizes_empty_success_payload_to_provider_error(client, app):
    def _empty_success(*_args, **_kwargs):
        return UnifiedResponse(
            request_id="req_empty_success_chat",
            text="",
            provider="openai",
            model="gpt-5.1",
            latency_ms=8,
            token_usage=TokenUsage(prompt_tokens=200, completion_tokens=500, total_tokens=700),
            estimated_cost=0.0,
            finish_reason="length",
            error=None,
            metadata={"endpoint": "chat.completions"},
        )

    app.state.fake_orchestrator.ask = _empty_success

    payload = {
        "prompt": "Long answer please",
        "provider": "openai",
        "model": "gpt-5.1",
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200

    body = r.json()
    assert body["text"] == ""
    assert body["finish_reason"] == "error"
    assert body["error"] is not None
    assert body["error"]["code"] == "provider_error"
    assert body["error"]["details"]["finish_reason"] == "length"
    assert body["error"]["details"]["endpoint"] == "chat.completions"


def test_chat_sanitizes_raw_transient_provider_error(client, app):
    raw_message = (
        "Provider error: 503 UNAVAILABLE. {'error': {'code': 503, 'message': "
        "'This model is currently experiencing high demand. Spikes in demand are usually temporary.'}}"
    )

    def _transient_error(*_args, **_kwargs):
        return UnifiedResponse(
            request_id="req_transient_chat",
            text="",
            provider="gemini",
            model="gemini-2.5-flash",
            latency_ms=20,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=NormalizedError(
                code="provider_error",
                message=raw_message,
                provider="gemini",
                retryable=True,
            ),
            metadata={},
        )

    app.state.fake_orchestrator.ask = _transient_error

    r = client.post(
        "/v1/chat",
        json={"prompt": "hello", "provider": "gemini", "model": "gemini-2.5-flash"},
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200

    body = r.json()
    assert body["error"]["message"] == "This model is temporarily busy. Try again shortly or switch to another model."
    assert body["error"]["details"]["kind"] == "transient_capacity"
    assert "UNAVAILABLE" not in body["error"]["message"]


def test_chat_stream_normalizes_empty_success_payload_to_provider_error(client, app):
    def _empty_success(*_args, **_kwargs):
        return UnifiedResponse(
            request_id="req_empty_success_chat_stream",
            text="",
            provider="openai",
            model="gpt-5.1",
            latency_ms=8,
            token_usage=TokenUsage(prompt_tokens=200, completion_tokens=500, total_tokens=700),
            estimated_cost=0.0,
            finish_reason="length",
            error=None,
            metadata={"endpoint": "chat.completions"},
        )

    app.state.fake_orchestrator.ask = _empty_success

    payload = {
        "prompt": "Long answer please",
        "provider": "openai",
        "model": "gpt-5.1",
    }
    r = client.post(
        "/v1/chat/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]

    line_events = [event for event in events if event.get("type") == "line"]
    assert any(
        "Error: Provider returned an empty response." in str(event.get("text", ""))
        for event in line_events
    )

    done = next((event for event in events if event.get("type") == "response_done"), None)
    assert done is not None
    payload_json = done["response"]
    assert payload_json["text"] == ""
    assert payload_json["finish_reason"] == "error"
    assert payload_json["error"]["code"] == "provider_error"
    assert payload_json["error"]["details"]["finish_reason"] == "length"


def test_chat_stream_sanitizes_raw_transient_provider_error(client, app):
    raw_message = (
        "Provider error: 503 UNAVAILABLE. {'error': {'message': "
        "'This model is currently experiencing high demand. Please try again later.'}}"
    )

    def _transient_error(*_args, **_kwargs):
        return UnifiedResponse(
            request_id="req_transient_chat_stream",
            text="",
            provider="gemini",
            model="gemini-2.5-flash",
            latency_ms=20,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=NormalizedError(
                code="provider_error",
                message=raw_message,
                provider="gemini",
                retryable=True,
            ),
            metadata={},
        )

    app.state.fake_orchestrator.ask = _transient_error

    r = client.post(
        "/v1/chat/stream",
        json={"prompt": "hello", "provider": "gemini", "model": "gemini-2.5-flash"},
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    rendered_text = "\n".join(str(event.get("text", "")) for event in events if event.get("type") == "line")
    assert rendered_text == "This model is temporarily busy. Try again shortly or switch to another model."
    assert "UNAVAILABLE" not in rendered_text
    assert "high demand" not in rendered_text


def test_compare_normalizes_empty_success_payload_to_provider_error(client, app):
    def _compare_with_blank_success(prompt: str, models_list: List[Dict[str, Any]], context: Any = None, **kwargs):
        empty = UnifiedResponse(
            request_id="req_cmp_empty",
            text="",
            provider=models_list[0]["provider"],
            model=models_list[0].get("model", "gpt-5.1"),
            latency_ms=7,
            token_usage=TokenUsage(prompt_tokens=120, completion_tokens=500, total_tokens=620),
            estimated_cost=0.0,
            finish_reason="length",
            error=None,
            metadata={"endpoint": "chat.completions"},
        )
        ok = UnifiedResponse(
            request_id="req_cmp_ok",
            text="second model answer",
            provider=models_list[1]["provider"],
            model=models_list[1].get("model", "gemini-2.5-flash"),
            latency_ms=9,
            token_usage=TokenUsage(prompt_tokens=12, completion_tokens=18, total_tokens=30),
            estimated_cost=0.0001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        return FakeMultiUnifiedResponse(
            request_id="req_compare_empty_shape",
            request_group_id="grp_compare_empty_shape",
            prompt=prompt,
            responses=[empty, ok],
            success_count=2,
            failure_count=0,
            error_count=0,
            total_tokens=650,
            total_cost=0.0001,
        )

    app.state.fake_orchestrator.compare = _compare_with_blank_success

    payload = {
        "prompt": "compare this",
        "targets": [
            {"provider": "openai", "model": "gpt-5.1"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200

    body = r.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    first = body["responses"][0]
    assert first["text"] == ""
    assert first["finish_reason"] == "error"
    assert first["error"]["code"] == "provider_error"
    assert first["error"]["details"]["finish_reason"] == "length"


def test_compare_sanitizes_raw_transient_provider_error(client, app):
    raw_message = (
        "Provider error: 503 UNAVAILABLE. {'error': {'message': "
        "'This model is currently experiencing high demand. Please try again later.'}}"
    )

    def _compare_with_transient_error(
        prompt: str,
        models_list: List[Dict[str, Any]],
        context: Any = None,
        **kwargs,
    ):
        failed = UnifiedResponse(
            request_id="req_cmp_transient",
            text="",
            provider=models_list[0]["provider"],
            model=models_list[0].get("model", "gemini-2.5-flash"),
            latency_ms=15,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=NormalizedError(
                code="provider_error",
                message=raw_message,
                provider=models_list[0]["provider"],
                retryable=True,
            ),
            metadata={},
        )
        ok = UnifiedResponse(
            request_id="req_cmp_still_ok",
            text="second model answer",
            provider=models_list[1]["provider"],
            model=models_list[1].get("model", "openai-model"),
            latency_ms=9,
            token_usage=TokenUsage(prompt_tokens=12, completion_tokens=18, total_tokens=30),
            estimated_cost=0.0001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        return FakeMultiUnifiedResponse(
            request_id="req_compare_transient_shape",
            request_group_id="grp_compare_transient_shape",
            prompt=prompt,
            responses=[failed, ok],
            success_count=1,
            failure_count=1,
            error_count=1,
            total_tokens=30,
            total_cost=0.0001,
        )

    app.state.fake_orchestrator.compare = _compare_with_transient_error

    r = client.post(
        "/v1/compare",
        json={
            "prompt": "compare",
            "targets": [
                {"provider": "gemini", "model": "gemini-2.5-flash"},
                {"provider": "openai", "model": "gpt-4o-mini"},
            ],
        },
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    body = r.json()
    first = body["responses"][0]
    assert first["error"]["message"] == "This model is temporarily busy. Try again shortly or switch to another model."
    assert first["error"]["details"]["kind"] == "transient_capacity"
    assert "UNAVAILABLE" not in first["error"]["message"]
    assert body["success_count"] == 1
    assert body["error_count"] == 1


def test_compare_stream_returns_ndjson_events(client):
    payload = {
        "prompt": "hello",
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert "application/x-ndjson" in r.headers.get("content-type", "")

    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    event_types = [e.get("type") for e in events]

    assert "start" in event_types
    assert event_types.count("response_done") >= 2
    assert "done" in event_types


def test_compare_stream_normalizes_empty_success_payload_to_provider_error(client, app):
    def _ask_with_one_blank(prompt: str, model_type: Optional[str] = None, context: Any = None, **kwargs):
        provider = model_type or "openai"
        model = kwargs.get("model_name") or kwargs.get("model") or "unknown"
        if provider == "openai":
            return UnifiedResponse(
                request_id="req_cmp_stream_empty",
                text="",
                provider=provider,
                model=model,
                latency_ms=6,
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=500, total_tokens=600),
                estimated_cost=0.0,
                finish_reason="length",
                error=None,
                metadata={"endpoint": "chat.completions"},
            )

        return UnifiedResponse(
            request_id="req_cmp_stream_ok",
            text="healthy fallback answer",
            provider=provider,
            model=model,
            latency_ms=6,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0.0001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

    app.state.fake_orchestrator.ask = _ask_with_one_blank

    payload = {
        "prompt": "compare stream",
        "targets": [
            {"provider": "openai", "model": "gpt-5.1"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]

    response_done_events = [event for event in events if event.get("type") == "response_done"]
    assert len(response_done_events) >= 2
    openai_done = next(
        (event for event in response_done_events if event.get("response", {}).get("provider") == "openai"),
        None,
    )
    assert openai_done is not None
    openai_resp = openai_done["response"]
    assert openai_resp["text"] == ""
    assert openai_resp["finish_reason"] == "error"
    assert openai_resp["error"]["code"] == "provider_error"
    assert openai_resp["error"]["details"]["finish_reason"] == "length"


def test_compare_stream_done_payload_counts_normalized_errors_and_caps_tokens(client, app):
    observed_kwargs: dict[str, Any] = {}

    def _ask_with_one_blank(prompt: str, model_type: Optional[str] = None, context: Any = None, **kwargs):
        observed_kwargs.clear()
        observed_kwargs.update(kwargs)
        provider = model_type or "openai"
        model = kwargs.get("model_name") or kwargs.get("model") or "unknown"
        if provider == "openai":
            return UnifiedResponse(
                request_id="req_cmp_stream_empty_count",
                text="",
                provider=provider,
                model=model,
                latency_ms=6,
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=500, total_tokens=600),
                estimated_cost=0.0,
                finish_reason="length",
                error=None,
                metadata={"endpoint": "chat.completions"},
            )

        return UnifiedResponse(
            request_id="req_cmp_stream_ok_count",
            text="healthy fallback answer",
            provider=provider,
            model=model,
            latency_ms=6,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0.0001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

    app.state.fake_orchestrator.ask = _ask_with_one_blank

    payload = {
        "prompt": "compare stream aggregate",
        "max_tokens": 99999,
        "targets": [
            {"provider": "openai", "model": "gpt-5.1"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert observed_kwargs.get("max_tokens") == 2048

    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    done = next((event for event in events if event.get("type") == "done"), None)
    assert done is not None
    compare_payload = done.get("compare", {})
    assert compare_payload.get("success_count") == 1
    assert compare_payload.get("error_count") == 1


def test_compare_stream_allows_context_with_three_targets(client):
    payload = {
        "prompt": "Where is it most discussed in Canada?",
        "context": {
            "session_id": "session-compare-1",
            "new_session": False,
            "conversation_history": [
                {"role": "user", "content": "Tell me about Donald Trump"},
                {"role": "assistant", "content": "Trump is a former U.S. president."},
            ],
        },
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
            {"provider": "deepseek", "model": "deepseek-chat"},
        ],
    }
    r = client.post(
        "/v1/compare/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert "application/x-ndjson" in r.headers.get("content-type", "")

    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    event_types = [e.get("type") for e in events]
    assert event_types.count("response_done") >= 3
    assert "done" in event_types


def test_chat_accepts_auto_routing_without_provider(client, app):
    payload = {
        "prompt": "Give me a quick summary of async await",
        "routing": {"smart_mode": True, "research_mode": False},
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("provider") in set(get_provider_ids())
    assert isinstance(body.get("model"), str)
    assert app.state.fake_orchestrator.last_ask_model_type is None
    assert app.state.fake_orchestrator.last_ask_kwargs.get("routing_mode") == "smart"


def test_chat_rejects_model_without_provider(client):
    payload = {
        "prompt": "hello",
        "model": "gpt-4o-mini",
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 422


def test_chat_clamps_max_tokens_to_server_cap(client, app):
    payload = {
        "prompt": "Give me a summary",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "max_tokens": 99999,
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert app.state.fake_orchestrator.last_ask_kwargs.get("max_tokens") == 2048


def test_compare_clamps_max_tokens_to_server_cap(client, app):
    payload = {
        "prompt": "compare",
        "max_tokens": 77777,
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert app.state.fake_orchestrator.last_compare_kwargs.get("max_tokens") == 2048


def test_chat_stream_auto_routing_includes_selected_target(client, app):
    payload = {
        "prompt": "Write a small Python function",
        "routing": {"smart_mode": True},
    }
    r = client.post(
        "/v1/chat/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    start_event = next((e for e in events if e.get("type") == "start"), None)
    assert start_event is not None
    assert start_event.get("provider") in set(get_provider_ids())
    assert isinstance(start_event.get("model"), str)
    assert app.state.fake_orchestrator.last_ask_model_type is None
    assert app.state.fake_orchestrator.last_ask_kwargs.get("routing_mode") == "smart"


def test_chat_web_mode_keeps_prompt_clean_and_returns_sources_from_orchestrator(client, app):
    payload = {
        "prompt": "Latest AI policy updates",
        "routing": {"smart_mode": True, "research_mode": True},
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    payload_json = r.json()
    assert app.state.fake_orchestrator.last_ask_prompt == "Latest AI policy updates"
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "on"
    assert payload_json["web_source_items"] == [
        {"title": "Example Source", "url": "https://example.com/report"}
    ]


def test_chat_web_toggle_off_after_on_only_returns_sources_for_web_turn(client, app):
    first_payload = {
        "prompt": "Latest AI policy updates",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "context": {"session_id": "session-toggle-chat", "new_session": False},
        "routing": {"smart_mode": True, "research_mode": True},
    }
    first_response = client.post(
        "/v1/chat",
        json=first_payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert first_response.status_code == 200
    assert app.state.fake_orchestrator.last_ask_prompt == "Latest AI policy updates"
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "on"
    assert first_response.json()["web_source_items"] == [
        {"title": "Example Source", "url": "https://example.com/report"}
    ]

    second_payload = {
        "prompt": "Explain photosynthesis in one sentence.",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "context": {"session_id": "session-toggle-chat", "new_session": False},
        "routing": {"smart_mode": True, "research_mode": False},
    }
    second_response = client.post(
        "/v1/chat",
        json=second_payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert second_response.status_code == 200
    assert app.state.fake_orchestrator.last_ask_prompt == "Explain photosynthesis in one sentence."
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "off"
    assert second_response.json()["web_source_items"] == []


def test_compare_web_mode_keeps_prompt_clean_and_returns_sources_from_orchestrator(client, app):
    payload = {
        "prompt": "Recent market updates",
        "routing": {"research_mode": True},
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    payload_json = r.json()
    assert app.state.fake_orchestrator.last_compare_prompt == "Recent market updates"
    assert payload_json["responses"][0]["web_source_items"] == [
        {"title": "Example Source", "url": "https://example.com/report"}
    ]


def test_chat_passes_research_mode_off_to_orchestrator_when_web_toggle_off(client, app):
    payload = {
        "prompt": "Can humans survive a nuclear war?",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "routing": {"smart_mode": True, "research_mode": False},
    }
    r = client.post(
        "/v1/chat",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "off"


def test_chat_stream_passes_research_mode_off_to_orchestrator_when_web_toggle_off(client, app):
    payload = {
        "prompt": "Can humans survive a nuclear war?",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "routing": {"smart_mode": True, "research_mode": False},
    }
    r = client.post(
        "/v1/chat/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "off"


def test_compare_passes_research_mode_to_orchestrator(client, app):
    payload = {
        "prompt": "Recent market updates",
        "routing": {"research_mode": True},
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert app.state.fake_orchestrator.last_compare_kwargs.get("research_mode") == "on"
    assert "routing_mode" not in app.state.fake_orchestrator.last_compare_kwargs


def test_compare_stream_passes_research_mode_off_to_orchestrator(client, app):
    payload = {
        "prompt": "Recent market updates",
        "routing": {"smart_mode": True, "research_mode": False},
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    r = client.post(
        "/v1/compare/stream",
        json=payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert r.status_code == 200
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "off"
    assert "routing_mode" not in app.state.fake_orchestrator.last_ask_kwargs


def test_compare_stream_web_toggle_off_after_on_only_returns_sources_for_web_turn(client, app):
    first_payload = {
        "prompt": "Recent market updates",
        "context": {"session_id": "session-toggle-compare-stream", "new_session": False},
        "routing": {"research_mode": True},
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    first_response = client.post(
        "/v1/compare/stream",
        json=first_payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert first_response.status_code == 200
    first_events = [json.loads(line) for line in first_response.text.splitlines() if line.strip()]
    first_start = next((event for event in first_events if event.get("type") == "start"), None)
    first_done = next((event for event in first_events if event.get("type") == "response_done"), None)
    assert first_start is not None
    assert first_done is not None
    assert first_start.get("research_mode") is True
    assert first_start.get("web_sources") == 0
    assert first_done.get("response", {}).get("web_source_items") == [
        {"title": "Example Source", "url": "https://example.com/report"}
    ]
    assert app.state.fake_orchestrator.last_ask_prompt == "Recent market updates"
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "on"

    second_payload = {
        "prompt": "Explain photosynthesis in one sentence.",
        "context": {"session_id": "session-toggle-compare-stream", "new_session": False},
        "routing": {"research_mode": False},
        "targets": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    second_response = client.post(
        "/v1/compare/stream",
        json=second_payload,
        headers={"X-API-Key": "dev-key-1"},
        cookies={"cortex_session": "test-session-cookie"},
    )
    assert second_response.status_code == 200
    second_events = [json.loads(line) for line in second_response.text.splitlines() if line.strip()]
    second_start = next((event for event in second_events if event.get("type") == "start"), None)
    second_done = next((event for event in second_events if event.get("type") == "response_done"), None)
    assert second_start is not None
    assert second_done is not None
    assert second_start.get("research_mode") is False
    assert second_start.get("web_sources") == 0
    assert second_done.get("response", {}).get("web_source_items") == []
    assert app.state.fake_orchestrator.last_ask_prompt == "Explain photosynthesis in one sentence."
    assert app.state.fake_orchestrator.last_ask_kwargs.get("research_mode") == "off"


