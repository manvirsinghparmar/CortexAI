import openai
import time
from typing import Optional
from .base_client import BaseAIClient
from models.unified_response import UnifiedResponse, TokenUsage
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient(BaseAIClient):
    """
    OpenAI API client returning UnifiedResponse.

    All responses are normalized to UnifiedResponse format.
    No provider-specific response objects are exposed.
    """

    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", **kwargs):
        """
        Initialize the OpenAI client.

        Args:
            api_key: The OpenAI API key
            model_name: The name of the model to use (default: gpt-3.5-turbo)
            **kwargs: Additional keyword arguments
        """
        super().__init__(api_key, model_name=model_name, **kwargs)
        self.client = openai.OpenAI(api_key=api_key)
        self.model_name = model_name
        self.cost_calculator = CostCalculator(model_type='openai', model_name=model_name)

    def get_completion(
        self,
        prompt: str,
        *,
        save_full: bool = False,
        **kwargs
    ) -> UnifiedResponse:
        """
        Get a completion from the OpenAI API.

        Args:
            prompt: The input prompt to send to the model
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

        model = kwargs.get('model', self.model_name)
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 500)

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            latency_ms = self._measure_latency(start_time)

            # Extract text
            text = response.choices[0].message.content or ""

            # Extract token usage
            token_usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                completion_tokens=response.usage.completion_tokens if hasattr(response, 'usage') else 0,
                total_tokens=response.usage.total_tokens if hasattr(response, 'usage') else 0
            )

            # Calculate cost
            cost = self.cost_calculator.calculate_cost(
                token_usage.prompt_tokens,
                token_usage.completion_tokens
            )
            estimated_cost = cost['total_cost']

            # Normalize finish reason
            finish_reason = self._normalize_finish_reason(
                response.choices[0].finish_reason if response.choices else None,
                provider='openai'
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
                                "content": choice.message.content
                            },
                            "finish_reason": choice.finish_reason
                        }
                        for choice in response.choices
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    } if hasattr(response, 'usage') else None
                }

            logger.info(
                "OpenAI completion successful",
                extra={"extra_fields": {
                    "request_id": request_id,
                    "model": model,
                    "latency_ms": latency_ms,
                    "tokens": token_usage.total_tokens,
                    "cost": estimated_cost
                }}
            )

            return UnifiedResponse(
                request_id=request_id,
                text=text,
                provider="openai",
                model=model,
                latency_ms=latency_ms,
                token_usage=token_usage,
                estimated_cost=estimated_cost,
                finish_reason=finish_reason,
                error=None,
                metadata={},
                raw=raw
            )

        except Exception as e:
            latency_ms = self._measure_latency(start_time)
            error = self._normalize_error(e, provider='openai')

            logger.error(
                f"OpenAI completion failed: {error.code}",
                extra={"extra_fields": {
                    "request_id": request_id,
                    "model": model,
                    "error_code": error.code,
                    "error_message": error.message,
                    "retryable": error.retryable
                }}
            )

            return self._create_error_response(
                request_id=request_id,
                error=error,
                latency_ms=latency_ms,
                model=model
            )

    @classmethod
    def list_available_models(cls, api_key: str = None, **kwargs) -> None:
        """
        List all available OpenAI models.

        Args:
            api_key: The OpenAI API key
            **kwargs: Additional parameters
                - current_model: The currently selected model (will be highlighted)
        """
        try:
            client = openai.OpenAI(api_key=api_key) if api_key else None
            if not client:
                logger.warning("API key not provided for listing models")
                print("API key not provided. Cannot list available models.")
                return

            current_model = kwargs.get('current_model', 'gpt-3.5-turbo')

            # Get the list of available models
            models = client.models.list()

            logger.info(
                "Listed available OpenAI models",
                extra={"extra_fields": {"model_count": len(models.data), "current_model": current_model}}
            )

            print("\n=== Available OpenAI Models ===")
            for model in sorted(models.data, key=lambda x: x.id):
                prefix = "* " if model.id == current_model else "  "
                print(f"{prefix}{model.id}")
            print("* = currently selected\n")

        except Exception as e:
            logger.error(
                f"Error listing available models: {str(e)}",
                extra={"extra_fields": {"error_type": type(e).__name__}}
            )
            print(f"Error listing available models: {str(e)}")
