import time

import openai

from models.unified_response import TokenUsage, UnifiedResponse
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

from .base_client import BaseAIClient

logger = get_logger(__name__)


class GrokClient(BaseAIClient):
    """
    Grok API client returning UnifiedResponse.

    Uses OpenAI SDK with custom base URL since Grok API is OpenAI-compatible.
    All responses are normalized to UnifiedResponse format.
    """

    def __init__(self, api_key: str, model_name: str = "grok-4-latest", **kwargs):
        """
        Initialize the Grok client.

        Args:
            api_key: The Grok API key (from X.AI)
            model_name: The name of the model to use (default: grok-4-latest)
            **kwargs: Additional keyword arguments
        """
        super().__init__(api_key, model_name=model_name, **kwargs)
        self.client = openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        self.model_name = model_name
        self.cost_calculator = CostCalculator(model_type="grok", model_name=model_name)

    def get_completion(
        self,
        prompt: str | None = None,
        *,
        messages: list | None = None,
        save_full: bool = False,
        **kwargs,
    ) -> UnifiedResponse:
        """
        Get a completion from the Grok API.

        Args:
            prompt: (Legacy) Single string prompt - converted to messages format
            messages: (Multi-turn) List of message dicts with 'role' and 'content' keys
            save_full: If True, include raw provider response in response.raw
            **kwargs: Additional parameters:
                - model: Override the default model for this call
                - temperature: Controls randomness (0.0 to 2.0)
                - max_tokens: Maximum number of tokens to generate

        Returns:
            UnifiedResponse: Normalized response object

        IMPORTANT: Never raises exceptions - returns UnifiedResponse with error instead
        """
        request_id = self._generate_request_id()
        start_time = time.time()

        model = kwargs.get("model", self.model_name)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 2048)

        try:
            # Normalize input to messages format
            normalized_messages = self._normalize_input(prompt=prompt, messages=messages)

            response = self.client.chat.completions.create(
                model=model,
                messages=normalized_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            latency_ms = self._measure_latency(start_time)

            # Extract text
            text = response.choices[0].message.content or ""

            # Extract token usage
            token_usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if hasattr(response, "usage") else 0,
                completion_tokens=(
                    response.usage.completion_tokens if hasattr(response, "usage") else 0
                ),
                total_tokens=response.usage.total_tokens if hasattr(response, "usage") else 0,
            )

            # Calculate cost
            cost = self.cost_calculator.calculate_cost(
                token_usage.prompt_tokens, token_usage.completion_tokens
            )
            estimated_cost = cost["total_cost"]

            # Normalize finish reason
            finish_reason = self._normalize_finish_reason(
                response.choices[0].finish_reason if response.choices else None, provider="grok"
            )

            # Build raw response if requested
            raw = None
            if save_full:
                raw = {
                    "id": response.id,
                    "object": response.object,
                    "created": response.created,
                    "model": response.model,
                    "choices": [
                        {
                            "index": choice.index,
                            "message": {
                                "role": choice.message.role,
                                "content": choice.message.content,
                            },
                            "finish_reason": choice.finish_reason,
                        }
                        for choice in response.choices
                    ],
                    "usage": (
                        {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        }
                        if hasattr(response, "usage")
                        else None
                    ),
                }

            logger.info(
                "Grok completion successful",
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
                provider="grok",
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
            error = self._normalize_error(e, provider="grok")

            logger.error(
                f"Grok completion failed: {error.code}",
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
        """
        List all available Grok models.

        Args:
            api_key: The Grok API key
            **kwargs: Additional parameters
                - current_model: The currently selected model (will be highlighted)
        """
        try:
            if not api_key:
                logger.warning("API key not provided for listing Grok models")
                print("API key not provided. Cannot list available models.")
                return

            client = openai.OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            current_model = kwargs.get("current_model", "grok-4-latest")

            # Get the list of available models
            models = client.models.list()

            logger.info(
                "Listed available Grok models",
                extra={
                    "extra_fields": {
                        "model_count": len(models.data),
                        "current_model": current_model,
                    }
                },
            )

            print("\n=== Available Grok Models ===")
            for model in sorted(models.data, key=lambda x: x.id):
                prefix = "* " if model.id == current_model else "  "
                # Add description for known models
                description = ""
                if model.id == "grok-4-latest":
                    description = " (Latest Grok model)"
                print(f"{prefix}{model.id}{description}")
            print("* = currently selected\n")

        except Exception as e:
            logger.error(
                f"Error listing available Grok models: {e!s}",
                extra={"extra_fields": {"error_type": type(e).__name__}},
            )
            print(f"Error listing available models: {e!s}")
