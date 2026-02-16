import os


class ModelUtils:
    @staticmethod
    def list_available_models(api_key: str, current_model: str, provider: str = "gemini") -> None:
        """
        List models available for a provider.

        Args:
            api_key: Provider API key
            current_model: Currently selected model name
            provider: Provider name (gemini, openai, deepseek, grok)
        """
        normalized_provider = provider.lower().strip()

        if normalized_provider == "gemini":
            try:
                from GeminiAvailableModels import GeminiClient as GeminiAvailableModels
            except ImportError:
                from utils.GeminiAvailableModels import GeminiClient as GeminiAvailableModels

            print("\n=== Fetching Available Gemini Models ===")
            try:
                models_client = GeminiAvailableModels(api_key=api_key, model_name=current_model)
                available_models = models_client.list_models()
            except Exception as e:
                print(f"\nWarning: Failed to fetch Gemini models - {e}")
                return

            print("\n=== Available Gemini Models ===")
            shown = 0
            for model, methods in available_models:
                method_list = list(methods) if methods else []
                normalized_methods = [m.lower() for m in method_list]
                supports_generation = any(
                    m in {"generatecontent", "models.generatecontent"} for m in normalized_methods
                )
                if supports_generation:
                    current = " (current)" if model.endswith(current_model) else ""
                    print(f"- {model}{current}")
                    shown += 1

            if shown == 0:
                print("- No models explicitly reporting 'generateContent' support were returned.")
                print("- Raw models returned by API:")
                for model, methods in available_models:
                    method_text = ", ".join(methods) if methods else "methods unavailable"
                    print(f"  - {model} [{method_text}]")
            else:
                print("\nNote: Only models supporting 'generateContent' are shown")
            return

        if normalized_provider == "openai":
            from api.openai_client import OpenAIClient

            print("\n=== Fetching Available OpenAI Models ===")
            try:
                OpenAIClient.list_available_models(api_key=api_key, current_model=current_model)
            except Exception as e:
                print(f"\nWarning: Failed to fetch OpenAI models - {e}")
            return

        if normalized_provider == "deepseek":
            from api.deepseek_client import DeepSeekClient

            print("\n=== Fetching Available DeepSeek Models ===")
            try:
                DeepSeekClient.list_available_models(api_key=api_key, current_model=current_model)
            except Exception as e:
                print(f"\nWarning: Failed to fetch DeepSeek models - {e}")
            return

        if normalized_provider == "grok":
            from api.grok_client import GrokClient

            print("\n=== Fetching Available Grok Models ===")
            try:
                GrokClient.list_available_models(api_key=api_key, current_model=current_model)
            except Exception as e:
                print(f"\nWarning: Failed to fetch Grok models - {e}")
            return

        raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def list_all_available_models(
        api_keys: dict[str, str] | None = None,
        current_models: dict[str, str] | None = None,
        providers: list[str] | None = None,
    ) -> None:
        """
        List models for all supported providers in one call.

        Args:
            api_keys: Optional provider->api_key mapping.
            current_models: Optional provider->current model mapping.
            providers: Optional list of providers to include.
        """
        selected_providers = providers or ["openai", "gemini", "deepseek", "grok"]

        env_api_keys = {
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "gemini": os.getenv("GOOGLE_GEMINI_API_KEY", ""),
            "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
            "grok": os.getenv("GROK_API_KEY", ""),
        }
        env_current_models = {
            "openai": os.getenv("DEFAULT_OPENAI_MODEL", "gpt-4o-mini"),
            "gemini": os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash-lite"),
            "deepseek": os.getenv("DEFAULT_DEEPSEEK_MODEL", "deepseek-chat"),
            "grok": os.getenv("DEFAULT_GROK_MODEL", "grok-4-latest"),
        }

        merged_api_keys = {**env_api_keys, **(api_keys or {})}
        merged_current_models = {**env_current_models, **(current_models or {})}

        print("\n=== Model Discovery (All Providers) ===")
        for provider in selected_providers:
            normalized_provider = provider.lower().strip()
            if normalized_provider not in env_api_keys:
                print(f"\n[{provider}] Skipped: unsupported provider")
                continue

            api_key = merged_api_keys.get(normalized_provider, "")
            current_model = merged_current_models.get(normalized_provider, "")

            if not api_key:
                print(f"\n[{normalized_provider}] Skipped: missing API key")
                continue

            print(f"\n--- {normalized_provider.upper()} ---")
            try:
                ModelUtils.list_available_models(
                    api_key=api_key,
                    current_model=current_model,
                    provider=normalized_provider,
                )
            except Exception as e:
                print(f"Warning: Failed listing for {normalized_provider} - {e}")
