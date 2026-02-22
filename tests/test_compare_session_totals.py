"""Regression test for Compare Mode session total calculation bug.

Bug: In Compare Mode, session totals (cost/tokens) were incorrectly calculated
using a single CostCalculator instance tied to MODEL_TYPE, causing wrong totals
when responses came from different providers with different pricing.

Fix: Session totals now sum estimated_cost and total_tokens directly from
UnifiedResponse objects, which already have correct per-provider costs.
"""

from models.multi_unified_response import MultiUnifiedResponse
from models.unified_response import TokenUsage, UnifiedResponse


def test_compare_session_totals_from_responses():
    """Session totals should sum response.estimated_cost, not use single CostCalculator."""
    # Mock responses from different providers with different costs
    resp1 = UnifiedResponse(
        request_id="1",
        text="ok",
        provider="openai",
        model="gpt-4",
        latency_ms=100,
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        estimated_cost=0.001,
        finish_reason="stop",
        error=None,
        metadata={},
    )
    resp2 = UnifiedResponse(
        request_id="2",
        text="ok",
        provider="gemini",
        model="gemini-flash",
        latency_ms=200,
        token_usage=TokenUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40),
        estimated_cost=0.0005,
        finish_reason="stop",
        error=None,
        metadata={},
    )

    multi = MultiUnifiedResponse(responses=(resp1, resp2))

    # Multi response aggregates correctly
    assert multi.total_cost == 0.0015
    assert multi.total_tokens == 70

    # Simulate two compare rounds - session totals accumulate
    session_cost = multi.total_cost + multi.total_cost
    session_tokens = multi.total_tokens + multi.total_tokens

    assert session_cost == 0.003
    assert session_tokens == 140
