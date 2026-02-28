import os
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

from config.provider_catalog import (
    get_provider_api_key_envs,
    get_provider_compare_default_models,
    get_provider_default_model_envs,
    get_provider_default_models,
    get_provider_ids,
    get_provider_labels,
)

_PROVIDER_IDS = get_provider_ids()
if not _PROVIDER_IDS:
    raise ValueError("Provider catalog must define at least one provider")

_PROVIDER_API_KEY_ENVS = get_provider_api_key_envs()
_PROVIDER_DEFAULT_MODEL_ENVS = get_provider_default_model_envs()
_PROVIDER_DEFAULT_MODELS = get_provider_default_models()
_PROVIDER_COMPARE_MODELS = get_provider_compare_default_models()
_PROVIDER_LABELS = get_provider_labels()

# Compare mode target configurations
# Each entry is treated as unique (same provider with different models allowed)
COMPARE_TARGETS = [
    {"provider": provider, "model": model}
    for provider, model in _PROVIDER_COMPARE_MODELS.items()
    if model
]


ModelType = Enum("ModelType", {provider.upper(): provider for provider in _PROVIDER_IDS})


class Config:
    """Configuration management for the application."""

    def __init__(self):
        """Initialize configuration with environment variables."""
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

        self.PROVIDER_IDS = list(_PROVIDER_IDS)
        self.PROVIDER_API_KEY_ENVS = dict(_PROVIDER_API_KEY_ENVS)
        self.PROVIDER_DEFAULT_MODEL_ENVS = dict(_PROVIDER_DEFAULT_MODEL_ENVS)
        self.PROVIDER_DEFAULT_MODELS = dict(_PROVIDER_DEFAULT_MODELS)
        self.PROVIDER_LABELS = dict(_PROVIDER_LABELS)

        self.PROVIDER_API_KEYS = {
            provider: os.getenv(env_name)
            for provider, env_name in self.PROVIDER_API_KEY_ENVS.items()
        }
        self.DEFAULT_MODELS_BY_PROVIDER = {
            provider: self._resolve_default_model(provider)
            for provider in self.PROVIDER_IDS
        }

        # Backward-compatible fields kept for older code paths.
        self.OPENAI_API_KEY = self.PROVIDER_API_KEYS.get("openai")
        self.GOOGLE_GEMINI_API_KEY = self.PROVIDER_API_KEYS.get("gemini")
        self.DEEPSEEK_API_KEY = self.PROVIDER_API_KEYS.get("deepseek")
        self.GROK_API_KEY = self.PROVIDER_API_KEYS.get("grok")

        self.DEFAULT_OPENAI_MODEL = self.DEFAULT_MODELS_BY_PROVIDER.get("openai")
        self.DEFAULT_GEMINI_MODEL = self.DEFAULT_MODELS_BY_PROVIDER.get("gemini")
        self.DEFAULT_DEEPSEEK_MODEL = self.DEFAULT_MODELS_BY_PROVIDER.get("deepseek")
        self.DEFAULT_GROK_MODEL = self.DEFAULT_MODELS_BY_PROVIDER.get("grok")

        default_provider = self.PROVIDER_IDS[0]
        self.MODEL_TYPE = (os.getenv("MODEL_TYPE", default_provider) or default_provider).strip().lower()
        self.DEFAULT_MODEL = self.DEFAULT_MODELS_BY_PROVIDER.get(
            self.MODEL_TYPE,
            os.getenv("DEFAULT_MODEL", self.PROVIDER_DEFAULT_MODELS.get(default_provider, "")),
        )

    def _resolve_default_model(self, provider: str) -> str:
        env_key = self.PROVIDER_DEFAULT_MODEL_ENVS.get(provider)
        fallback = self.PROVIDER_DEFAULT_MODELS.get(provider) or os.getenv("DEFAULT_MODEL", "")
        if not env_key:
            return fallback
        return os.getenv(env_key, fallback)

    def validate(self) -> bool:
        """
        Validate that required configuration is present for the selected provider.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        if self.MODEL_TYPE not in self.PROVIDER_IDS:
            print(
                "Error: Unknown MODEL_TYPE "
                f"'{self.MODEL_TYPE}'. Must be one of: {', '.join(self.PROVIDER_IDS)}"
            )
            return False

        env_name = self.PROVIDER_API_KEY_ENVS.get(self.MODEL_TYPE)
        api_key = self.PROVIDER_API_KEYS.get(self.MODEL_TYPE)
        if api_key:
            return True

        if env_name:
            print(f"Error: {env_name} is not set. Please set it in the .env file.")
        else:
            print(
                f"Error: API key environment mapping missing for MODEL_TYPE '{self.MODEL_TYPE}'."
            )
        return False

    def get_model_info(self) -> str:
        """
        Get information about the currently selected model.

        Returns:
            str: Formatted string with model information
        """
        if self.MODEL_TYPE not in self.PROVIDER_IDS:
            return "Unknown"
        label = self.PROVIDER_LABELS.get(self.MODEL_TYPE, self.MODEL_TYPE.title())
        return f"{label} ({self.DEFAULT_MODEL})"
