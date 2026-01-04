import openai
from typing import Optional, Dict, Any, Tuple
from .base_client import BaseAIClient
from utils.logger import get_logger

logger = get_logger(__name__)


class DeepSeekClient(BaseAIClient):
    """
    A client for interacting with the DeepSeek API.
    Uses OpenAI SDK with custom base URL since DeepSeek API is OpenAI-compatible.
    """

    def __init__(self, api_key: str, model_name: str = "deepseek-chat", **kwargs):
        """
        Initialize the DeepSeek client.

        Args:
            api_key: The DeepSeek API key
            model_name: The name of the model to use (default: deepseek-chat)
                Options:
                - "deepseek-chat" (V3.2): Best for general chat and discussion
                - "deepseek-reasoner" (R1): Best for reasoning, math, and coding tasks
            **kwargs: Additional keyword arguments
        """
        super().__init__(api_key, **kwargs)
        # Initialize OpenAI client with DeepSeek endpoint
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        self.model_name = model_name

    def get_completion(self, prompt: str, **kwargs) -> Tuple[Optional[str], Optional[Dict[str, int]]]:
        """
        Get a completion from the DeepSeek API with token usage tracking.

        Args:
            prompt: The input prompt to send to the model
            **kwargs: Additional parameters for the API call
                - model: Override the default model for this call
                - temperature: Controls randomness (0.0 to 2.0)
                - max_tokens: Maximum number of tokens to generate
                - return_usage: If True, returns token usage information

        Returns:
            A tuple of (response_text, usage_dict) where usage_dict contains
            token usage information (prompt_tokens, completion_tokens, total_tokens)
        """
        model = kwargs.get('model', self.model_name)
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 2048)
        return_usage = kwargs.get('return_usage', True)

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            usage = None
            if return_usage and hasattr(response, 'usage'):
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }

            return response.choices[0].message.content, usage

        except Exception as e:
            logger.error(
                f"Error getting completion from DeepSeek: {str(e)}",
                extra={"extra_fields": {"model": model, "error_type": type(e).__name__}}
            )
            return None, None

    @classmethod
    def list_available_models(cls, api_key: str = None, **kwargs) -> None:
        """
        List all available DeepSeek models.

        Args:
            api_key: The DeepSeek API key
            **kwargs: Additional parameters
                - current_model: The currently selected model (will be highlighted)
        """
        try:
            if not api_key:
                logger.warning("API key not provided for listing DeepSeek models")
                print("API key not provided. Cannot list available models.")
                return

            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
            current_model = kwargs.get('current_model', 'deepseek-chat')

            # Get the list of available models
            models = client.models.list()

            logger.info(
                "Listed available DeepSeek models",
                extra={"extra_fields": {"model_count": len(models.data), "current_model": current_model}}
            )

            print("\n=== Available DeepSeek Models ===")
            for model in sorted(models.data, key=lambda x: x.id):
                prefix = "* " if model.id == current_model else "  "
                # Add description for known models
                description = ""
                if model.id == "deepseek-chat":
                    description = " (V3.2 - General chat & discussion)"
                elif model.id == "deepseek-reasoner":
                    description = " (R1 - Advanced reasoning & coding)"
                print(f"{prefix}{model.id}{description}")
            print("* = currently selected\n")

        except Exception as e:
            logger.error(
                f"Error listing available DeepSeek models: {str(e)}",
                extra={"extra_fields": {"error_type": type(e).__name__}}
            )
            print(f"Error listing available models: {str(e)}")
