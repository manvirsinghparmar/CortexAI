from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Callable

from config.provider_catalog import get_provider_catalog
from api.base_client import BaseAIClient
from api.provider_adapter import ProviderAdapter, RegistryProviderAdapter


ClientFactory = Callable[[str, str], BaseAIClient]

_PROVIDER_SDK_MODULES: dict[str, str] = {
    "openai": "openai",
    "deepseek": "openai",
    "grok": "openai",
    "gemini": "google.genai",
    "claude": "anthropic",
}


def is_provider_sdk_available(provider: str) -> bool:
    provider_norm = (provider or "").strip().lower()
    module_name = _PROVIDER_SDK_MODULES.get(provider_norm)
    if not module_name:
        return True
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False

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


def _build_claude_client(api_key: str, model_name: str) -> BaseAIClient:
    from api.claude_client import ClaudeClient

    return ClaudeClient(api_key=api_key, model_name=model_name)


def _default_factories() -> dict[str, ClientFactory]:
    return {
        "openai": _build_openai_client,
        "gemini": _build_gemini_client,
        "deepseek": _build_deepseek_client,
        "grok": _build_grok_client,
        "claude": _build_claude_client,
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

    def has_configured_api_key(
        self,
        provider: str,
        *,
        api_key_override: str | None = None,
    ) -> bool:
        adapter = self.get_adapter(provider)
        if api_key_override:
            return True
        return bool(os.getenv(adapter.api_key_env))

    def is_provider_routable(
        self,
        provider: str,
        *,
        api_key_override: str | None = None,
    ) -> bool:
        provider_norm = (provider or "").strip().lower()
        if not provider_norm:
            return False
        return is_provider_sdk_available(provider_norm) and self.has_configured_api_key(
            provider_norm,
            api_key_override=api_key_override,
        )

    def available_providers(
        self,
        providers: list[str] | tuple[str, ...] | None = None,
        *,
        provider_api_keys: dict[str, str] | None = None,
    ) -> list[str]:
        overrides = {
            str(provider or "").strip().lower(): str(api_key or "").strip()
            for provider, api_key in (provider_api_keys or {}).items()
            if str(provider or "").strip() and str(api_key or "").strip()
        }
        candidates = providers or self.supported_providers()
        available: list[str] = []

        for provider in candidates:
            provider_norm = (provider or "").strip().lower()
            if not provider_norm or provider_norm in available:
                continue
            try:
                if self.is_provider_routable(
                    provider_norm,
                    api_key_override=overrides.get(provider_norm),
                ):
                    available.append(provider_norm)
            except ValueError:
                continue

        return available

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



