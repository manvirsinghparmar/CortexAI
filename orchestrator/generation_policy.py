"""Provider-neutral generation-budget resolution.

This is the single authority for translating a public generation request into
an output ceiling and reasoning configuration. Routes pass the returned values
unchanged to both billing and provider execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from orchestrator.model_registry import ModelRegistry


PROFILE_ORDER = ("quick", "balanced", "deep", "extended")
LEGACY_PROFILE = "quick"


class GenerationPolicyError(ValueError):
    """Raised when a requested generation configuration is unsupported."""


@dataclass(frozen=True)
class GenerationBudgetResolution:
    profile: str
    requested_max_output_tokens: int
    effective_max_output_tokens: int
    requested_reasoning_mode: str
    effective_reasoning_mode: str
    requested_reasoning_effort: str
    effective_reasoning_effort: str
    reasoning_disable_supported: bool
    reasoning_counts_against_output: bool
    policy_version: str
    provider: str
    model: str

    @property
    def retry_profile(self) -> str | None:
        if self.profile not in PROFILE_ORDER:
            return None
        index = PROFILE_ORDER.index(self.profile)
        if index + 1 >= len(PROFILE_ORDER):
            return None
        return PROFILE_ORDER[index + 1]

    def provider_kwargs(self) -> dict[str, Any]:
        return {
            "max_tokens": self.effective_max_output_tokens,
            "reasoning_mode": self.effective_reasoning_mode,
            "reasoning_effort": self.effective_reasoning_effort,
        }

    def to_metadata(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "requested_max_output_tokens": self.requested_max_output_tokens,
            "effective_max_output_tokens": self.effective_max_output_tokens,
            "requested_reasoning_mode": self.requested_reasoning_mode,
            "effective_reasoning_mode": self.effective_reasoning_mode,
            "requested_reasoning_effort": self.requested_reasoning_effort,
            "effective_reasoning_effort": self.effective_reasoning_effort,
            "reasoning_disable_supported": self.reasoning_disable_supported,
            "reasoning_counts_against_output": self.reasoning_counts_against_output,
            "policy_version": self.policy_version,
            "retry_profile": self.retry_profile,
        }


@lru_cache(maxsize=4)
def load_generation_policy(path: str | None = None) -> dict[str, Any]:
    policy_path = (
        Path(path)
        if path
        else Path(__file__).resolve().parent.parent / "config" / "generation_profiles.yaml"
    )
    data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), dict):
        raise GenerationPolicyError("Invalid generation profile configuration")
    return data


def _value(source: object | Mapping[str, Any] | None, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _reasoning_value(generation: object | Mapping[str, Any] | None, name: str, default: str) -> str:
    reasoning = _value(generation, "reasoning")
    return str(_value(reasoning, name, default) or default).strip().lower()


def _supports_reasoning(provider: str, model: str, modes: list[str], tags: list[str]) -> bool:
    if modes:
        return any(mode != "none" for mode in modes)
    return "reasoning" in tags or (provider in {"openai", "claude"} and any(
        marker in model for marker in ("gpt-5", "claude-")
    ))


def _resolve_reasoning(
    *,
    provider: str,
    model: str,
    generation: object | Mapping[str, Any] | None,
    profile_effort: str,
    modes: list[str],
    efforts: list[str],
    default_mode: str | None,
    disable_supported: bool,
    tags: list[str],
) -> tuple[str, str, str, str]:
    requested_mode = _reasoning_value(generation, "mode", "auto")
    requested_effort = _reasoning_value(generation, "effort", "auto")
    if requested_mode not in {"auto", "off", "on"}:
        raise GenerationPolicyError(f"Unsupported reasoning mode '{requested_mode}'")
    allowed_efforts = {"auto", "minimal", "low", "medium", "high", "xhigh", "max"}
    if requested_effort not in allowed_efforts:
        raise GenerationPolicyError(f"Unsupported reasoning effort '{requested_effort}'")

    reasoning_supported = _supports_reasoning(provider, model, modes, tags)
    if not reasoning_supported:
        if requested_mode == "on" or requested_effort not in {"auto", "minimal", "low"}:
            raise GenerationPolicyError(f"{provider}:{model} does not support reasoning controls")
        return requested_mode, "off", requested_effort, "none"

    if requested_mode == "off" and not disable_supported:
        raise GenerationPolicyError(f"{provider}:{model} does not allow reasoning to be disabled")

    effort = profile_effort if requested_effort == "auto" else requested_effort
    mode = requested_mode
    if provider == "deepseek":
        if mode == "auto":
            mode = "on" if (default_mode or "thinking") != "none" else "off"
        effective_mode = "thinking" if mode == "on" else "none"
        effort = "max" if effort in {"xhigh", "max"} else "high"
    elif provider == "claude":
        effective_mode = "disabled" if mode == "off" else "adaptive"
        if effective_mode == "disabled" and effort in {"xhigh", "max"} and "opus-5" in model:
            raise GenerationPolicyError("Claude Opus 5 cannot disable reasoning at xhigh/max effort")
    elif provider == "gemini":
        can_disable = "none" in modes
        if mode == "off" and not can_disable:
            raise GenerationPolicyError(f"{provider}:{model} does not allow reasoning to be disabled")
        effective_mode = "none" if mode == "off" else "thinking"
        if effort in {"xhigh", "max"}:
            effort = "high"
    elif provider == "openai":
        effective_mode = "none" if mode == "off" else "standard"
        if effective_mode == "none":
            effort = "none"
    else:
        effective_mode = "none" if mode == "off" else (default_mode or effort)

    if efforts and effort not in efforts and effort != "none":
        if requested_effort != "auto":
            raise GenerationPolicyError(
                f"Reasoning effort '{effort}' is unsupported for {provider}:{model}"
            )
        effort_order = ["minimal", "low", "medium", "high", "xhigh", "max"]
        requested_rank = effort_order.index(effort) if effort in effort_order else 0
        supported = [item for item in effort_order if item in efforts]
        lower_or_equal = [item for item in supported if effort_order.index(item) <= requested_rank]
        if not lower_or_equal:
            raise GenerationPolicyError(
                f"No compatible reasoning effort is configured for {provider}:{model}"
            )
        effort = lower_or_equal[-1]

    return requested_mode, effective_mode, requested_effort, effort


def resolve_generation_budget(
    *,
    provider: str,
    model: str,
    generation: object | Mapping[str, Any] | None = None,
    legacy_max_tokens: int | None = None,
    estimated_input_tokens: int = 0,
    registry: ModelRegistry | None = None,
    policy_path: str | None = None,
) -> GenerationBudgetResolution:
    provider = str(provider or "").strip().lower()
    model = str(model or "").strip()
    registry = registry or ModelRegistry.from_yaml()
    candidate = registry.find_model(provider, model)
    if candidate is None:
        raise GenerationPolicyError(f"Unknown model '{provider}:{model}'")

    policy = load_generation_policy(policy_path)
    profiles = policy["profiles"]
    profile_value = _value(generation, "profile")
    explicit_max = _value(generation, "max_output_tokens")
    if profile_value not in (None, "") and explicit_max not in (None, ""):
        raise GenerationPolicyError("profile and max_output_tokens are mutually exclusive")
    if generation is not None and legacy_max_tokens is not None:
        raise GenerationPolicyError("generation and legacy max_tokens cannot be supplied together")

    if explicit_max not in (None, ""):
        if isinstance(explicit_max, bool) or int(explicit_max) <= 0:
            raise GenerationPolicyError("max_output_tokens must be a positive integer")
        requested_max = int(explicit_max)
        profile = "custom"
    elif legacy_max_tokens is not None:
        if isinstance(legacy_max_tokens, bool) or int(legacy_max_tokens) <= 0:
            raise GenerationPolicyError("max_tokens must be a positive integer")
        requested_max = int(legacy_max_tokens)
        profile = "custom"
    else:
        profile = str(profile_value or LEGACY_PROFILE).strip().lower()
        if profile not in profiles:
            raise GenerationPolicyError(f"Unknown generation profile '{profile}'")
        requested_max = int(profiles[profile]["max_output_tokens"])

    native_max = int(candidate.max_output_tokens or requested_max)
    operational_max = int(policy.get("operational_max_output_tokens") or native_max)
    context_margin = int(policy.get("context_safety_margin_tokens") or 0)
    remaining_context = max(1, int(candidate.context_limit) - max(0, estimated_input_tokens) - context_margin)
    allowed_max = min(native_max, operational_max, remaining_context)
    if profile == "custom" and requested_max > allowed_max:
        raise GenerationPolicyError(
            f"Requested max_output_tokens {requested_max} exceeds the allowed maximum {allowed_max} "
            f"for {provider}:{model}"
        )
    effective_max = min(requested_max, allowed_max)

    profile_config = profiles.get(profile) or {}
    profile_effort = str(profile_config.get("default_reasoning_effort") or "medium")
    requested_mode, effective_mode, requested_effort, effective_effort = _resolve_reasoning(
        provider=provider,
        model=model.lower(),
        generation=generation,
        profile_effort=profile_effort,
        modes=list(candidate.reasoning_modes or []),
        efforts=list(candidate.reasoning_efforts or []),
        default_mode=candidate.default_reasoning_mode,
        disable_supported=candidate.reasoning_disable_supported,
        tags=[str(tag).lower() for tag in candidate.tags],
    )

    return GenerationBudgetResolution(
        profile=profile,
        requested_max_output_tokens=requested_max,
        effective_max_output_tokens=effective_max,
        requested_reasoning_mode=requested_mode,
        effective_reasoning_mode=effective_mode,
        requested_reasoning_effort=requested_effort,
        effective_reasoning_effort=effective_effort,
        reasoning_disable_supported=candidate.reasoning_disable_supported,
        reasoning_counts_against_output=candidate.reasoning_counts_against_output,
        policy_version=str(policy.get("version") or "generation-budget-unknown"),
        provider=provider,
        model=model,
    )
