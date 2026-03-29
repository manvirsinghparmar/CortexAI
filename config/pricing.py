"""
Model pricing configuration.
All prices are in USD per million tokens.
Prices are updated as of February 2026.
"""


class ModelPricing:
    """Pricing information for different AI models."""

    # OpenAI Models Pricing (per million tokens)
    OPENAI_PRICING = {
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-5.1": {"input": 1.25, "output": 10.00},
        "gpt-5.2-codex": {"input": 1.75, "output": 14.00},
        # GPT-4 Models
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-4-32k": {"input": 60.00, "output": 120.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
        "gpt-4-0125-preview": {"input": 10.00, "output": 30.00},
        "gpt-4-1106-preview": {"input": 10.00, "output": 30.00},
        "gpt-4-vision-preview": {"input": 10.00, "output": 30.00},
        # GPT-3.5 Models
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
        "gpt-3.5-turbo-16k": {"input": 3.00, "output": 4.00},
        "gpt-3.5-turbo-instruct": {"input": 1.50, "output": 2.00},
        # Legacy Models
        "davinci-002": {"input": 2.00, "output": 2.00},
        "babbage-002": {"input": 0.40, "output": 0.40},
    }

    # Google Gemini Models Pricing (per million tokens)
    # Note: Gemini 2.5 pricing is tiered by prompt size; these are <=200k token rates.
    GEMINI_PRICING = {
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-2.0-flash-exp": {"input": 0.00, "output": 0.00},  # Free during preview
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-1.0-pro": {"input": 0.50, "output": 1.50},
        "gemini-1.0-pro-001": {"input": 0.50, "output": 1.50},
    }

    # DeepSeek Models Pricing (per million tokens)
    # Note: uses current cache-miss input pricing for a simple one-rate estimator.
    DEEPSEEK_PRICING = {
        "deepseek-chat": {"input": 0.28, "output": 0.42},
        "deepseek-reasoner": {"input": 0.28, "output": 0.42},
    }

    # Grok Models Pricing (per million tokens)
    GROK_PRICING = {
        "grok-4-latest": {"input": 3.00, "output": 15.00},
        "grok-4-1-fast-non-reasoning": {"input": 0.20, "output": 0.50},
        "grok-4-1-fast-reasoning": {"input": 0.20, "output": 0.50},
        "grok-2": {"input": 2.00, "output": 10.00},
        "grok-2-mini": {"input": 0.50, "output": 2.50},
    }

    # Anthropic Claude Models Pricing (per million tokens)
    CLAUDE_PRICING = {
        "claude-3-5-haiku-latest": {"input": 0.80, "output": 4.00},
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
        "claude-sonnet-4": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
        "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-opus-4-5": {"input": 5.00, "output": 25.00},
        "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    }

    @classmethod
    def get_model_pricing(cls, model_type: str, model_name: str) -> dict[str, float] | None:
        """
        Get pricing information for a specific model.

        Args:
            model_type: The type of model ('openai', 'gemini', 'deepseek', 'grok', 'claude')
            model_name: The specific model name

        Returns:
            Dictionary with 'input' and 'output' pricing per million tokens,
            or None if pricing not found
        """
        model_type = model_type.lower()

        pricing_map = {
            "openai": cls.OPENAI_PRICING,
            "gemini": cls.GEMINI_PRICING,
            "deepseek": cls.DEEPSEEK_PRICING,
            "grok": cls.GROK_PRICING,
            "claude": cls.CLAUDE_PRICING,
        }

        pricing_dict = pricing_map.get(model_type)
        if not pricing_dict:
            return None

        return pricing_dict.get(model_name)

    @classmethod
    def list_all_pricing(
        cls, model_type: str | None = None
    ) -> dict[str, dict[str, dict[str, float]]]:
        """
        List all pricing information, optionally filtered by model type.

        Args:
            model_type: Optional model type to filter by

        Returns:
            Dictionary of all pricing information
        """
        all_pricing = {
            "openai": cls.OPENAI_PRICING,
            "gemini": cls.GEMINI_PRICING,
            "deepseek": cls.DEEPSEEK_PRICING,
            "grok": cls.GROK_PRICING,
            "claude": cls.CLAUDE_PRICING,
        }

        if model_type:
            model_type = model_type.lower()
            return {model_type: all_pricing.get(model_type, {})}

        return all_pricing
