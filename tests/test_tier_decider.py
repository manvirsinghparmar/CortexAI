from orchestrator.routing_types import PromptFeatures, Tier
from orchestrator.tier_decider import TierDecider


def _base_features(**overrides):
    base = PromptFeatures(
        word_count=10,
        char_count=50,
        token_estimate=50,
        has_code=False,
        has_math=False,
        has_analysis=False,
        has_creative=False,
        has_factual=False,
        strict_format=False,
        has_logs_stacktrace=False,
        context_token_estimate=0,
        context_messages=0,
        is_follow_up=False,
        needs_latest_info=False,
        needs_accuracy=False,
        intent="general",
        has_strict_constraints=False,
    )
    return base.__class__(**{**base.__dict__, **overrides})


def test_tier_t0_for_simple_rewrite():
    decider = TierDecider()
    features = _base_features(intent="rewrite", token_estimate=200)
    decision = decider.decide(features)
    assert decision.tier == Tier.T0


def test_tier_t2_for_code():
    decider = TierDecider()
    features = _base_features(has_code=True)
    decision = decider.decide(features)
    assert decision.tier == Tier.T2


def test_tier_t3_for_ultra_strict():
    decider = TierDecider()
    features = _base_features(
        token_estimate=4000,
        strict_format=True,
        needs_accuracy=True,
        has_factual=True,
    )
    decision = decider.decide(features)
    assert decision.tier == Tier.T3


def test_tier_t3_for_complex_code_request():
    decider = TierDecider()
    features = _base_features(
        has_code=True,
        has_logs_stacktrace=True,
        needs_accuracy=True,
    )
    decision = decider.decide(features)
    assert decision.tier == Tier.T3
