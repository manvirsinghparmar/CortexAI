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
from server.schemas.responses import CompareResponseDTO
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
    def test_openai_defaults_to_2048_max_tokens_when_not_provided(self, mock_openai):
        """OpenAI chat path should use the repository default output cap when caller omits max_tokens."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Default cap response"), finish_reason="stop")]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-4o")
        response = client.get_completion("Test prompt")

        assert response.is_success
        assert response.text == "Default cap response"
        payload = mock_openai.return_value.chat.completions.create.call_args.kwargs
        assert payload["max_tokens"] == 2048

    @patch("openai.OpenAI")
    def test_openai_length_finish_reason_with_empty_content_is_preserved(self, mock_openai):
        """
        Reproduce provider payload where output cap is hit but assistant text is empty.
        Downstream orchestrator tests assert this shape is normalized to provider_error.
        """
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="", refusal=None), finish_reason="length")]
        mock_response.usage = Mock(prompt_tokens=1200, completion_tokens=500, total_tokens=1700)
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-5.1")
        response = client.get_completion("Test prompt")

        assert response.is_success
        assert response.text == ""
        assert response.finish_reason == "length"
        assert response.token_usage.completion_tokens == 500

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
    def test_openai_retries_with_max_completion_tokens_when_max_tokens_unsupported(self, mock_openai):
        """Test OpenAI fallback for model families that reject max_tokens."""
        mock_success = Mock()
        mock_success.choices = [Mock(message=Mock(content="Recovered"), finish_reason="stop")]
        mock_success.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        unsupported_error = Exception(
            "Invalid request: Error code: 400 - {'error': {'message': "
            "'Unsupported parameter: \\'max_tokens\\' is not supported with this model. "
            "Use \\'max_completion_tokens\\' instead.'}}"
        )
        mock_openai.return_value.chat.completions.create.side_effect = [unsupported_error, mock_success]

        client = OpenAIClient(api_key="test-key", model_name="gpt-5.1")
        response = client.get_completion("Test prompt", max_tokens=321)

        assert response.is_success
        assert response.text == "Recovered"

        calls = mock_openai.return_value.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert "max_tokens" in calls[0].kwargs
        assert calls[0].kwargs["max_tokens"] == 321
        assert "max_completion_tokens" in calls[1].kwargs
        assert calls[1].kwargs["max_completion_tokens"] == 321
        assert "max_tokens" not in calls[1].kwargs

    @patch("openai.OpenAI")
    def test_openai_codex_models_use_responses_api(self, mock_openai):
        """Codex-family models should use responses API directly."""
        mock_response = Mock()
        mock_response.output_text = "Codex response"
        mock_response.usage = Mock(input_tokens=7, output_tokens=11, total_tokens=18)
        mock_response.status = "completed"
        mock_response.finish_reason = None
        mock_openai.return_value.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-5.2-codex")
        response = client.get_completion("Test prompt", max_tokens=333)

        assert response.is_success
        assert response.text == "Codex response"
        assert response.finish_reason == "stop"
        assert response.token_usage.prompt_tokens == 7
        assert response.token_usage.completion_tokens == 11
        assert response.token_usage.total_tokens == 18
        assert response.metadata["endpoint"] == "responses"

        mock_openai.return_value.chat.completions.create.assert_not_called()
        mock_openai.return_value.responses.create.assert_called_once()
        payload = mock_openai.return_value.responses.create.call_args.kwargs
        assert payload["model"] == "gpt-5.2-codex"
        assert payload["max_output_tokens"] == 333
        assert payload["input"] == [{"role": "user", "content": "Test prompt"}]

    @patch("openai.OpenAI")
    def test_openai_retries_with_responses_when_chat_endpoint_incompatible(self, mock_openai):
        """If chat endpoint rejects a model family, retry with responses API."""
        incompatible_error = Exception(
            "Error code: 404 - {'error': {'message': "
            "'This is not a chat model and thus not supported in the v1/chat/completions "
            "endpoint. Did you mean to use v1/completions?'}}"
        )
        mock_openai.return_value.chat.completions.create.side_effect = incompatible_error

        mock_response = Mock()
        mock_response.output_text = "Recovered through responses API"
        mock_response.usage = Mock(input_tokens=4, output_tokens=6, total_tokens=10)
        mock_response.status = "completed"
        mock_response.finish_reason = None
        mock_openai.return_value.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-4o")
        response = client.get_completion("Test prompt", model="future-non-chat-model", max_tokens=123)

        assert response.is_success
        assert response.text == "Recovered through responses API"
        assert response.finish_reason == "stop"
        assert response.metadata["endpoint"] == "responses"
        assert mock_openai.return_value.chat.completions.create.call_count == 1
        mock_openai.return_value.responses.create.assert_called_once()
        payload = mock_openai.return_value.responses.create.call_args.kwargs
        assert payload["model"] == "future-non-chat-model"
        assert payload["max_output_tokens"] == 123

    @patch("openai.OpenAI")
    def test_openai_retries_responses_without_temperature_when_unsupported(self, mock_openai):
        """Responses path should retry without temperature for incompatible models."""
        unsupported_temp = Exception(
            "Error code: 400 - {'error': {'message': "
            "\"Unsupported parameter: 'temperature' is not supported with this model.\"}}"
        )
        success = Mock()
        success.output_text = "Recovered without temperature"
        success.usage = Mock(input_tokens=3, output_tokens=5, total_tokens=8)
        success.status = "completed"
        success.finish_reason = None
        mock_openai.return_value.responses.create.side_effect = [unsupported_temp, success]

        client = OpenAIClient(api_key="test-key", model_name="gpt-5.2-codex")
        response = client.get_completion("Test prompt", temperature=0.2, max_tokens=77)

        assert response.is_success
        assert response.text == "Recovered without temperature"
        assert response.finish_reason == "stop"
        assert response.metadata["endpoint"] == "responses"
        assert response.metadata["adaptive_retry"]["dropped_param"] == "temperature"
        assert response.metadata["adaptive_retry"]["retry_reason"] == "unsupported_parameter"
        assert mock_openai.return_value.responses.create.call_count == 2
        first_payload = mock_openai.return_value.responses.create.call_args_list[0].kwargs
        second_payload = mock_openai.return_value.responses.create.call_args_list[1].kwargs
        assert first_payload["temperature"] == 0.2
        assert "temperature" not in second_payload
        assert second_payload["max_output_tokens"] == 77

    @patch("openai.OpenAI")
    def test_openai_attachments_use_responses_input_blocks(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Image analyzed"
        mock_response.usage = Mock(input_tokens=12, output_tokens=8, total_tokens=20)
        mock_response.status = "completed"
        mock_response.finish_reason = None
        mock_openai.return_value.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-4o")
        response = client.get_completion(
            "What is in this image?",
            attachments=[
                {
                    "file_id": "f1",
                    "filename": "cat.png",
                    "mime_type": "image/png",
                    "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
                }
            ],
        )

        assert response.is_success
        payload = mock_openai.return_value.responses.create.call_args.kwargs
        assert payload["model"] == "gpt-4o"
        assert isinstance(payload["input"], list) and payload["input"]
        user_message = payload["input"][-1]
        assert user_message["role"] == "user"
        content_types = [item["type"] for item in user_message["content"]]
        assert "input_text" in content_types
        assert "input_image" in content_types

    @patch("openai.OpenAI")
    def test_openai_responses_attachment_history_uses_assistant_output_text(self, mock_openai):
        mock_response = Mock()
        mock_response.output_text = "Image analyzed with history"
        mock_response.usage = Mock(input_tokens=18, output_tokens=9, total_tokens=27)
        mock_response.status = "completed"
        mock_response.finish_reason = None
        mock_openai.return_value.responses.create.return_value = mock_response

        client = OpenAIClient(api_key="test-key", model_name="gpt-4o")
        response = client.get_completion(
            messages=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
                {"role": "user", "content": "What changed in this image?"},
            ],
            attachments=[
                {
                    "file_id": "f1",
                    "filename": "diagram.png",
                    "mime_type": "image/png",
                    "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
                }
            ],
        )

        assert response.is_success
        payload = mock_openai.return_value.responses.create.call_args.kwargs
        assistant_message = next(item for item in payload["input"] if item["role"] == "assistant")
        assert assistant_message["content"] == [{"type": "output_text", "text": "Earlier answer"}]

        last_user_message = payload["input"][-1]
        assert last_user_message["role"] == "user"
        content_types = [item["type"] for item in last_user_message["content"]]
        assert "input_text" in content_types
        assert "input_image" in content_types

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
    def test_deepseek_retries_without_unsupported_parameter(self, mock_openai):
        """DeepSeek should retry once when provider rejects an optional parameter."""
        unsupported_temp = Exception(
            "Error code: 400 - {'error': {'message': "
            "\"Unsupported parameter: 'temperature' is not supported with this model.\"}}"
        )
        mock_success = Mock()
        mock_success.choices = [Mock(message=Mock(content="Recovered"), finish_reason="stop")]
        mock_success.usage = Mock(prompt_tokens=8, completion_tokens=13, total_tokens=21)
        mock_openai.return_value.chat.completions.create.side_effect = [unsupported_temp, mock_success]

        client = DeepSeekClient(api_key="test-key", model_name="deepseek-chat")
        response = client.get_completion("Test prompt", temperature=0.5, max_tokens=200)

        assert response.is_success
        assert response.text == "Recovered"
        assert response.metadata["endpoint"] == "chat.completions"
        assert response.metadata["adaptive_retry"]["dropped_param"] == "temperature"
        assert mock_openai.return_value.chat.completions.create.call_count == 2
        first_payload = mock_openai.return_value.chat.completions.create.call_args_list[0].kwargs
        second_payload = mock_openai.return_value.chat.completions.create.call_args_list[1].kwargs
        assert first_payload["temperature"] == 0.5
        assert "temperature" not in second_payload

    @patch("openai.OpenAI")
    def test_deepseek_rejects_binary_attachments(self, mock_openai):
        client = DeepSeekClient(api_key="test-key", model_name="deepseek-chat")
        response = client.get_completion(
            "describe this",
            attachments=[
                {
                    "file_id": "f1",
                    "filename": "cat.png",
                    "mime_type": "image/png",
                    "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
                }
            ],
        )

        assert response.is_error
        assert response.error.code == "bad_request"
        mock_openai.return_value.chat.completions.create.assert_not_called()

    @patch("openai.OpenAI")
    def test_deepseek_accepts_text_materialized_attachments(self, mock_openai):
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Processed text attachment"), finish_reason="stop")]
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = DeepSeekClient(api_key="test-key", model_name="deepseek-chat")
        response = client.get_completion(
            "summarize this",
            attachments=[
                {
                    "file_id": "f1",
                    "filename": "report.txt",
                    "mime_type": "text/plain",
                    "extracted_text": "Quarterly revenue grew by 12%.",
                }
            ],
        )

        assert response.is_success
        payload = mock_openai.return_value.chat.completions.create.call_args.kwargs
        assert payload["model"] == "deepseek-chat"
        assert payload["messages"][-1]["role"] == "user"
        assert "Attachment context:" in payload["messages"][-1]["content"]
        assert "Quarterly revenue grew by 12%." in payload["messages"][-1]["content"]

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

    @patch("openai.OpenAI")
    def test_grok_retries_without_unsupported_parameter(self, mock_openai):
        """Grok should retry once when provider rejects an optional parameter."""
        unsupported_temp = Exception(
            "Error code: 400 - {'error': {'message': "
            "\"Unsupported parameter: 'temperature' is not supported with this model.\"}}"
        )
        mock_success = Mock()
        mock_success.choices = [Mock(message=Mock(content="Recovered"), finish_reason="stop")]
        mock_success.usage = Mock(prompt_tokens=6, completion_tokens=9, total_tokens=15)
        mock_openai.return_value.chat.completions.create.side_effect = [unsupported_temp, mock_success]

        client = GrokClient(api_key="test-key", model_name="grok-4-latest")
        response = client.get_completion("Test prompt", temperature=0.3, max_tokens=120)

        assert response.is_success
        assert response.text == "Recovered"
        assert response.metadata["endpoint"] == "chat.completions"
        assert response.metadata["adaptive_retry"]["dropped_param"] == "temperature"
        assert mock_openai.return_value.chat.completions.create.call_count == 2
        first_payload = mock_openai.return_value.chat.completions.create.call_args_list[0].kwargs
        second_payload = mock_openai.return_value.chat.completions.create.call_args_list[1].kwargs
        assert first_payload["temperature"] == 0.3
        assert "temperature" not in second_payload

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

    @patch("google.genai.Client")
    def test_gemini_retries_without_unsupported_parameter(self, mock_genai):
        """Gemini should retry once when config includes unsupported optional parameter."""
        unsupported_temp = Exception(
            "400 Invalid argument: Unsupported parameter: 'temperature' is not supported with this model."
        )
        mock_response = Mock()
        mock_response.text = "Recovered"
        mock_response.usage_metadata = Mock(
            prompt_token_count=4, candidates_token_count=7, total_token_count=11
        )
        mock_response.candidates = [Mock(finish_reason="STOP")]
        mock_genai.return_value.models.generate_content.side_effect = [unsupported_temp, mock_response]

        client = GeminiClient(api_key="test-key", model_name="gemini-1.5-flash")
        response = client.get_completion("Test prompt", temperature=0.4, max_output_tokens=222)

        assert response.is_success
        assert response.text == "Recovered"
        assert response.metadata["endpoint"] == "models.generate_content"
        assert response.metadata["adaptive_retry"]["dropped_param"] == "temperature"
        assert mock_genai.return_value.models.generate_content.call_count == 2
        first_config = mock_genai.return_value.models.generate_content.call_args_list[0].kwargs["config"]
        second_config = mock_genai.return_value.models.generate_content.call_args_list[1].kwargs["config"]
        assert first_config["temperature"] == 0.4
        assert "temperature" not in second_config

    @patch("google.genai.Client")
    def test_gemini_accepts_max_tokens_alias_from_routes(self, mock_genai):
        """Route layer sends max_tokens; Gemini client should map it to max_output_tokens."""
        mock_response = Mock()
        mock_response.text = "Alias works"
        mock_response.usage_metadata = Mock(
            prompt_token_count=4, candidates_token_count=7, total_token_count=11
        )
        mock_response.candidates = [Mock(finish_reason="STOP")]
        mock_genai.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key", model_name="gemini-1.5-flash")
        response = client.get_completion("Test prompt", max_tokens=333)

        assert response.is_success
        assert response.text == "Alias works"
        config = mock_genai.return_value.models.generate_content.call_args.kwargs["config"]
        assert config["max_output_tokens"] == 333

    @patch("google.genai.Client")
    def test_gemini_defaults_to_2048_output_tokens_when_unset(self, mock_genai):
        mock_response = Mock()
        mock_response.text = "Default output limit"
        mock_response.usage_metadata = Mock(
            prompt_token_count=4, candidates_token_count=7, total_token_count=11
        )
        mock_response.candidates = [Mock(finish_reason="STOP")]
        mock_genai.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key", model_name="gemini-1.5-flash")
        response = client.get_completion("Test prompt")

        assert response.is_success
        config = mock_genai.return_value.models.generate_content.call_args.kwargs["config"]
        assert config["max_output_tokens"] == 2048

    @patch("google.genai.Client")
    def test_gemini_includes_inline_attachment_parts(self, mock_genai):
        mock_response = Mock()
        mock_response.text = "Image analyzed"
        mock_response.usage_metadata = Mock(
            prompt_token_count=4, candidates_token_count=7, total_token_count=11
        )
        mock_response.candidates = [Mock(finish_reason="STOP")]
        mock_genai.return_value.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key", model_name="gemini-2.5-flash")
        response = client.get_completion(
            "Describe this image",
            attachments=[
                {
                    "file_id": "f1",
                    "filename": "cat.png",
                    "mime_type": "image/png",
                    "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
                }
            ],
        )

        assert response.is_success
        contents = mock_genai.return_value.models.generate_content.call_args.kwargs["contents"]
        user_parts = contents[-1]["parts"]
        assert any("inline_data" in part for part in user_parts)


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


class TestCompareDtoCompatibility:
    def test_compare_dto_supports_timestamp_based_multi_response_shape(self):
        class TimestampShapeMur:
            def __init__(self):
                self.request_group_id = "grp_ts_1"
                self.responses = [
                    UnifiedResponse(
                        request_id="cmp_ts_1",
                        text="hello",
                        provider="openai",
                        model="gpt-4o-mini",
                        latency_ms=10,
                        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
                        estimated_cost=0.00001,
                        finish_reason="stop",
                        error=None,
                        metadata={},
                    )
                ]
                self.success_count = 1
                self.error_count = 0
                self.total_tokens = 3
                self.total_cost = 0.00001
                self.timestamp = "2026-02-18T12:00:00Z"

        dto = CompareResponseDTO.from_multi_unified_response(TimestampShapeMur())
        assert dto.request_group_id == "grp_ts_1"
        assert dto.timestamp == "2026-02-18T12:00:00Z"
        assert len(dto.responses) == 1

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
