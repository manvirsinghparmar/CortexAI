"""Cortex AI-credit accounting for cumulative Managed Agent session usage."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Mapping

from orchestrator.model_registry import ModelRegistry
from server.billing.credit_calculator import calculate_model_credit_charge

WORK_PRICING_VERSION = "managed-agents-2026-08-20"
MANAGED_RUNTIME_USD_PER_HOUR = Decimal("0.08")
CORTEX_CREDITS_PER_USD = Decimal("1000000")
ANTHROPIC_WEB_SEARCH_USD = Decimal("0.01")


def _int(mapping: Mapping[str, object], key: str) -> int:
    raw = mapping.get(key, 0)
    if not isinstance(raw, (str, int, float, bool)):
        return 0
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _nested(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _delta(current: int, baseline: int) -> int:
    return max(0, current - baseline)


@dataclass(frozen=True)
class WorkCreditUsage:
    total_credits: int
    model_credits: int
    input_credits: int
    output_credits: int
    runtime_credits: int
    web_credits: int
    prompt_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
    output_tokens: int
    active_seconds: int
    web_searches: int
    provider_cost_usd: float
    model: str
    pricing_version: str = WORK_PRICING_VERSION


def calculate_work_credit_usage(
    current: Mapping[str, object],
    baseline: Mapping[str, object],
    *,
    model: str,
) -> WorkCreditUsage:
    candidate = ModelRegistry.from_yaml().find_model("claude", model)
    if candidate is None or not candidate.enabled:
        raise ValueError(f"Managed Agent billing model is absent or disabled: {model}")

    cache_current = _nested(current, "cache_creation")
    cache_baseline = _nested(baseline, "cache_creation")
    prompt_tokens = _delta(_int(current, "input_tokens"), _int(baseline, "input_tokens"))
    output_tokens = _delta(_int(current, "output_tokens"), _int(baseline, "output_tokens"))
    cached = _delta(
        _int(current, "cache_read_input_tokens"),
        _int(baseline, "cache_read_input_tokens"),
    )
    cache_write = _delta(
        _int(cache_current, "ephemeral_5m_input_tokens")
        + _int(cache_current, "ephemeral_1h_input_tokens"),
        _int(cache_baseline, "ephemeral_5m_input_tokens")
        + _int(cache_baseline, "ephemeral_1h_input_tokens"),
    )
    active_seconds = _delta(_int(current, "active_seconds"), _int(baseline, "active_seconds"))
    tool_current = _nested(current, "server_tool_use")
    tool_baseline = _nested(baseline, "server_tool_use")
    web_searches = _delta(
        _int(tool_current, "web_search_requests"),
        _int(tool_baseline, "web_search_requests"),
    )

    charge = calculate_model_credit_charge(
        prompt_tokens=prompt_tokens,
        cached_input_tokens=min(prompt_tokens, cached),
        cache_write_tokens=min(prompt_tokens, cache_write),
        output_tokens=output_tokens,
        input_credit_multiplier=candidate.input_credit_multiplier,
        output_credit_multiplier=candidate.output_credit_multiplier,
        pricing_snapshot={
            "input": candidate.input_cost_per_1m,
            "cached_input": candidate.cached_input_cost_per_1m,
            "cache_write": candidate.cache_write_cost_per_1m,
            "pricing_version": candidate.credit_pricing_version,
        },
    )
    runtime_usd = (Decimal(active_seconds) / Decimal(3600)) * MANAGED_RUNTIME_USD_PER_HOUR
    web_usd = Decimal(web_searches) * ANTHROPIC_WEB_SEARCH_USD
    normal_input = max(
        0, prompt_tokens - min(prompt_tokens, cached) - min(prompt_tokens, cache_write)
    )
    cached_rate = candidate.cached_input_cost_per_1m or candidate.input_cost_per_1m
    cache_write_rate = candidate.cache_write_cost_per_1m or candidate.input_cost_per_1m
    model_usd = (
        Decimal(normal_input) * Decimal(str(candidate.input_cost_per_1m))
        + Decimal(min(prompt_tokens, cached)) * Decimal(str(cached_rate))
        + Decimal(min(prompt_tokens, cache_write)) * Decimal(str(cache_write_rate))
        + Decimal(output_tokens) * Decimal(str(candidate.output_cost_per_1m))
    ) / Decimal(1_000_000)
    runtime_credits = int(
        (runtime_usd * CORTEX_CREDITS_PER_USD).to_integral_value(rounding=ROUND_CEILING)
    )
    web_credits = int((web_usd * CORTEX_CREDITS_PER_USD).to_integral_value(rounding=ROUND_CEILING))
    return WorkCreditUsage(
        total_credits=charge.total_credits + runtime_credits + web_credits,
        model_credits=charge.total_credits,
        input_credits=charge.input_credits,
        output_credits=charge.output_credits,
        runtime_credits=runtime_credits,
        web_credits=web_credits,
        prompt_tokens=prompt_tokens,
        cached_input_tokens=min(prompt_tokens, cached),
        cache_write_tokens=min(prompt_tokens, cache_write),
        output_tokens=output_tokens,
        active_seconds=active_seconds,
        web_searches=web_searches,
        provider_cost_usd=float(model_usd + runtime_usd + web_usd),
        model=model,
    )
