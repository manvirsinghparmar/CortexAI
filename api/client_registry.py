from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from config.provider_catalog import get_provider_catalog
from api.base_client import BaseAIClient
from api.provider_adapter import ProviderAdapter, RegistryProviderAdapter


ClientFactory = Callable[[str, str], BaseAIClient]


def _build_openai_client(api_key: str, model_name: str) -> BaseAIClient:
    from api.openai_client import OpenAIClient

    return OpenAIClient(api_key=api_key, model_name=model_name)


def _build_gemini_client(api_key: str, model_name: str) -> BaseAIClient:
    from api.google_gemini_client import GeminiClient

    return GeminiClient(api_key=api_key, model_name=model_name)


def _build_deepseek_client(api_key: str, model_name: str) -> BaseAIClient:
    from api.deepseek_client import DeepSeekClient

    return DeepSeekClient(api_key=api_key, model_name=model_name)


def _build_grok_client(api_key: str, model_name: str) -> BaseAIClient:
    from api.grok_client import GrokClient

    return GrokClient(api_key=api_key, model_name=model_name)


def _default_factories() -> dict[str, ClientFactory]:
    return {
        "openai": _build_openai_client,
        "gemini": _build_gemini_client,
        "deepseek": _build_deepseek_client,
        "grok": _build_grok_client,
    }


@dataclass(frozen=True)
class ClientRegistry:
    _adapters: dict[str, ProviderAdapter]

    @classmethod
    def from_catalog(
        cls,
        *,
        factories: dict[str, ClientFactory] | None = None,
    ) -> "ClientRegistry":
        catalog = get_provider_catalog()
        provider_ids = catalog.provider_ids()
        api_key_envs = catalog.api_key_envs()
        default_model_envs = catalog.default_model_envs()
        default_models = catalog.default_models()
        provider_factories = factories or _default_factories()

        adapters: dict[str, ProviderAdapter] = {}
        for provider_id in provider_ids:
            factory = provider_factories.get(provider_id)
            if not callable(factory):
                # Keep the failure mode explicit so unsupported providers fail fast.
                raise ValueError(f"No provider adapter registered for '{provider_id}'")

            adapters[provider_id] = RegistryProviderAdapter(
                provider_id=provider_id,
                api_key_env=api_key_envs[provider_id],
                default_model_env=default_model_envs[provider_id],
                default_model=default_models[provider_id],
                client_factory=factory,
            )

        return cls(_adapters=adapters)

    def supported_providers(self) -> tuple[str, ...]:
        return tuple(self._adapters.keys())

    def get_adapter(self, provider: str) -> ProviderAdapter:
        provider_norm = (provider or "").strip().lower()
        adapter = self._adapters.get(provider_norm)
        if adapter is None:
            raise ValueError(f"Unsupported MODEL_TYPE: {provider_norm or provider}")
        return adapter

    def create_client(
        self,
        provider: str,
        *,
        model_name: str | None = None,
        api_key_override: str | None = None,
    ) -> BaseAIClient:
        adapter = self.get_adapter(provider)
        api_key = api_key_override or os.getenv(adapter.api_key_env)
        if not api_key:
            raise ValueError(f"{adapter.api_key_env} not found in environment variables")

        resolved_model = model_name or os.getenv(adapter.default_model_env, adapter.default_model)
        return adapter.create_client(api_key=api_key, model_name=resolved_model)
