from orchestrator.fallback_manager import FallbackManager, FallbackPolicy
from orchestrator.routing_types import NextAction, Tier, ValidationResult


def test_retry_same_tier_on_provider_error():
    manager = FallbackManager()
    policy = FallbackPolicy(max_attempts=2, max_total_latency_ms=12000, allow_escalation=True)
    decision = manager.decide(
        current_tier=Tier.T1,
        validation=ValidationResult(ok=False, reason="provider_error", severity="high"),
        attempt_index=0,
        elapsed_ms=100,
        remaining_same_tier_candidates=1,
        policy=policy,
        next_tier_fn=lambda t: Tier.T2,
    )
    assert decision.action == NextAction.RETRY_SAME_TIER


def test_escalate_on_format_violation():
    manager = FallbackManager()
    policy = FallbackPolicy(max_attempts=3, max_total_latency_ms=12000, allow_escalation=True)
    decision = manager.decide(
        current_tier=Tier.T1,
        validation=ValidationResult(ok=False, reason="format_violation", severity="high"),
        attempt_index=0,
        elapsed_ms=100,
        remaining_same_tier_candidates=0,
        policy=policy,
        next_tier_fn=lambda t: Tier.T2,
    )
    assert decision.action == NextAction.ESCALATE_TIER
    assert decision.next_tier == Tier.T2


def test_stop_when_attempts_exhausted():
    manager = FallbackManager()
    policy = FallbackPolicy(max_attempts=1, max_total_latency_ms=12000, allow_escalation=True)
    decision = manager.decide(
        current_tier=Tier.T1,
        validation=ValidationResult(ok=False, reason="provider_error", severity="high"),
        attempt_index=0,
        elapsed_ms=100,
        remaining_same_tier_candidates=1,
        policy=policy,
        next_tier_fn=lambda t: Tier.T2,
    )
    assert decision.action == NextAction.STOP


def test_retry_same_tier_on_refusal():
    manager = FallbackManager()
    policy = FallbackPolicy(max_attempts=3, max_total_latency_ms=12000, allow_escalation=True)
    decision = manager.decide(
        current_tier=Tier.T2,
        validation=ValidationResult(ok=False, reason="refusal", severity="medium"),
        attempt_index=1,
        elapsed_ms=500,
        remaining_same_tier_candidates=1,
        policy=policy,
        next_tier_fn=lambda t: Tier.T3,
    )
    assert decision.action == NextAction.RETRY_SAME_TIER
