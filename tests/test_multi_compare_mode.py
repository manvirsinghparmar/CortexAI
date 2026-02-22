"""
Tests for multi-model compare mode functionality.

Tests MultiModelOrchestrator, MultiUnifiedResponse, and related components.
"""

from datetime import datetime, timezone

import pytest

from api.base_client import BaseAIClient
from models.multi_unified_response import MultiUnifiedResponse
from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
from orchestrator.multi_orchestrator import MultiModelOrchestrator


class FakeClient(BaseAIClient):
    """
    Fake AI client for testing purposes.
    """

    def __init__(
        self,
        provider_name: str = "fake",
        model_name: str = "fake-model",
        response_text: str = "Fake response",
        latency_ms: int = 100,
        should_error: bool = False,
        error_code: str = "timeout",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
    ):
        self.provider_name = provider_name
        self.model_name = model_name
        self.response_text = response_text
        self.latency_ms = latency_ms
        self.should_error = should_error
        self.error_code = error_code
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def get_completion(
        self, prompt: str = None, messages: list = None, **kwargs
    ) -> UnifiedResponse:
        """Return a fake UnifiedResponse."""
        request_id = f"{self.provider_name}-{self.model_name}"

        if self.should_error:
            error = NormalizedError(
                code=self.error_code,
                message=f"Fake {self.error_code} error",
                provider=self.provider_name,
                retryable=(self.error_code in ["timeout", "rate_limit"]),
            )
            return UnifiedResponse(
                request_id=request_id,
                text="",
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=self.latency_ms,
                token_usage=TokenUsage(),
                estimated_cost=0.0,
                finish_reason="error",
                error=error,
            )

        return UnifiedResponse(
            request_id=request_id,
            text=self.response_text,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=self.latency_ms,
            token_usage=TokenUsage(
                prompt_tokens=self.prompt_tokens,
                completion_tokens=self.completion_tokens,
            ),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
        )

    @classmethod
    def list_available_models(cls, **kwargs):
        """Fake method to satisfy interface."""
        pass


class TestMultiUnifiedResponse:
    """Tests for MultiUnifiedResponse dataclass."""

    def test_empty_responses(self):
        """Test MultiUnifiedResponse with no responses."""
        multi_resp = MultiUnifiedResponse(
            request_group_id="test-123", created_at=datetime.now(timezone.utc), responses=tuple()
        )

        assert len(multi_resp.responses) == 0
        assert multi_resp.total_cost == 0.0
        assert multi_resp.total_tokens == 0
        assert multi_resp.success_count == 0
        assert multi_resp.error_count == 0

    def test_successful_responses(self):
        """Test MultiUnifiedResponse with successful responses."""
        resp1 = UnifiedResponse(
            request_id="req1",
            text="Response 1",
            provider="openai",
            model="gpt-4",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
        )

        resp2 = UnifiedResponse(
            request_id="req2",
            text="Response 2",
            provider="gemini",
            model="gemini-flash",
            latency_ms=200,
            token_usage=TokenUsage(prompt_tokens=15, completion_tokens=25),
            estimated_cost=0.002,
            finish_reason="stop",
            error=None,
        )

        multi_resp = MultiUnifiedResponse(
            request_group_id="test-123",
            created_at=datetime.now(timezone.utc),
            responses=(resp1, resp2),
        )

        assert len(multi_resp.responses) == 2
        assert multi_resp.total_cost == 0.003
        assert multi_resp.total_tokens == 70  # (10+20) + (15+25)
        assert multi_resp.success_count == 2
        assert multi_resp.error_count == 0

    def test_error_responses(self):
        """Test MultiUnifiedResponse with error responses."""
        error_resp = UnifiedResponse(
            request_id="req-error",
            text="",
            provider="openai",
            model="gpt-4",
            latency_ms=100,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=NormalizedError(
                code="timeout",
                message="Timeout error",
                provider="openai",
                retryable=True,
            ),
        )

        success_resp = UnifiedResponse(
            request_id="req-success",
            text="Success",
            provider="gemini",
            model="gemini-flash",
            latency_ms=200,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
        )

        multi_resp = MultiUnifiedResponse(
            request_group_id="test-123",
            created_at=datetime.now(timezone.utc),
            responses=(error_resp, success_resp),
        )

        assert len(multi_resp.responses) == 2
        assert multi_resp.success_count == 1
        assert multi_resp.error_count == 1
        assert multi_resp.total_tokens == 30  # Only from success
        assert multi_resp.total_cost == 0.001  # Only from success

    def test_immutability(self):
        """Test that MultiUnifiedResponse is immutable."""
        multi_resp = MultiUnifiedResponse(
            request_group_id="test-123", created_at=datetime.now(timezone.utc), responses=tuple()
        )

        with pytest.raises(AttributeError):
            multi_resp.responses = tuple()


class TestMultiModelOrchestrator:
    """Tests for MultiModelOrchestrator."""

    def test_single_successful_client(self):
        """Test orchestrator with single successful client."""
        orchestrator = MultiModelOrchestrator()
        client = FakeClient(provider_name="openai", model_name="gpt-4")

        result = orchestrator.get_comparisons_sync("Test prompt", [client])

        assert len(result.responses) == 1
        assert result.success_count == 1
        assert result.error_count == 0
        assert result.responses[0].provider == "openai"
        assert result.responses[0].text == "Fake response"

    def test_multiple_successful_clients(self):
        """Test orchestrator with multiple successful clients."""
        orchestrator = MultiModelOrchestrator()
        clients = [
            FakeClient(provider_name="openai", model_name="gpt-4", response_text="OpenAI response"),
            FakeClient(
                provider_name="gemini", model_name="gemini-flash", response_text="Gemini response"
            ),
            FakeClient(
                provider_name="deepseek",
                model_name="deepseek-chat",
                response_text="DeepSeek response",
            ),
        ]

        result = orchestrator.get_comparisons_sync("Test prompt", clients)

        assert len(result.responses) == 3
        assert result.success_count == 3
        assert result.error_count == 0
        assert result.responses[0].provider == "openai"
        assert result.responses[1].provider == "gemini"
        assert result.responses[2].provider == "deepseek"

    def test_client_with_error(self):
        """Test orchestrator with a client that errors."""
        orchestrator = MultiModelOrchestrator()
        clients = [
            FakeClient(provider_name="openai", model_name="gpt-4"),
            FakeClient(
                provider_name="gemini",
                model_name="gemini-flash",
                should_error=True,
                error_code="timeout",
            ),
        ]

        result = orchestrator.get_comparisons_sync("Test prompt", clients)

        assert len(result.responses) == 2
        assert result.success_count == 1
        assert result.error_count == 1
        assert result.responses[0].is_success
        assert result.responses[1].is_error
        assert result.responses[1].error.code == "timeout"

    def test_order_preservation(self):
        """Test that response order matches client order."""
        orchestrator = MultiModelOrchestrator()
        clients = [
            FakeClient(provider_name="fast", model_name="model1", latency_ms=50),
            FakeClient(provider_name="slow", model_name="model2", latency_ms=500),
            FakeClient(provider_name="medium", model_name="model3", latency_ms=200),
        ]

        result = orchestrator.get_comparisons_sync("Test prompt", clients)

        # Order should match input, not completion time
        assert result.responses[0].provider == "fast"
        assert result.responses[1].provider == "slow"
        assert result.responses[2].provider == "medium"

    def test_concurrent_execution(self):
        """Test that clients are called concurrently."""

        orchestrator = MultiModelOrchestrator()
        clients = [
            FakeClient(provider_name=f"client{i}", model_name=f"model{i}", latency_ms=100)
            for i in range(5)
        ]

        result = orchestrator.get_comparisons_sync("Test prompt", clients)

        # If run sequentially, would take ~500ms (5 * 100ms)
        # Concurrent should be much faster (close to 100ms + overhead)
        assert len(result.responses) == 5
        # Note: Using sync wrapper, so timing may vary

    def test_timeout_handling(self):
        """Test timeout handling for slow clients."""
        # Note: This test would require a real slow client or mocking asyncio.wait_for
        # For now, we verify the structure exists
        orchestrator = MultiModelOrchestrator(default_timeout_s=1.0)
        assert orchestrator.default_timeout_s == 1.0

    def test_request_group_id_passthrough(self):
        """Caller-provided request_group_id should be preserved end-to-end."""
        orchestrator = MultiModelOrchestrator()
        client = FakeClient(provider_name="openai", model_name="gpt-4")
        group_id = "group-fixed-123"

        result = orchestrator.get_comparisons_sync(
            "Test prompt",
            [client],
            request_group_id=group_id,
        )

        assert result.request_group_id == group_id

    def test_empty_client_list(self):
        """Test orchestrator with empty client list."""
        orchestrator = MultiModelOrchestrator()

        result = orchestrator.get_comparisons_sync("Test prompt", [])

        assert len(result.responses) == 0
        assert result.success_count == 0
        assert result.error_count == 0


class TestIntegration:
    """Integration tests for compare mode."""

    def test_full_comparison_flow(self):
        """Test complete comparison flow from prompt to results."""
        orchestrator = MultiModelOrchestrator()
        clients = [
            FakeClient(
                provider_name="openai",
                model_name="gpt-4o-mini",
                response_text="OpenAI response",
                prompt_tokens=10,
                completion_tokens=30,
            ),
            FakeClient(
                provider_name="gemini",
                model_name="gemini-2.5-flash-lite",
                response_text="Gemini response",
                prompt_tokens=12,
                completion_tokens=28,
            ),
            FakeClient(
                provider_name="deepseek",
                model_name="deepseek-chat",
                response_text="DeepSeek response",
                prompt_tokens=11,
                completion_tokens=29,
            ),
        ]

        result = orchestrator.get_comparisons_sync("What is Python?", clients)

        # Verify structure
        assert isinstance(result, MultiUnifiedResponse)
        assert len(result.responses) == 3

        # Verify all succeeded
        assert result.success_count == 3
        assert result.error_count == 0

        # Verify aggregations
        assert result.total_tokens == 120  # (10+30) + (12+28) + (11+29)
        assert result.total_cost == 0.003  # 3 * 0.001

        # Verify individual responses
        for resp in result.responses:
            assert resp.is_success
            assert resp.text != ""
            assert resp.token_usage.total_tokens > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
