from orchestrator.routing_types import PromptFeatures, Tier, TierDecision


class TierDecider:
    def __init__(self, thresholds: dict[str, int] | None = None):
        self._thresholds = thresholds or {}

    def decide(self, features: PromptFeatures) -> TierDecision:
        reasons: list[str] = []

        cheap_max_prompt_tokens = self._thresholds.get("cheap_max_prompt_tokens", 700)
        strong_prompt_tokens = self._thresholds.get("strong_prompt_tokens", 1800)
        ultra_prompt_tokens = self._thresholds.get("ultra_prompt_tokens", 3200)
        strong_context_tokens = self._thresholds.get("strong_context_tokens", 2200)

        if (
            features.token_estimate >= ultra_prompt_tokens
            and features.strict_format
            and features.needs_accuracy
            and features.has_factual
        ):
            reasons.append("ultra_strict_high_accuracy")
            return TierDecision(tier=Tier.T3, reasons=reasons)

        if features.has_code and (
            features.has_logs_stacktrace
            or features.needs_accuracy
            or features.has_strict_constraints
            or features.token_estimate >= strong_prompt_tokens
            or features.context_token_estimate >= strong_context_tokens
        ):
            reasons.append("complex_code_or_reasoning")
            return TierDecision(tier=Tier.T3, reasons=reasons)

        if (features.has_math or features.has_analysis) and (
            features.needs_accuracy
            or features.strict_format
            or features.token_estimate >= strong_prompt_tokens
            or features.context_token_estimate >= strong_context_tokens
        ):
            reasons.append("advanced_reasoning")
            return TierDecision(tier=Tier.T3, reasons=reasons)

        if features.has_strict_constraints and features.needs_accuracy and (
            features.has_factual or features.has_analysis
        ):
            reasons.append("strict_high_quality_output")
            return TierDecision(tier=Tier.T3, reasons=reasons)

        if (
            features.has_code
            or features.has_math
            or features.has_analysis
            or features.strict_format
            or features.has_logs_stacktrace
            or features.has_strict_constraints
        ):
            if features.has_code:
                reasons.append("code_detected")
            if features.has_math:
                reasons.append("math_detected")
            if features.has_analysis:
                reasons.append("analysis_detected")
            if features.strict_format:
                reasons.append("strict_format")
            if features.has_logs_stacktrace:
                reasons.append("logs_detected")
            if features.has_strict_constraints:
                reasons.append("strict_constraints")
            return TierDecision(tier=Tier.T2, reasons=reasons)

        if (
            features.token_estimate >= strong_prompt_tokens
            or features.context_token_estimate >= strong_context_tokens
        ):
            reasons.append("large_context_or_prompt")
            return TierDecision(tier=Tier.T2, reasons=reasons)

        if features.needs_accuracy and features.has_factual:
            reasons.append("high_accuracy_factual")
            return TierDecision(tier=Tier.T2, reasons=reasons)

        if (
            features.intent in ("rewrite", "summarize", "bullets", "brainstorm")
            and features.token_estimate < cheap_max_prompt_tokens
            and not features.strict_format
            and not features.has_code
            and not features.has_math
            and not features.has_analysis
        ):
            reasons.append("short_simple_rewrite")
            return TierDecision(tier=Tier.T0, reasons=reasons)

        reasons.append("default_t1")
        return TierDecision(tier=Tier.T1, reasons=reasons)
