"""
Tests for UnifiedResponse Contract

These tests validate that all provider clients adhere to the "locked" UnifiedResponse contract.
All clients must return UnifiedResponse, handle errors gracefully, and never expose provider-specific fields.
"""

from unittest.mock import Mock, patch

import pytest

from api.deepseek_client import DeepSeekClient
from api.google_gemini_client import GeminiClient
from api.grok_client import GrokClient
from api.openai_client import OpenAIClient
from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse


class TestUnifiedResponseContract:
    """Test that all providers return UnifiedResponse with correct structure."""

    def test_unified_response_creation(self):
        """Test that UnifiedResponse can be created with all required fields."""
        response = UnifiedResponse(
            request_id="test-123",
            text="Test response",
            provider="test",
            model="test-model",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
        )

        assert response.request_id == "test-123"
        assert response.text == "Test response"
        assert response.provider == "test"
        assert response.model == "test-model"
        assert response.latency_ms == 100
        assert response.token_usage.total_tokens == 30
        assert response.estimated_cost == 0.001
        assert response.finish_reason == "stop"
        assert response.error is None
        assert response.is_success
        assert not response.is_error

    def test_unified_response_with_error(self):
        """Test that UnifiedResponse can represent errors correctly."""
        error = NormalizedError(
            code="timeout", message="Request timed out", provider="test", retryable=True
        )

        response = UnifiedResponse(
            request_id="test-123",
            text="",
            provider="test",
            model="test-model",
            latency_ms=5000,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=error,
        )

        assert response.is_error
        assert not response.is_success
        assert response.error.code == "timeout"
        assert response.error.retryable
        assert response.text == ""
        assert response.token_usage.total_tokens == 0

    def test_token_usage_auto_total(self):
        """Test that TokenUsage auto-calculates total if not provided."""
        usage = TokenUsage(prompt_tokens=50, completion_tokens=100)
        assert usage.total_tokens == 150

    def test_normalized_error_validates_code(self):
        """Test that NormalizedError validates error codes."""
        # Valid code
        error = NormalizedError(code="auth", message="Auth failed", provider="test")
        assert error.code == "auth"

        # Invalid code should be normalized to "unknown"
        error = NormalizedError(code="invalid_code", message="Test", provider="test")
        assert error.code == "unknown"

    def test_finish_reason_validation(self):
        """Test that UnifiedResponse validates finish_reason."""
        # Valid finish reason
        response = UnifiedResponse(
            request_id="test",
            text="test",
            provider="test",
            model="test",
            latency_ms=100,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="stop",
        )
        assert response.finish_reason == "stop"

        # Invalid finish reason should become None
        response = UnifiedResponse(
            request_id="test",
            text="test",
            provider="test",
            model="test",
            latency_ms=100,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="invalid_reason",
        )
        assert response.finish_reason is None


class TestProviderContractCompliance:
    """Test that all provider clients return UnifiedResponse."""

    @patch("openai.OpenAI")
    def test_openai_returns_unified_response(self, mock_openai):
        """Test that OpenAI client returns UnifiedResponse."""
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"), finish_reason="stop")]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-3.5-turbo")
        response = client.get_completion("Test prompt")

        # Validate UnifiedResponse
        assert isinstance(response, UnifiedResponse)
        assert response.provider == "openai"
        assert response.text == "Test response"
        assert isinstance(response.token_usage, TokenUsage)
        assert response.token_usage.total_tokens == 30
        assert response.finish_reason == "stop"
        assert response.error is None
        assert response.is_success

    @patch("openai.OpenAI")
    def test_openai_handles_errors_gracefully(self, mock_openai):
        """Test that OpenAI client returns UnifiedResponse with error on exception."""
        # Mock exception
        mock_openai.return_value.chat.completions.create.side_effect = Exception("API Error")

        client = OpenAIClient(api_key="test-key")
        response = client.get_completion("Test prompt")

        # Should return UnifiedResponse with error, NOT raise exception
        assert isinstance(response, UnifiedResponse)
        assert response.is_error
        assert response.error is not None
        assert response.error.code in [
            "timeout",
            "auth",
            "rate_limit",
            "bad_request",
            "provider_error",
            "unknown",
        ]
        assert response.finish_reason == "error"
        assert response.text == ""

    @patch("openai.OpenAI")
    def test_deepseek_returns_unified_response(self, mock_openai):
        """Test that DeepSeek client returns UnifiedResponse."""
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"), finish_reason="stop")]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = DeepSeekClient(api_key="test-key", model_name="deepseek-chat")
        response = client.get_completion("Test prompt")

        assert isinstance(response, UnifiedResponse)
        assert response.provider == "deepseek"
        assert response.is_success

    @patch("openai.OpenAI")
    def test_grok_returns_unified_response(self, mock_openai):
        """Test that Grok client returns UnifiedResponse."""
        # Mock successful response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"), finish_reason="stop")]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = GrokClient(api_key="test-key", model_name="grok-4-latest")
        response = client.get_completion("Test prompt")

        assert isinstance(response, UnifiedResponse)
        assert response.provider == "grok"
        assert response.is_success

    @patch("google.genai.Client")
    def test_gemini_returns_unified_response(self, mock_genai):
        """Test that Gemini client returns UnifiedResponse."""
        # Mock successful response
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata = Mock(
            prompt_token_count=10, candidates_token_count=20, total_token_count=30
        )
        mock_response.candidates = [Mock(finish_reason="STOP")]
        mock_genai.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key", model_name="gemini-1.5-flash")
        response = client.get_completion("Test prompt")

        assert isinstance(response, UnifiedResponse)
        assert response.provider == "gemini"
        assert response.text == "Test response"
        assert response.is_success


class TestErrorHandlingContract:
    """Test that errors are handled according to contract."""

    @patch("openai.OpenAI")
    def test_timeout_error_normalized(self, mock_openai):
        """Test that timeout errors are properly normalized."""
        mock_openai.return_value.chat.completions.create.side_effect = Exception(
            "Request timed out"
        )

        client = OpenAIClient(api_key="test-key")
        response = client.get_completion("Test")

        assert response.is_error
        assert response.error.code == "timeout"
        assert response.error.retryable is True

    @patch("openai.OpenAI")
    def test_auth_error_normalized(self, mock_openai):
        """Test that auth errors are properly normalized."""
        mock_openai.return_value.chat.completions.create.side_effect = Exception("401 Unauthorized")

        client = OpenAIClient(api_key="test-key")
        response = client.get_completion("Test")

        assert response.is_error
        assert response.error.code == "auth"
        assert response.error.retryable is False

    @patch("openai.OpenAI")
    def test_rate_limit_error_normalized(self, mock_openai):
        """Test that rate limit errors are properly normalized."""
        mock_openai.return_value.chat.completions.create.side_effect = Exception(
            "429 Too Many Requests"
        )

        client = OpenAIClient(api_key="test-key")
        response = client.get_completion("Test")

        assert response.is_error
        assert response.error.code == "rate_limit"
        assert response.error.retryable is True


class TestTokenTrackerIntegration:
    """Test that TokenTracker works with UnifiedResponse."""

    def test_token_tracker_accepts_unified_response(self):
        """Test that TokenTracker can accept UnifiedResponse directly."""
        from utils.token_tracker import TokenTracker

        response = UnifiedResponse(
            request_id="test",
            text="test",
            provider="test",
            model="test",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
        )

        tracker = TokenTracker()
        tracker.update(response)

        assert tracker.total_prompt_tokens == 50
        assert tracker.total_completion_tokens == 100
        assert tracker.total_tokens == 150
        assert tracker.requests == 1

    def test_token_tracker_backward_compatibility(self):
        """Test that TokenTracker still accepts dicts for backward compatibility."""
        from utils.token_tracker import TokenTracker

        usage_dict = {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}

        tracker = TokenTracker()
        tracker.update(usage_dict)

        assert tracker.total_prompt_tokens == 50
        assert tracker.total_completion_tokens == 100
        assert tracker.total_tokens == 150
        assert tracker.requests == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
