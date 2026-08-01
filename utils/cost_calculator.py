"""Provider-cost calculation with auditable pricing-rule snapshots."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from config.pricing import ModelPricing
from utils.logger import get_logger


logger = get_logger(__name__)


class PricingUnavailableError(RuntimeError):
    """Raised when neither an exact nor a conservative pricing rule exists."""


class CostCalculator:
    """Calculate provider cost independently from CortexAI credit charging."""

    def __init__(
        self,
        model_type: str,
        model_name: str,
        *,
        catalog_path: str | Path | None = None,
    ):
        self.model_type = model_type.lower()
        self.model_name = model_name
        self.catalog_path = catalog_path
        self.pricing = ModelPricing.get_model_pricing(
            self.model_type,
            self.model_name,
            catalog_path=self.catalog_path,
        )

        self.total_input_cost = 0.0
        self.total_output_cost = 0.0
        self.total_cost = 0.0

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        *,
        cached_input_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        processing_mode: str = "standard",
        request_at: datetime | str | None = None,
        cache_write_ttl: str = "5m",
    ) -> dict[str, Any]:
        """Calculate one call and return both amounts and pricing evidence.

        ``prompt_tokens`` is normalized to include uncached, cache-read, and
        cache-write input. ``completion_tokens`` is normalized to include any
        provider-reported reasoning tokens, so reasoning is recorded separately
        but never double billed.
        """

        prompt = max(0, int(prompt_tokens or 0))
        completion = max(0, int(completion_tokens or 0))
        cached = min(prompt, max(0, int(cached_input_tokens or 0)))
        cache_write = min(
            max(0, prompt - cached),
            max(0, int(cache_write_tokens or 0)),
        )
        normal_input = max(0, prompt - cached - cache_write)
        reasoning = min(completion, max(0, int(reasoning_tokens or 0)))

        pricing = ModelPricing.get_pricing_snapshot(
            self.model_type,
            self.model_name,
            at=request_at,
            prompt_tokens=prompt,
            processing_mode=processing_mode,
            cache_write_ttl=cache_write_ttl,
            catalog_path=self.catalog_path,
        )
        pricing_unknown = pricing is None
        if pricing is None:
            pricing = ModelPricing.conservative_fallback(
                self.model_type,
                at=request_at,
                prompt_tokens=prompt,
                processing_mode=processing_mode,
                catalog_path=self.catalog_path,
            )
            if pricing is not None:
                logger.warning(
                    "Exact provider pricing unavailable; applying conservative fallback",
                    extra={
                        "extra_fields": {
                            "provider": self.model_type,
                            "served_model": self.model_name,
                            "pricing_rule_applied": pricing.get("pricing_rule_id"),
                            "prompt_tokens": prompt,
                            "completion_tokens": completion,
                        }
                    },
                )
        if pricing is None:
            raise PricingUnavailableError(
                f"No pricing or conservative fallback for {self.model_type}:{self.model_name}"
            )

        input_cost = normal_input * float(pricing["input"]) / 1_000_000
        cached_input_cost = cached * float(pricing["cached_input"]) / 1_000_000
        cache_write_cost = cache_write * float(pricing["cache_write"]) / 1_000_000
        output_cost = completion * float(pricing["output"]) / 1_000_000
        total_cost = input_cost + cached_input_cost + cache_write_cost + output_cost

        return {
            "input_cost": input_cost,
            "cached_input_cost": cached_input_cost,
            "cache_write_cost": cache_write_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "normal_input_tokens": normal_input,
            "cached_input_tokens": cached,
            "cache_write_tokens": cache_write,
            "completion_tokens": completion,
            "reasoning_tokens": reasoning,
            "pricing_unknown": pricing_unknown,
            "pricing_rule_applied": pricing["pricing_rule_id"],
            "pricing_version": pricing["pricing_version"],
            "pricing_model": pricing.get("pricing_model") or self.model_name,
            "processing_mode": pricing["processing_mode"],
            "long_context_applied": bool(pricing["long_context_applied"]),
            "source_url": pricing.get("source_url"),
            "source_verified_at": pricing.get("source_verified_at"),
            "rates_per_1m": {
                "input": float(pricing["input"]),
                "cached_input": float(pricing["cached_input"]),
                "cache_write": float(pricing["cache_write"]),
                "output": float(pricing["output"]),
            },
        }

    def update_cumulative_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        **kwargs: Any,
    ) -> None:
        costs = self.calculate_cost(prompt_tokens, completion_tokens, **kwargs)
        self.total_input_cost += (
            float(costs["input_cost"])
            + float(costs["cached_input_cost"])
            + float(costs["cache_write_cost"])
        )
        self.total_output_cost += float(costs["output_cost"])
        self.total_cost += float(costs["total_cost"])

    def get_cumulative_cost(self) -> dict[str, float]:
        return {
            "total_input_cost": self.total_input_cost,
            "total_output_cost": self.total_output_cost,
            "total_cost": self.total_cost,
        }

    def format_cost(self, cost: float, currency: str = "USD") -> str:
        if currency == "USD":
            return f"${cost:.6f}"
        return f"{cost:.6f} {currency}"

    def get_pricing_info(self) -> dict[str, Any]:
        snapshot = ModelPricing.get_pricing_snapshot(
            self.model_type,
            self.model_name,
            catalog_path=self.catalog_path,
        )
        if snapshot is None:
            return {
                "model_type": self.model_type,
                "model_name": self.model_name,
                "pricing_available": False,
                "message": "Exact pricing is unavailable; calls use a flagged conservative fallback",
            }
        return {
            "model_type": self.model_type,
            "model_name": self.model_name,
            "pricing_available": True,
            "input_price_per_million": snapshot["input"],
            "cached_input_price_per_million": snapshot["cached_input"],
            "cache_write_price_per_million": snapshot["cache_write"],
            "output_price_per_million": snapshot["output"],
            "pricing_rule_applied": snapshot["pricing_rule_id"],
            "pricing_version": snapshot["pricing_version"],
            "source_url": snapshot.get("source_url"),
            "source_verified_at": snapshot.get("source_verified_at"),
        }

    def format_summary(self) -> str:
        return (
            f"Input cost: {self.format_cost(self.total_input_cost)}\n"
            f"Output cost: {self.format_cost(self.total_output_cost)}\n"
            f"Total cost: {self.format_cost(self.total_cost)}"
        )

    def reset(self) -> None:
        self.total_input_cost = 0.0
        self.total_output_cost = 0.0
        self.total_cost = 0.0
