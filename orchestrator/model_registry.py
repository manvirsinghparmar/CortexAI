from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from orchestrator.routing_types import ModelCandidate, RoutingConstraints, Tier


@dataclass
class ModelRegistry:
    _providers: dict[str, list[ModelCandidate]]
    _routing_defaults: dict[str, Any]

    @classmethod
    def from_yaml(cls, path: str | None = None) -> "ModelRegistry":
        registry_path = Path(path) if path else Path(__file__).resolve().parent.parent / "config" / "model_registry.yaml"
        if not registry_path.exists():
            raise ValueError(f"Model registry not found at {registry_path}")

        data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        if not data or "providers" not in data:
            raise ValueError("Invalid model registry: missing providers")

        providers: dict[str, list[ModelCandidate]] = {}
        for provider, pdata in data["providers"].items():
            models = pdata.get("models", [])
            if not isinstance(models, list):
                raise ValueError(f"Invalid models list for provider {provider}")
            candidates: list[ModelCandidate] = []
            for model in models:
                required = [
                    "name",
                    "tier",
                    "input_cost_per_1m",
                    "output_cost_per_1m",
                    "context_limit",
                    "tags",
                ]
                if any(key not in model for key in required):
                    raise ValueError(f"Missing required fields in model for provider {provider}")
                tier = Tier(model["tier"])
                candidates.append(
                    ModelCandidate(
                        provider=provider,
                        model_name=model["name"],
                        tier=tier,
                        input_cost_per_1m=float(model["input_cost_per_1m"]),
                        output_cost_per_1m=float(model["output_cost_per_1m"]),
                        context_limit=int(model["context_limit"]),
                        tags=list(model.get("tags", [])),
                        enabled=bool(model.get("enabled", True)),
                    )
                )
            providers[provider] = candidates

        routing_defaults = data.get("routing_defaults", {})
        return cls(_providers=providers, _routing_defaults=routing_defaults)

    def routing_defaults(self) -> dict[str, Any]:
        return self._routing_defaults

    def next_tier(self, tier: Tier) -> Tier | None:
        tier_order = self._routing_defaults.get("tier_order", ["T0", "T1", "T2", "T3"])
        if tier.value not in tier_order:
            raise ValueError(f"Invalid tier {tier}")
        idx = tier_order.index(tier.value)
        if idx + 1 >= len(tier_order):
            return None
        return Tier(tier_order[idx + 1])

    def get_candidates(
        self, tier: Tier, constraints: RoutingConstraints | None = None
    ) -> list[ModelCandidate]:
        if not isinstance(tier, Tier):
            raise ValueError(f"Invalid tier: {tier}")

        allowed = None
        if constraints and constraints.allowed_providers is not None:
            allowed = [p.lower() for p in constraints.allowed_providers]
        else:
            allow_defaults = self._routing_defaults.get("allow_providers")
            if allow_defaults:
                allowed = [p.lower() for p in allow_defaults]

        results: list[ModelCandidate] = []
        for provider, models in self._providers.items():
            if allowed and provider.lower() not in allowed:
                continue
            for candidate in models:
                if not candidate.enabled:
                    continue
                if candidate.tier != tier:
                    continue
                if constraints and constraints.min_context_limit is not None:
                    if candidate.context_limit < constraints.min_context_limit:
                        continue
                results.append(candidate)

        return results

    def find_model(self, provider: str, model_name: str) -> ModelCandidate | None:
        provider_norm = (provider or "").lower().strip()
        model_norm = (model_name or "").strip()
        if not provider_norm or not model_norm:
            return None

        models = self._providers.get(provider_norm, [])
        for candidate in models:
            if candidate.model_name == model_norm:
                return candidate
        return None

    def is_enabled_model(self, provider: str, model_name: str) -> bool:
        candidate = self.find_model(provider, model_name)
        return bool(candidate and candidate.enabled)

    def list_enabled_models(self) -> list[ModelCandidate]:
        out: list[ModelCandidate] = []
        for candidates in self._providers.values():
            out.extend([c for c in candidates if c.enabled])
        return out
