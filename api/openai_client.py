import openai
from typing import Optional, Dict, Any, Tuple
from .base_client import BaseAIClient
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient(BaseAIClient):
    """
    A client for interacting with the OpenAI API.
    Handles API calls and response processing.
    """

    def __init__(self, api_key: str, model_name: str = "gpt-3.5-turbo", **kwargs):
        """
        Initialize the OpenAI client.
        
        Args:
            api_key: The OpenAI API key
            model_name: The name of the model to use (default: gpt-3.5-turbo)
            **kwargs: Additional keyword arguments
        """
        super().__init__(api_key, **kwargs)
        self.client = openai.OpenAI(api_key=api_key)
        self.model_name = model_name

    def get_completion(self, prompt: str, **kwargs) -> Tuple[Optional[str], Optional[Dict[str, int]]]:
        """
        Get a completion from the OpenAI API with token usage tracking.
        
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
        max_tokens = kwargs.get('max_tokens', 500)
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
                f"Error getting completion: {str(e)}",
                extra={"extra_fields": {"model": model, "error_type": type(e).__name__}}
            )
            return None, None
            
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
