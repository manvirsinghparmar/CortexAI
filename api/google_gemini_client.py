import os
import time
from typing import Optional
from google import genai
from .base_client import BaseAIClient
from models.unified_response import UnifiedResponse, TokenUsage
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(BaseAIClient):
    """
    Google Gemini API client returning UnifiedResponse.

    Uses google.genai package.
    All responses are normalized to UnifiedResponse format.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash", **kwargs):
        """
        Initialize the Gemini client.

        Args:
            api_key: The Google Gemini API key
            model_name: The name of the model to use (default: gemini-1.5-flash)
            **kwargs: Additional keyword arguments
        """
        super().__init__(api_key, model_name=model_name, **kwargs)

        if not api_key:
            raise ValueError("API key is required for Gemini")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.cost_calculator = CostCalculator(model_type='gemini', model_name=model_name)

    def get_completion(
        self,
        prompt: str,
        *,
        save_full: bool = False,
        **kwargs
    ) -> UnifiedResponse:
        """
        Get a completion from the Gemini API.

        Args:
            prompt: The input prompt to send to the model
            save_full: If True, include raw provider response in response.raw
            **kwargs: Additional parameters:
                - model: Override the default model for this call
                - temperature: Controls randomness (0.0 to 1.0)
                - max_output_tokens: Maximum number of tokens to generate

        Returns:
            UnifiedResponse: Normalized response object

        IMPORTANT: Never raises exceptions - returns UnifiedResponse with error instead
        """
        request_id = self._generate_request_id()
        start_time = time.time()

        model_name = kwargs.get('model', self.model_name)
        temperature = kwargs.get('temperature', 0.7)
        max_output_tokens = kwargs.get('max_output_tokens', 2048)

        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'temperature': temperature,
                    'max_output_tokens': max_output_tokens,
                }
            )

            latency_ms = self._measure_latency(start_time)

            # Extract text
            text = response.text if hasattr(response, 'text') else ""

            # Extract token usage
            token_usage = TokenUsage()
            if hasattr(response, 'usage_metadata'):
                usage_metadata = response.usage_metadata
                token_usage = TokenUsage(
                    prompt_tokens=getattr(usage_metadata, 'prompt_token_count', 0),
                    completion_tokens=getattr(usage_metadata, 'candidates_token_count', 0),
                    total_tokens=getattr(usage_metadata, 'total_token_count', 0)
                )

            # Calculate cost
            cost = self.cost_calculator.calculate_cost(
                token_usage.prompt_tokens,
                token_usage.completion_tokens
            )
            estimated_cost = cost['total_cost']

            # Extract finish reason from Gemini response
            finish_reason_raw = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason_raw = str(candidate.finish_reason)

            # Normalize finish reason
            finish_reason = self._normalize_finish_reason(
                finish_reason_raw,
                provider='gemini'
            )

            # Build raw response if requested
            raw = None
            if save_full:
                raw = {
                    "text": text,
                    "usage_metadata": {
                        "prompt_token_count": token_usage.prompt_tokens,
                        "candidates_token_count": token_usage.completion_tokens,
                        "total_token_count": token_usage.total_tokens
                    } if hasattr(response, 'usage_metadata') else None,
                    "candidates": [
                        {
                            "finish_reason": finish_reason_raw
                        }
                    ] if hasattr(response, 'candidates') else []
                }

            logger.info(
                "Gemini completion successful",
                extra={"extra_fields": {
                    "request_id": request_id,
                    "model": model_name,
                    "latency_ms": latency_ms,
                    "tokens": token_usage.total_tokens,
                    "cost": estimated_cost
                }}
            )

            return UnifiedResponse(
                request_id=request_id,
                text=text,
                provider="gemini",
                model=model_name,
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
            error = self._normalize_error(e, provider='gemini')

            logger.error(
                f"Gemini completion failed: {error.code}",
                extra={"extra_fields": {
                    "request_id": request_id,
                    "model": model_name,
                    "error_code": error.code,
                    "error_message": error.message,
                    "retryable": error.retryable
                }}
            )

            return self._create_error_response(
                request_id=request_id,
                error=error,
                latency_ms=latency_ms,
                model=model_name
            )

    @classmethod
    def list_available_models(cls, api_key: str = None, **kwargs) -> None:
        """
        List all available Gemini models.

        Args:
            api_key: The Google Gemini API key
            **kwargs: Additional parameters
                - current_model: The currently selected model (will be highlighted)
        """
        try:
            if not api_key:
                logger.warning("API key not provided for listing Gemini models")
                print("API key not provided. Cannot list available models.")
                return

            client = genai.Client(api_key=api_key)
            current_model = kwargs.get('current_model', 'gemini-1.5-flash')

            # Get the list of available models
            models = client.models.list()

            model_list = list(models)
            logger.info(
                "Listed available Gemini models",
                extra={"extra_fields": {"model_count": len(model_list), "current_model": current_model}}
            )

            print("\n=== Available Gemini Models ===")
            for model in model_list:
                # Check if model supports content generation
                if hasattr(model, 'supported_generation_methods') and 'generateContent' in model.supported_generation_methods:
                    prefix = "* " if model.name == current_model else "  "
                    print(f"{prefix}{model.name} (supports: {', '.join(model.supported_generation_methods)})")
                elif hasattr(model, 'name'):
                    # Fallback if supported_generation_methods is not available
                    prefix = "* " if model.name == current_model else "  "
                    print(f"{prefix}{model.name}")
            print("* = currently selected\n")

        except Exception as e:
            logger.error(
                f"Error listing available Gemini models: {str(e)}",
                extra={"extra_fields": {"error_type": type(e).__name__}}
            )
            print(f"Error listing available models: {str(e)}")


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
    model_name = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-1.5-flash")

    if not api_key:
        print("Error: GOOGLE_GEMINI_API_KEY not found in environment variables")
    else:
        client = GeminiClient(api_key=api_key, model_name=model_name)
        response = client.get_completion("Hello, how can I help you today?")
        print(f"Text: {response.text}")
        print(f"Tokens: {response.token_usage.total_tokens}")
        print(f"Cost: ${response.estimated_cost:.6f}")
