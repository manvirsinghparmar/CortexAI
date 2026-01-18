from typing import List, Tuple, Optional

class ModelUtils:
    @staticmethod
    def list_available_models(api_key: str,current_model: str,  provider: str = "gemini") -> None:
        """
        List all available Gemini models that support content generation.
        
        Args:
            api_key: Provider API key
            current_model: Currently selected model name
            provider: Provider name (gemini or openai)
        """
        normalized_provider = provider.lower().strip()

        if normalized_provider == "gemini":
            from GeminiAvailableModels import GeminiClient as GeminiAvailableModels

            print("\n=== Fetching Available Gemini Models ===")
            models_client = GeminiAvailableModels(api_key=api_key, model_name=current_model)
            available_models = models_client.list_models()

            print("\n=== Available Gemini Models ===")
            for model, methods in available_models:
                if methods and 'generateContent' in methods:  # Only show models that support generation
                    current = " (current)" if model.endswith(current_model) else ""
                    print(f"- {model}{current}")
            print("\nNote: Only models supporting 'generateContent' are shown")
            return

        if normalized_provider == "openai":
            from api.openai_client import OpenAIClient

            print("\n=== Fetching Available OpenAI Models ===")
            OpenAIClient.list_available_models(
                api_key=api_key,
                current_model=current_model
            )
            return

        raise ValueError(f"Unsupported provider: {provider}")