from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    label: str
    api_key_env: str
    default_model_env: str
    default_model: str
    compare_default_model: str
    byok_supported: bool
    capabilities: tuple[str, ...]
    ui: dict[str, Any]


@dataclass(frozen=True)
class ProviderCatalog:
    _providers: dict[str, ProviderSpec]

    @classmethod
    def from_yaml(cls, path: str | None = None) -> "ProviderCatalog":
        catalog_path = (
            Path(path)
            if path
            else Path(__file__).resolve().parent / "providers.yaml"
        )
        if not catalog_path.exists():
            raise ValueError(f"Provider catalog not found at {catalog_path}")

        data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        raw_providers = data.get("providers")
        if not isinstance(raw_providers, list) or not raw_providers:
            raise ValueError("Invalid provider catalog: 'providers' must be a non-empty list")

        providers: dict[str, ProviderSpec] = {}
        for item in raw_providers:
            if not isinstance(item, dict):
                raise ValueError("Invalid provider catalog entry: expected mapping")

            required = {
                "id",
                "label",
                "api_key_env",
                "default_model_env",
                "default_model",
                "byok_supported",
                "capabilities",
                "ui",
            }
            missing = [key for key in required if key not in item]
            if missing:
                raise ValueError(
                    f"Invalid provider catalog entry: missing required fields {missing}"
                )

            provider_id = str(item["id"]).strip().lower()
            if not provider_id:
                raise ValueError("Invalid provider catalog entry: provider id is empty")
            if provider_id in providers:
                raise ValueError(f"Duplicate provider id in catalog: {provider_id}")

            capabilities = item["capabilities"]
            if not isinstance(capabilities, list):
                raise ValueError(
                    f"Invalid provider catalog entry for {provider_id}: "
                    "'capabilities' must be a list"
                )
            capability_values = tuple(
                str(cap).strip().lower()
                for cap in capabilities
                if str(cap).strip()
            )

            ui = item["ui"]
            if not isinstance(ui, dict):
                raise ValueError(
                    f"Invalid provider catalog entry for {provider_id}: 'ui' must be a mapping"
                )

            compare_default_model = str(
                item.get("compare_default_model") or item["default_model"]
            ).strip()

            providers[provider_id] = ProviderSpec(
                provider_id=provider_id,
                label=str(item["label"]).strip(),
                api_key_env=str(item["api_key_env"]).strip(),
                default_model_env=str(item["default_model_env"]).strip(),
                default_model=str(item["default_model"]).strip(),
                compare_default_model=compare_default_model,
                byok_supported=bool(item["byok_supported"]),
                capabilities=capability_values,
                ui=dict(ui),
            )

        return cls(_providers=providers)

    def provider_ids(self) -> list[str]:
        return list(self._providers.keys())

    def default_models(self) -> dict[str, str]:
        return {provider_id: spec.default_model for provider_id, spec in self._providers.items()}

    def compare_default_models(self) -> dict[str, str]:
        return {
            provider_id: spec.compare_default_model
            for provider_id, spec in self._providers.items()
        }

    def api_key_envs(self) -> dict[str, str]:
        return {provider_id: spec.api_key_env for provider_id, spec in self._providers.items()}

    def default_model_envs(self) -> dict[str, str]:
        return {
            provider_id: spec.default_model_env for provider_id, spec in self._providers.items()
        }

    def labels(self) -> dict[str, str]:
        return {provider_id: spec.label for provider_id, spec in self._providers.items()}

    def byok_supported_provider_ids(self) -> list[str]:
        return [
            provider_id
            for provider_id, spec in self._providers.items()
            if spec.byok_supported
        ]

    def ui_metadata(self) -> dict[str, dict[str, Any]]:
        return {provider_id: dict(spec.ui) for provider_id, spec in self._providers.items()}


@lru_cache(maxsize=1)
def get_provider_catalog() -> ProviderCatalog:
    return ProviderCatalog.from_yaml()


def get_provider_ids() -> list[str]:
    return get_provider_catalog().provider_ids()


def get_provider_default_models() -> dict[str, str]:
    return get_provider_catalog().default_models()


def get_provider_compare_default_models() -> dict[str, str]:
    return get_provider_catalog().compare_default_models()


def get_provider_api_key_envs() -> dict[str, str]:
    return get_provider_catalog().api_key_envs()


def get_provider_default_model_envs() -> dict[str, str]:
    return get_provider_catalog().default_model_envs()


def get_provider_labels() -> dict[str, str]:
    return get_provider_catalog().labels()


def get_byok_supported_providers() -> list[str]:
    return get_provider_catalog().byok_supported_provider_ids()


def get_provider_ui_metadata() -> dict[str, dict[str, Any]]:
    return get_provider_catalog().ui_metadata()
