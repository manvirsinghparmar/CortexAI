from dataclasses import dataclass
from typing import Callable

from orchestrator.routing_types import FallbackDecision, NextAction, Tier, ValidationResult


@dataclass(frozen=True)
class FallbackPolicy:
    max_attempts: int = 2
    max_total_latency_ms: int = 12000
    allow_escalation: bool = True


class FallbackManager:
    def decide(
        self,
        *,
        current_tier: Tier,
        validation: ValidationResult,
        attempt_index: int,
        elapsed_ms: int,
        remaining_same_tier_candidates: int,
        policy: FallbackPolicy,
        next_tier_fn: Callable[[Tier], Tier | None],
    ) -> FallbackDecision:
        if attempt_index + 1 >= policy.max_attempts:
            return FallbackDecision(action=NextAction.STOP, next_tier=None, reason="max_attempts")

        if elapsed_ms >= policy.max_total_latency_ms:
            return FallbackDecision(action=NextAction.STOP, next_tier=None, reason="latency_budget")

        if validation.reason in {"provider_error", "rate_limit", "timeout", "refusal"}:
            if remaining_same_tier_candidates > 0:
                return FallbackDecision(
                    action=NextAction.RETRY_SAME_TIER, next_tier=None, reason=validation.reason
                )
            if validation.reason == "refusal" and policy.allow_escalation:
                next_tier = next_tier_fn(current_tier)
                if next_tier is not None:
                    return FallbackDecision(
                        action=NextAction.ESCALATE_TIER,
                        next_tier=next_tier,
                        reason=validation.reason,
                    )

        if validation.reason in {"too_short", "format_violation", "truncated"}:
            if policy.allow_escalation:
                next_tier = next_tier_fn(current_tier)
                if next_tier is not None:
                    return FallbackDecision(
                        action=NextAction.ESCALATE_TIER,
                        next_tier=next_tier,
                        reason=validation.reason,
                    )

        return FallbackDecision(action=NextAction.STOP, next_tier=None, reason=validation.reason)
