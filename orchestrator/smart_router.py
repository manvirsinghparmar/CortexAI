from typing import Any

from models.user_context import UserContext
from orchestrator.model_registry import ModelRegistry
from orchestrator.model_selector import ModelSelector
from orchestrator.prompt_analyzer import PromptAnalyzer
from orchestrator.response_validator import ResponseValidator
from orchestrator.routing_types import ModelCandidate, PromptFeatures, RoutingConstraints, Tier
from orchestrator.tier_decider import TierDecider


class SmartRouter:
    def __init__(
        self,
        *,
        registry: ModelRegistry,
        selector: ModelSelector,
        validator: ResponseValidator,
        fallback_manager: Any,
        analyzer: PromptAnalyzer,
        decider: TierDecider,
    ):
        self._registry = registry
        self._selector = selector
        self._validator = validator
        self._fallback_manager = fallback_manager
        self._analyzer = analyzer
        self._decider = decider

    def route_once_plan(
        self,
        prompt: str,
        context: UserContext | None,
        routing_mode: str,
        constraints: RoutingConstraints | None,
    ) -> tuple[PromptFeatures, Tier, list[ModelCandidate], dict[str, Any]]:
        features = self._analyzer.analyze(prompt, context)
        features = self._apply_constraints(features, constraints)

        forced_tier = self._resolve_forced_tier(routing_mode)
        if forced_tier:
            tier = forced_tier
            reasons = [f"forced_mode_{routing_mode}"]
        else:
            decision = self._decider.decide(features)
            tier = decision.tier
            reasons = decision.reasons

        candidates = self._registry.get_candidates(tier, constraints)
        selection = self._selector.select(features, candidates, constraints)
        ordered_candidates = [selection.primary_candidate, *selection.fallback_candidates]

        metadata = self.make_metadata(
            mode=routing_mode,
            initial_tier=tier,
            final_tier=tier,
            decision_reasons=reasons,
        )
        metadata["selection"] = {
            "primary_provider": selection.primary_candidate.provider,
            "primary_model": selection.primary_candidate.model_name,
            "primary_blended_cost_per_1m": round(
                (0.6 * selection.primary_candidate.input_cost_per_1m)
                + (0.4 * selection.primary_candidate.output_cost_per_1m),
                6,
            ),
            "fallback_count": len(selection.fallback_candidates),
        }

        return features, tier, ordered_candidates, metadata

    def make_metadata(
        self,
        *,
        mode: str,
        initial_tier: Tier,
        final_tier: Tier,
        decision_reasons: list[str],
    ) -> dict[str, Any]:
        return {
            "mode": mode,
            "initial_tier": initial_tier.value,
            "final_tier": final_tier.value,
            "attempt_count": 0,
            "fallback_used": False,
            "attempts": [],
            "decision_reasons": decision_reasons,
        }

    def _apply_constraints(
        self, features: PromptFeatures, constraints: RoutingConstraints | None
    ) -> PromptFeatures:
        if not constraints:
            return features

        strict = features.strict_format
        has_strict = features.has_strict_constraints
        if constraints.strict_format or constraints.json_only:
            strict = True
            has_strict = True

        return PromptFeatures(
            word_count=features.word_count,
            char_count=features.char_count,
            token_estimate=features.token_estimate,
            has_code=features.has_code,
            has_math=features.has_math,
            has_analysis=features.has_analysis,
            has_creative=features.has_creative,
            has_factual=features.has_factual,
            strict_format=strict,
            has_logs_stacktrace=features.has_logs_stacktrace,
            context_token_estimate=features.context_token_estimate,
            context_messages=features.context_messages,
            is_follow_up=features.is_follow_up,
            needs_latest_info=features.needs_latest_info,
            needs_accuracy=features.needs_accuracy,
            intent=features.intent,
            has_strict_constraints=has_strict,
        )

    def _resolve_forced_tier(self, routing_mode: str) -> Tier | None:
        if routing_mode == "cheap":
            return Tier.T0
        if routing_mode == "strong":
            return Tier.T2
        return None
