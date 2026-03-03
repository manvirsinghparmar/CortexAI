import time
from typing import Any

try:
    import anthropic
except Exception:
    anthropic = None

from models.unified_response import TokenUsage, UnifiedResponse
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

from .base_client import BaseAIClient

logger = get_logger(__name__)


class ClaudeClient(BaseAIClient):
    """
    Anthropic Claude client returning UnifiedResponse.

    All responses are normalized to UnifiedResponse format.
    """

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-5", **kwargs):
        if anthropic is None:
            raise ValueError(
                "anthropic package is not installed. Install dependencies from requirements.txt."
            )
        super().__init__(api_key, model_name=model_name, **kwargs)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model_name
        self.cost_calculator = CostCalculator(model_type="claude", model_name=model_name)

    def _convert_messages_to_claude_format(
        self, messages: list[dict[str, str]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Convert normalized messages into Anthropic Messages API shape.
        """
        system_instruction = None
        claude_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = str(msg.get("role", "user")).strip().lower()
            content = str(msg.get("content", ""))

            if role == "system":
                if system_instruction is None:
                    system_instruction = content
                continue

            if role not in {"user", "assistant"}:
                role = "user"

            claude_messages.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": content}],
                }
            )

        if not claude_messages:
            claude_messages = [{"role": "user", "content": [{"type": "text", "text": ""}]}]

        return system_instruction, claude_messages

    def _extract_text(self, response: Any) -> str:
        parts = getattr(response, "content", None) or []
        chunks: list[str] = []
        for part in parts:
            part_type = getattr(part, "type", "")
            if part_type == "text":
                chunks.append(str(getattr(part, "text", "") or ""))
        return "".join(chunks).strip()

    def get_completion(
        self,
        prompt: str | None = None,
        *,
        messages: list | None = None,
        save_full: bool = False,
        **kwargs,
    ) -> UnifiedResponse:
        request_id = self._generate_request_id()
        start_time = time.time()

        model = kwargs.get("model", self.model_name)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)

        try:
            normalized_messages = self._normalize_input(prompt=prompt, messages=messages)
            system_instruction, claude_messages = self._convert_messages_to_claude_format(
                normalized_messages
            )

            request_payload: dict[str, Any] = {
                "model": model,
                "messages": claude_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system_instruction:
                request_payload["system"] = system_instruction

            response = self.client.messages.create(**request_payload)
            latency_ms = self._measure_latency(start_time)

            text = self._extract_text(response)
            usage = getattr(response, "usage", None)
            prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            token_usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

            cost = self.cost_calculator.calculate_cost(
                token_usage.prompt_tokens, token_usage.completion_tokens
            )
            estimated_cost = cost["total_cost"]

            finish_reason = self._normalize_finish_reason(
                getattr(response, "stop_reason", None),
                provider="claude",
            )

            raw = None
            if save_full:
                raw = {
                    "id": getattr(response, "id", None),
                    "model": getattr(response, "model", model),
                    "stop_reason": getattr(response, "stop_reason", None),
                    "usage": {
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "total_tokens": token_usage.total_tokens,
                    },
                }

            logger.info(
                "Claude completion successful",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "model": model,
                        "latency_ms": latency_ms,
                        "tokens": token_usage.total_tokens,
                        "cost": estimated_cost,
                    }
                },
            )

            return UnifiedResponse(
                request_id=request_id,
                text=text,
                provider="claude",
                model=model,
                latency_ms=latency_ms,
                token_usage=token_usage,
                estimated_cost=estimated_cost,
                finish_reason=finish_reason,
                error=None,
                metadata={},
                raw=raw,
            )

        except Exception as e:
            latency_ms = self._measure_latency(start_time)
            error = self._normalize_error(e, provider="claude")

            logger.error(
                f"Claude completion failed: {error.code}",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "model": model,
                        "error_code": error.code,
                        "error_message": error.message,
                        "retryable": error.retryable,
                    }
                },
            )

            return self._create_error_response(
                request_id=request_id, error=error, latency_ms=latency_ms, model=model
            )

    @classmethod
    def list_available_models(cls, api_key: str = None, **kwargs) -> None:
        try:
            if anthropic is None:
                print("anthropic package is not installed. Cannot list Claude models.")
                return
            if not api_key:
                logger.warning("API key not provided for listing Claude models")
                print("API key not provided. Cannot list available models.")
                return

            current_model = kwargs.get("current_model", "claude-sonnet-4-5")
            client = anthropic.Anthropic(api_key=api_key)

            fallback_models = [
                "claude-3-5-haiku-latest",
                "claude-3-5-sonnet-latest",
                "claude-sonnet-4",
                "claude-sonnet-4-5",
                "claude-opus-4-5",
            ]
            model_ids: list[str] = []

            try:
                if hasattr(client, "models") and hasattr(client.models, "list"):
                    listed = client.models.list()
                    if hasattr(listed, "data"):
                        model_ids = [
                            str(getattr(model, "id", "") or "")
                            for model in listed.data
                            if str(getattr(model, "id", "") or "").strip()
                        ]
                    else:
                        model_ids = [
                            str(getattr(model, "id", "") or "")
                            for model in listed
                            if str(getattr(model, "id", "") or "").strip()
                        ]
            except Exception:
                model_ids = []

            if not model_ids:
                model_ids = fallback_models

            logger.info(
                "Listed available Claude models",
                extra={
                    "extra_fields": {
                        "model_count": len(model_ids),
                        "current_model": current_model,
                    }
                },
            )

            print("\n=== Available Claude Models ===")
            for model_id in sorted(model_ids):
                prefix = "* " if model_id == current_model else "  "
                print(f"{prefix}{model_id}")
            print("* = currently selected\n")

        except Exception as e:
            logger.error(
                f"Error listing available Claude models: {e!s}",
                extra={"extra_fields": {"error_type": type(e).__name__}},
            )
            print(f"Error listing available models: {e!s}")
