"""
Baseline safety-rail regression tests.

These tests freeze provider-related behavior across:
- request schema validation
- chat route planning helpers
- BYOK provider validation/runtime resolution
- core orchestrator guardrails
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.core import CortexOrchestrator
from server import byok_service
from server.routes import chat as chat_route
from server.schemas.requests import (
    ByokUpdateRequest,
    ChatRequest,
    ChatRoutingRequest,
    CompareRequest,
)


SMART_CONSTRAINT_ENV_VARS = (
    "SMART_CHAT_MAX_COST_USD",
    "SMART_CHAT_MAX_TOTAL_LATENCY_MS",
    "SMART_CHAT_MIN_CONTEXT_LIMIT",
    "SMART_CHAT_PREFERRED_PROVIDER",
    "SMART_CHAT_ALLOWED_PROVIDERS",
)


def _clear_smart_constraint_env(monkeypatch) -> None:
    for key in SMART_CONSTRAINT_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


class _PreviewOrchestrator:
    def __init__(self, preview_target):
        self.preview_target = preview_target

    def preview_smart_target(self, **_kwargs):
        return self.preview_target


class _PreviewAndAvailabilityOrchestrator(_PreviewOrchestrator):
    def __init__(self, preview_target, available):
        super().__init__(preview_target)
        self.available = available

    def available_providers(self, **_kwargs):
        return list(self.available)

# ---------------------------------------------------------------------------
# Request schema contract
# ---------------------------------------------------------------------------


def test_chat_request_rejects_model_without_provider():
    with pytest.raises(ValidationError):
        ChatRequest(prompt="hello", model="gpt-4o-mini")


def test_chat_request_rejects_unknown_provider():
    with pytest.raises(ValidationError):
        ChatRequest(prompt="hello", provider="unknown-provider", model="unknown-model")


def test_compare_request_rejects_unknown_target_provider():
    with pytest.raises(ValidationError):
        CompareRequest(
            prompt="hello",
            targets=[
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "unknown-provider", "model": "unknown-model"},
            ],
        )


def test_byok_update_requires_non_empty_payload():
    with pytest.raises(ValidationError):
        ByokUpdateRequest(
            provider_keys={},
            baseline_provider=None,
            baseline_model=None,
            requests_per_minute=None,
        )


def test_byok_update_requires_baseline_provider_when_model_is_present():
    with pytest.raises(ValidationError):
        ByokUpdateRequest(provider_keys={}, baseline_model="gpt-4o-mini")


# ---------------------------------------------------------------------------
# Chat route helper contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("OPENAI", "openai"),
        (" openai ", "openai"),
        ("gemini", "gemini"),
        ("claude", "claude"),
        ("", None),
        (None, None),
    ],
)
def test_chat_normalize_provider_contract(raw, expected):
    assert chat_route._normalize_provider(raw) == expected


def test_chat_normalize_provider_list_dedupes_and_drops_invalid():
    normalized = chat_route._normalize_provider_list(
        ["OpenAI", "grok", "invalid", "openai", "GROK", " "]
    )
    assert normalized == ["openai", "grok"]


def test_build_chat_routing_constraints_none_when_not_configured(monkeypatch):
    _clear_smart_constraint_env(monkeypatch)
    assert chat_route._build_chat_routing_constraints() is None


def test_build_chat_routing_constraints_parses_and_filters_values(monkeypatch):
    _clear_smart_constraint_env(monkeypatch)
    monkeypatch.setenv("SMART_CHAT_MAX_COST_USD", "0.03")
    monkeypatch.setenv("SMART_CHAT_MAX_TOTAL_LATENCY_MS", "7000")
    monkeypatch.setenv("SMART_CHAT_MIN_CONTEXT_LIMIT", "2048")
    monkeypatch.setenv("SMART_CHAT_PREFERRED_PROVIDER", " OpenAI ")
    monkeypatch.setenv("SMART_CHAT_ALLOWED_PROVIDERS", "grok,invalid,OPENAI,grok")

    constraints = chat_route._build_chat_routing_constraints()
    assert constraints == {
        "max_cost_usd": 0.03,
        "max_total_latency_ms": 7000,
        "min_context_limit": 2048,
        "preferred_provider": "openai",
        "allowed_providers": ["grok", "openai"],
    }


def test_build_chat_routing_constraints_ignores_invalid_numeric_values(monkeypatch):
    _clear_smart_constraint_env(monkeypatch)
    monkeypatch.setenv("SMART_CHAT_MAX_COST_USD", "not-a-float")
    monkeypatch.setenv("SMART_CHAT_MAX_TOTAL_LATENCY_MS", "-10")
    monkeypatch.setenv("SMART_CHAT_MIN_CONTEXT_LIMIT", "0")
    monkeypatch.setenv("SMART_CHAT_PREFERRED_PROVIDER", "not-a-provider")
    monkeypatch.setenv("SMART_CHAT_ALLOWED_PROVIDERS", "invalid1,invalid2")

    assert chat_route._build_chat_routing_constraints() is None


def test_resolve_chat_execution_plan_manual_uses_provider_default(monkeypatch):
    monkeypatch.setenv("DEFAULT_OPENAI_MODEL", "gpt-4o-mini")
    request = ChatRequest(prompt="hello", provider="openai")

    plan = chat_route._resolve_chat_execution_plan(
        request,
        effective_prompt="hello",
        context=None,
        orchestrator=SimpleNamespace(),
    )

    assert plan.strategy == "explicit_manual"
    assert plan.model_type == "openai"
    assert plan.model_name == "gpt-4o-mini"
    assert plan.preview_provider == "openai"
    assert plan.preview_model == "gpt-4o-mini"


def test_resolve_chat_execution_plan_smart_uses_preview_when_valid(monkeypatch):
    monkeypatch.setattr(chat_route, "TRUE_SMART_ROUTING_ENABLED", True)
    request = ChatRequest(
        prompt="hello",
        routing=ChatRoutingRequest(smart_mode=True, research_mode=False),
    )
    orchestrator = _PreviewOrchestrator(("gemini", "gemini-2.5-flash"))

    plan = chat_route._resolve_chat_execution_plan(
        request,
        effective_prompt="hello",
        context=None,
        orchestrator=orchestrator,
    )

    assert plan.strategy == "smart_orchestrator"
    assert plan.preview_provider == "gemini"
    assert plan.preview_model == "gemini-2.5-flash"
    assert plan.model_type is None
    assert plan.model_name is None


def test_resolve_chat_execution_plan_smart_falls_back_on_invalid_preview(monkeypatch):
    monkeypatch.setattr(chat_route, "TRUE_SMART_ROUTING_ENABLED", True)
    monkeypatch.setenv("DEFAULT_DEEPSEEK_MODEL", "deepseek-chat")
    request = ChatRequest(
        prompt="Write a python function to reverse a list",
        routing=ChatRoutingRequest(smart_mode=True, research_mode=False),
    )
    orchestrator = _PreviewOrchestrator(("unknown-provider", "unknown-model"))

    plan = chat_route._resolve_chat_execution_plan(
        request,
        effective_prompt=request.prompt,
        context=None,
        orchestrator=orchestrator,
    )

    assert plan.strategy == "smart_orchestrator"
    assert plan.preview_provider == "deepseek"
    assert plan.preview_model == "deepseek-chat"


def test_resolve_chat_execution_plan_uses_legacy_auto_when_true_smart_disabled(monkeypatch):
    monkeypatch.setattr(chat_route, "TRUE_SMART_ROUTING_ENABLED", False)
    monkeypatch.setenv("DEFAULT_GROK_MODEL", "grok-4-latest")
    request = ChatRequest(
        prompt="Write a short poem about testing",
        routing=ChatRoutingRequest(smart_mode=True, research_mode=False),
    )

    plan = chat_route._resolve_chat_execution_plan(
        request,
        effective_prompt=request.prompt,
        context=None,
        orchestrator=SimpleNamespace(),
    )

    assert plan.strategy == "legacy_auto"
    assert plan.preview_provider == "grok"
    assert plan.preview_model == "grok-4-latest"


def test_resolve_chat_execution_plan_smart_fallback_prefers_available_providers(monkeypatch):
    monkeypatch.setattr(chat_route, "TRUE_SMART_ROUTING_ENABLED", True)
    monkeypatch.setenv("DEFAULT_OPENAI_MODEL", "gpt-5.2-codex")
    request = ChatRequest(
        prompt="Write a python function to reverse a list",
        routing=ChatRoutingRequest(smart_mode=True, research_mode=False),
    )
    orchestrator = _PreviewAndAvailabilityOrchestrator(None, ["openai"])

    plan = chat_route._resolve_chat_execution_plan(
        request,
        effective_prompt=request.prompt,
        context=None,
        orchestrator=orchestrator,
    )

    assert plan.strategy == "smart_orchestrator"
    assert plan.preview_provider == "openai"
    assert plan.preview_model == "gpt-5.2-codex"

def test_providers_for_runtime_keys_returns_preview_provider_when_not_smart():
    plan = chat_route.ChatExecutionPlan(
        strategy="legacy_auto",
        model_type="openai",
        model_name="gpt-4o-mini",
        routing_mode="legacy",
        routing_constraints=None,
        preview_provider="openai",
        preview_model="gpt-4o-mini",
    )
    assert chat_route._providers_for_runtime_keys(plan) == ["openai"]


def test_providers_for_runtime_keys_uses_filtered_allowed_provider_list():
    plan = chat_route.ChatExecutionPlan(
        strategy="smart_orchestrator",
        model_type=None,
        model_name=None,
        routing_mode="smart",
        routing_constraints={"allowed_providers": ["OPENAI", "bad", "grok", "openai"]},
        preview_provider="gemini",
        preview_model="gemini-2.5-flash",
    )
    assert chat_route._providers_for_runtime_keys(plan) == ["openai", "grok"]


# ---------------------------------------------------------------------------
# BYOK provider validation contract
# ---------------------------------------------------------------------------


def test_byok_validate_provider_normalizes_case_and_whitespace():
    assert byok_service.validate_provider(" OpenAI ") == "openai"


def test_byok_validate_provider_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        byok_service.validate_provider("not-a-provider")


def test_byok_set_keys_normalizes_provider_and_baseline(monkeypatch):
    monkeypatch.setenv("MASTER_KEY", "test-master-key")

    byok_key_calls: list[dict] = []
    settings_calls: list[dict] = []

    monkeypatch.setattr(
        byok_service,
        "upsert_byok_provider_key",
        lambda db_session, **kwargs: byok_key_calls.append(kwargs),
    )
    monkeypatch.setattr(
        byok_service,
        "upsert_api_key_settings",
        lambda db_session, **kwargs: settings_calls.append(kwargs),
    )

    updated = byok_service.set_byok_keys(
        object(),
        api_key_id=uuid4(),
        provider_keys={" OpenAI ": "sk-openai-tenant-1234"},
        baseline_provider=" GEMINI ",
        baseline_model="gemini-2.5-flash",
        requests_per_minute=77,
    )

    assert updated == ["openai"]
    assert byok_key_calls[0]["provider"] == "openai"
    assert byok_key_calls[0]["encrypted_key"].startswith("v1:")
    assert byok_key_calls[0]["encrypted_key"] != "sk-openai-tenant-1234"
    assert settings_calls[0]["baseline_provider"] == "gemini"


def test_byok_set_keys_requires_master_key(monkeypatch):
    monkeypatch.delenv("MASTER_KEY", raising=False)
    with pytest.raises(ValueError, match="MASTER_KEY"):
        byok_service.set_byok_keys(
            object(),
            api_key_id=uuid4(),
            provider_keys={"openai": "sk-openai-tenant-1234"},
        )


def test_byok_runtime_key_resolution_rejects_unknown_requested_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        byok_service.resolve_provider_api_keys(
            object(),
            api_key_id=uuid4(),
            providers=["not-a-provider"],
        )


def test_byok_runtime_key_resolution_returns_empty_without_master_key(monkeypatch):
    monkeypatch.delenv("MASTER_KEY", raising=False)
    monkeypatch.setattr(
        byok_service,
        "list_byok_provider_keys",
        lambda *_args, **_kwargs: [{"provider": "openai", "encrypted_key": "enc-openai"}],
    )

    resolved = byok_service.resolve_provider_api_keys(
        object(),
        api_key_id=uuid4(),
        providers=["openai"],
    )
    assert resolved == {}


def test_byok_runtime_key_resolution_filters_rows_and_wanted_providers(monkeypatch):
    monkeypatch.setenv("MASTER_KEY", "test-master-key")
    monkeypatch.setattr(
        byok_service,
        "list_byok_provider_keys",
        lambda *_args, **_kwargs: [
            {"provider": "openai", "encrypted_key": "enc-openai"},
            {"provider": "gemini", "encrypted_key": "enc-gemini"},
            {"provider": "unknown", "encrypted_key": "enc-unknown"},
        ],
    )
    monkeypatch.setattr(byok_service, "decrypt_secret", lambda token: f"dec:{token}")

    resolved = byok_service.resolve_provider_api_keys(
        object(),
        api_key_id=uuid4(),
        providers=["openai"],
    )
    assert resolved == {"openai": "dec:enc-openai"}


# ---------------------------------------------------------------------------
# Orchestrator guardrail contract
# ---------------------------------------------------------------------------


def test_orchestrator_get_client_rejects_unknown_model_type():
    orchestrator = CortexOrchestrator()
    with pytest.raises(ValueError, match="Unsupported MODEL_TYPE"):
        orchestrator._get_client("unknown-provider")


def test_orchestrator_ask_legacy_mode_requires_provider():
    orchestrator = CortexOrchestrator()
    response = orchestrator.ask(prompt="hello", routing_mode="legacy")
    assert response.is_error is True
    assert response.error is not None
    assert response.error.code == "bad_request"




