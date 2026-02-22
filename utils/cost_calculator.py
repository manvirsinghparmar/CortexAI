"""
Cost calculation module for tracking API usage costs.
This module provides cost estimation based on token usage and model pricing.
"""

from typing import Any

from config.pricing import ModelPricing


class CostCalculator:
    """
    Calculate costs based on token usage and model pricing.
    This class maintains separation from token tracking logic.
    """

    def __init__(self, model_type: str, model_name: str):
        """
        Initialize the cost calculator with model information.

        Args:
            model_type: The type of model ('openai', 'gemini', 'deepseek', 'grok')
            model_name: The specific model name
        """
        self.model_type = model_type.lower()
        self.model_name = model_name
        self.pricing = ModelPricing.get_model_pricing(self.model_type, self.model_name)

        # Track cumulative costs
        self.total_input_cost = 0.0
        self.total_output_cost = 0.0
        self.total_cost = 0.0

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> dict[str, float]:
        """
        Calculate cost for a single API call.

        Args:
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens

        Returns:
            Dictionary containing:
                - input_cost: Cost for input tokens
                - output_cost: Cost for output tokens
                - total_cost: Total cost for this call
        """
        if not self.pricing:
            # If pricing not available, return zero costs
            return {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}

        # Calculate costs (pricing is per million tokens)
        input_cost = (prompt_tokens * self.pricing["input"]) / 1_000_000
        output_cost = (completion_tokens * self.pricing["output"]) / 1_000_000
        total_cost = input_cost + output_cost

        return {"input_cost": input_cost, "output_cost": output_cost, "total_cost": total_cost}

    def update_cumulative_cost(self, prompt_tokens: int, completion_tokens: int) -> None:
        """
        Update cumulative cost tracking.

        Args:
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens
        """
        costs = self.calculate_cost(prompt_tokens, completion_tokens)
        self.total_input_cost += costs["input_cost"]
        self.total_output_cost += costs["output_cost"]
        self.total_cost += costs["total_cost"]

    def get_cumulative_cost(self) -> dict[str, float]:
        """
        Get cumulative costs for all API calls.

        Returns:
            Dictionary containing:
                - total_input_cost: Total cost for all input tokens
                - total_output_cost: Total cost for all output tokens
                - total_cost: Total cost for all API calls
        """
        return {
            "total_input_cost": self.total_input_cost,
            "total_output_cost": self.total_output_cost,
            "total_cost": self.total_cost,
        }

    def format_cost(self, cost: float, currency: str = "USD") -> str:
        """
        Format cost as a currency string.

        Args:
            cost: Cost amount
            currency: Currency code (default: 'USD')

        Returns:
            Formatted cost string
        """
        if currency == "USD":
            return f"${cost:.6f}"
        return f"{cost:.6f} {currency}"

    def get_pricing_info(self) -> dict[str, Any]:
        """
        Get pricing information for the current model.

        Returns:
            Dictionary containing pricing information or None if not available
        """
        if not self.pricing:
            return {
                "model_type": self.model_type,
                "model_name": self.model_name,
                "pricing_available": False,
                "message": "Pricing information not available for this model",
            }

        return {
            "model_type": self.model_type,
            "model_name": self.model_name,
            "pricing_available": True,
            "input_price_per_million": self.pricing["input"],
            "output_price_per_million": self.pricing["output"],
        }

    def format_summary(self) -> str:
        """
        Format cumulative cost summary as a human-readable string.

        Returns:
            Formatted string with cost breakdown
        """
        if not self.pricing:
            return "Cost tracking not available (pricing information not found for this model)"

        return (
            f"Input cost: {self.format_cost(self.total_input_cost)}\n"
            f"Output cost: {self.format_cost(self.total_output_cost)}\n"
            f"Total cost: {self.format_cost(self.total_cost)}"
        )

    def reset(self) -> None:
        """Reset cumulative cost tracking."""
        self.total_input_cost = 0.0
        self.total_output_cost = 0.0
        self.total_cost = 0.0
