from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from api.base_client import BaseAIClient
from api import client_registry as client_registry_module
from api.client_registry import ClientRegistry
from config.provider_catalog import get_provider_catalog, get_provider_ids
from server.schemas import requests as request_models


class DummyClient(BaseAIClient):
    def __init__(self, api_key: str, model_name: str, provider_name: str):
        super().__init__(api_key, model_name=model_name)
        self.provider_name = provider_name

    def get_completion(
        self,
        prompt: str | None = None,
        *,
        messages: list | None = None,
        save_full: bool = False,
        **kwargs,
    ):
        raise NotImplementedError

    @classmethod
    def list_available_models(cls, api_key: str = None, **kwargs) -> None:
        return None


def _dummy_factories() -> dict[str, Any]:
    factories = {}
    for provider in get_provider_ids():
        factories[provider] = (
            lambda api_key, model_name, provider=provider: DummyClient(
                api_key=api_key,
                model_name=model_name,
                provider_name=provider,
            )
        )
    return factories


def test_client_registry_builds_from_catalog():
    registry = ClientRegistry.from_catalog(factories=_dummy_factories())
    assert registry.supported_providers() == tuple(get_provider_ids())


def test_client_registry_create_client_uses_catalog_env_defaults(monkeypatch):
    catalog = get_provider_catalog()
    provider = get_provider_ids()[0]
    api_env = catalog.api_key_envs()[provider]
    model_env = catalog.default_model_envs()[provider]

    monkeypatch.setenv(api_env, "key-from-env")
    monkeypatch.setenv(model_env, "model-from-env")

    registry = ClientRegistry.from_catalog(factories=_dummy_factories())
    client = registry.create_client(provider)

    assert isinstance(client, DummyClient)
    assert client.provider_name == provider
    assert client.api_key == "key-from-env"
    assert client.model_name == "model-from-env"


def test_client_registry_create_client_respects_overrides(monkeypatch):
    catalog = get_provider_catalog()
    provider = get_provider_ids()[0]
    api_env = catalog.api_key_envs()[provider]
    monkeypatch.delenv(api_env, raising=False)

    registry = ClientRegistry.from_catalog(factories=_dummy_factories())
    client = registry.create_client(
        provider,
        api_key_override="override-key",
        model_name="override-model",
    )

    assert isinstance(client, DummyClient)
    assert client.api_key == "override-key"
    assert client.model_name == "override-model"


def test_client_registry_rejects_unknown_provider():
    registry = ClientRegistry.from_catalog(factories=_dummy_factories())
    with pytest.raises(ValueError, match="Unsupported MODEL_TYPE"):
        registry.create_client("unknown-provider", api_key_override="x")



def test_client_registry_available_providers_requires_sdk_and_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setattr(
        client_registry_module,
        "is_provider_sdk_available",
        lambda provider: provider != "claude",
    )

    registry = ClientRegistry.from_catalog(factories=_dummy_factories())
    available = registry.available_providers(["openai", "claude"])

    assert available == ["openai"]


def test_client_registry_available_providers_honors_override_keys(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(client_registry_module, "is_provider_sdk_available", lambda provider: True)

    registry = ClientRegistry.from_catalog(factories=_dummy_factories())
    available = registry.available_providers(
        ["claude"],
        provider_api_keys={"claude": "tenant-claude-key"},
    )

    assert available == ["claude"]
def test_client_registry_fails_when_catalog_provider_has_no_registered_adapter():
    providers = get_provider_ids()
    assert providers
    missing_provider = providers[0]
    factories = _dummy_factories()
    factories.pop(missing_provider)

    with pytest.raises(ValueError, match=f"No provider adapter registered for '{missing_provider}'"):
        ClientRegistry.from_catalog(factories=factories)


def test_request_schema_accepts_provider_added_via_catalog_lookup(monkeypatch):
    monkeypatch.setattr(
        request_models,
        "get_provider_ids",
        lambda: ["openai", "gemini", "deepseek", "grok", "claude"],
    )

    chat = request_models.ChatRequest(
        prompt="hello",
        provider="claude",
        model="claude-sonnet",
    )
    compare = request_models.CompareRequest(
        prompt="hello",
        targets=[
            {"provider": "claude", "model": "claude-sonnet"},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ],
    )
    byok = request_models.ByokUpdateRequest(
        provider_keys={},
        baseline_provider="claude",
        baseline_model="claude-sonnet",
    )

    assert chat.provider == "claude"
    assert compare.targets[0].provider == "claude"
    assert byok.baseline_provider == "claude"


def test_request_schema_still_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(
        request_models,
        "get_provider_ids",
        lambda: ["openai", "gemini", "deepseek", "grok"],
    )

    with pytest.raises(ValidationError):
        request_models.ChatRequest(prompt="hello", provider="claude", model="claude-sonnet")
