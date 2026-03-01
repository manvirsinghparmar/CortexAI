"""Prompt optimizer helpers used by orchestrator and API routes."""

import json
import os
from typing import Any, Optional, Tuple

from config.provider_catalog import (
    get_provider_api_key_envs,
    get_provider_default_model_envs,
    get_provider_default_models,
)
from models.unified_response import UnifiedResponse
from models.user_context import UserContext
from utils.logger import get_logger

logger = get_logger(__name__)

_PLAIN_SYSTEM_INSTRUCTION = (
    "You are a prompt optimization expert. "
    "Rewrite the given prompt to be clearer and more specific while preserving intent. "
    "Return only the improved prompt text."
)

_JSON_SYSTEM_INSTRUCTION = (
    "You are a prompt optimization expert. "
    "Rewrite the user prompt to be clearer and more specific while preserving intent exactly. "
    "Return strictly valid JSON with this schema: "
    '{"optimized_prompt": "string", "steps": ["string"], "explanations": ["string"], "metrics": {"key": number}}. '
    "Do not add markdown fences, commentary, or extra keys."
)

_DEFAULT_MODELS = get_provider_default_models()
_DEFAULT_MODEL_ENVS = get_provider_default_model_envs()
_API_KEY_ENVS = get_provider_api_key_envs()


class PromptOptimizer:
    """
    Optimize prompts before main model execution.

    Supports two modes:
    - optimize(prompt, orchestrator): route-level flow using orchestrator.ask
    - optimize_prompt(payload): direct provider client flow used by orchestrator internals
    """

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
        api_key: str | None = None,
        client: Any | None = None,
    ):
        self.provider = (provider or os.getenv("PROMPT_OPTIMIZER_PROVIDER", "gemini")).lower()
        self.model = model or os.getenv("PROMPT_OPTIMIZER_MODEL") or self._default_model_for_provider(
            self.provider
        )
        self.max_retries = max_retries or int(os.getenv("PROMPT_OPTIMIZER_MAX_RETRIES", "3"))
        self._api_key = api_key
        self._client = client

    def _default_model_for_provider(self, provider: str) -> str:
        env_key = _DEFAULT_MODEL_ENVS.get(provider)
        default_model = _DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        if not env_key:
            return default_model
        return os.getenv(env_key, default_model)

    def _resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key

        env_name = _API_KEY_ENVS.get(self.provider)
        if not env_name:
            raise ValueError(f"Unsupported provider for prompt optimizer: {self.provider}")
        api_key = os.getenv(env_name, "")
        if not api_key:
            raise ValueError(f"{env_name} not set for prompt optimizer provider '{self.provider}'")
        return api_key

    def _create_client(self):
        api_key = self._resolve_api_key()
        model_name = self.model

        if self.provider == "openai":
            from api.openai_client import OpenAIClient

            return OpenAIClient(api_key=api_key, model_name=model_name)
        if self.provider == "gemini":
            from api.google_gemini_client import GeminiClient

            return GeminiClient(api_key=api_key, model_name=model_name)
        if self.provider == "deepseek":
            from api.deepseek_client import DeepSeekClient

            return DeepSeekClient(api_key=api_key, model_name=model_name)
        if self.provider == "grok":
            from api.grok_client import GrokClient

            return GrokClient(api_key=api_key, model_name=model_name)

        raise ValueError(f"Unsupported provider for prompt optimizer: {self.provider}")

    def _get_client(self):
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _error_payload(self, message: str, code: str = "bad_request") -> dict[str, Any]:
        return {"error": {"code": code, "message": message}}

    def _validate_input(self, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return self._error_payload("Input must be a dictionary")

        if "prompt" not in payload:
            return self._error_payload("Missing required field: prompt")

        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            return self._error_payload("Prompt must be a string")
        if not prompt.strip():
            return self._error_payload("Prompt cannot be empty")

        settings = payload.get("settings")
        if settings is not None and not isinstance(settings, dict):
            return self._error_payload("settings must be a dictionary")

        return None

    def _is_valid_output(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        optimized = payload.get("optimized_prompt")
        if not isinstance(optimized, str) or not optimized.strip():
            return False

        steps = payload.get("steps")
        if steps is not None and (
            not isinstance(steps, list) or any(not isinstance(item, str) for item in steps)
        ):
            return False

        explanations = payload.get("explanations")
        if explanations is not None and (
            not isinstance(explanations, list)
            or any(not isinstance(item, str) for item in explanations)
        ):
            return False

        metrics = payload.get("metrics")
        if metrics is not None and not isinstance(metrics, dict):
            return False

        return True

    def _strip_markdown_fences(self, text: str) -> str:
        raw = text.strip()
        if raw.startswith("```") and raw.endswith("```"):
            lines = raw.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1]).strip()
        return raw

    def _parse_ai_response(self, response_text: str, original_prompt: str) -> dict[str, Any]:
        cleaned = self._strip_markdown_fences(response_text or "")
        try:
            parsed = json.loads(cleaned)
        except Exception as exc:
            raise ValueError("Invalid JSON from optimizer response") from exc

        if not self._is_valid_output(parsed):
            raise ValueError("Invalid optimizer response schema: missing or invalid optimized_prompt")

        result: dict[str, Any] = {
            "optimized_prompt": parsed["optimized_prompt"].strip() or original_prompt,
            "steps": parsed.get("steps", []),
            "explanations": parsed.get("explanations", []),
            "metrics": parsed.get("metrics", {}),
        }
        return result

    def _build_user_message(self, prompt: str, settings: dict[str, Any] | None) -> str:
        if not settings:
            return prompt
        settings_blob = json.dumps(settings, ensure_ascii=False)
        return f"Prompt:\n{prompt}\n\nOptimization settings:\n{settings_blob}"

    def optimize_prompt(self, payload: Any) -> dict[str, Any]:
        """
        Optimize prompt using direct provider client path.

        Returns a normalized dict and never raises for runtime/provider failures.
        """
        validation_error = self._validate_input(payload)
        if validation_error:
            return validation_error

        original_prompt = str(payload["prompt"]).strip()
        settings = payload.get("settings") if isinstance(payload, dict) else None

        client = self._get_client()
        last_error: str | None = None

        for _attempt in range(1, max(1, self.max_retries) + 1):
            response: UnifiedResponse = client.get_completion(
                messages=[
                    {"role": "system", "content": _JSON_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": self._build_user_message(original_prompt, settings)},
                ],
                model=self.model,
            )

            if response.is_error:
                last_error = response.error.message if response.error else "Optimizer request failed"
                continue

            try:
                return self._parse_ai_response(response.text, original_prompt)
            except Exception as exc:
                last_error = str(exc)
                continue

        return {
            "optimized_prompt": original_prompt,
            "steps": [],
            "explanations": [],
            "metrics": {},
            "error": {
                "code": "optimization_failed",
                "message": last_error or "Prompt optimization failed",
            },
        }

    def optimize(self, prompt: str, orchestrator) -> Tuple[str, bool]:
        """
        Optimize prompt using orchestrator path (used by /v1/optimize route).
        """
        if not prompt or not prompt.strip():
            return prompt, False

        context = UserContext(
            conversation_history=[
                {"role": "system", "content": _PLAIN_SYSTEM_INSTRUCTION}
            ]
        )

        try:
            response = orchestrator.ask(
                prompt=prompt,
                model_type=self.provider,
                model_name=self.model,
                context=context,
                token_tracker=None,
            )

            if response.is_error or not response.text:
                logger.warning(
                    "Prompt optimization failed - using original",
                    extra={"extra_fields": {
                        "error": str(response.error) if response.error else "empty_response"
                    }},
                )
                return prompt, False

            optimized = response.text.strip()
            if not optimized:
                return prompt, False

            logger.info(
                "Prompt optimized successfully",
                extra={"extra_fields": {
                    "original_len": len(prompt),
                    "optimized_len": len(optimized),
                    "provider": self.provider,
                }},
            )
            return optimized, True

        except Exception as exc:
            logger.error(
                f"PromptOptimizer error: {exc}",
                extra={"extra_fields": {"error_type": type(exc).__name__}},
            )
            return prompt, False
