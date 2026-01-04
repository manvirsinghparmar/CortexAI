import os
from typing import Optional, Dict, Any, Tuple

from google import genai
from .base_client import BaseAIClient
from utils.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(BaseAIClient):
    """
    A client for interacting with the Google Gemini API using the new google.genai package.
    Handles API calls and response processing.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash", **kwargs):
        """
        Initialize the Gemini client.

        Args:
            api_key: The Google Gemini API key
            model_name: The name of the model to use (default: gemini-1.5-flash)
            **kwargs: Additional keyword arguments
        """
        super().__init__(api_key, **kwargs)

        if not api_key:
            raise ValueError("API key is required for Gemini")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def get_completion(self, prompt: str, **kwargs) -> Tuple[Optional[str], Optional[Dict[str, int]]]:
        """
        Get a completion from the Gemini API.

        Args:
            prompt: The input prompt to send to the model
            **kwargs: Additional parameters for the API call
                - model: Override the default model for this call
                - temperature: Controls randomness (0.0 to 1.0)
                - max_output_tokens: Maximum number of tokens to generate
                - return_usage: If True, returns token usage information

        Returns:
            A tuple of (response_text, usage_dict) where usage_dict contains
            token usage information (prompt_tokens, completion_tokens, total_tokens)
        """
        model_name = kwargs.get('model', self.model_name)
        temperature = kwargs.get('temperature', 0.7)
        max_output_tokens = kwargs.get('max_output_tokens', 2048)
        return_usage = kwargs.get('return_usage', True)

        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'temperature': temperature,
                    'max_output_tokens': max_output_tokens,
                }
            )

            text = response.text if hasattr(response, 'text') else None

            if not return_usage:
                return text, None

            # Try to get usage information if available
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage_metadata = response.usage_metadata
                usage = {
                    'prompt_tokens': getattr(usage_metadata, 'prompt_token_count', 0),
                    'completion_tokens': getattr(usage_metadata, 'candidates_token_count', 0),
                    'total_tokens': getattr(usage_metadata, 'total_token_count', 0)
                }

            return text, usage

        except Exception as e:
            logger.error(
                f"Error getting completion from Gemini: {str(e)}",
                extra={"extra_fields": {"model": model_name, "error_type": type(e).__name__}}
            )
            return None, None

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
        response, usage = client.get_completion(
            "Hello, how can I help you today?",
            return_usage=True
        )
        print(response)
        print(usage)