"""
Tests for Prompt Optimizer Module

Comprehensive test suite covering input validation, optimization flow,
output schema validation, error handling, and self-correction mechanisms.
"""

import json
from unittest.mock import Mock

import pytest

from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
from utils.prompt_optimizer import PromptOptimizer


class TestInputValidation:
    """Test input validation logic."""

    def test_valid_input_with_prompt_only(self):
        """Test valid input with only prompt field."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = {"prompt": "write code for sorting"}

        error = optimizer._validate_input(input_data)
        assert error is None

    def test_valid_input_with_settings(self):
        """Test valid input with prompt and settings."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = {
            "prompt": "write code for sorting",
            "settings": {"focus": "clarity", "language": "python"},
        }

        error = optimizer._validate_input(input_data)
        assert error is None

    def test_missing_prompt_field(self):
        """Test error when prompt field is missing."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = {"settings": {"focus": "clarity"}}

        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "prompt" in error["error"]["message"].lower()

    def test_empty_prompt(self):
        """Test error when prompt is empty."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = {"prompt": "   "}

        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "empty" in error["error"]["message"].lower()

    def test_non_string_prompt(self):
        """Test error when prompt is not a string."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = {"prompt": 123}

        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "string" in error["error"]["message"].lower()

    def test_non_dict_input(self):
        """Test error when input is not a dictionary."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = "not a dict"

        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "dictionary" in error["error"]["message"].lower()

    def test_invalid_settings_type(self):
        """Test error when settings is not a dictionary."""
        optimizer = PromptOptimizer(client=Mock())
        input_data = {"prompt": "test prompt", "settings": "not a dict"}

        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "settings" in error["error"]["message"].lower()


class TestOutputValidation:
    """Test output schema validation."""

    def test_valid_output_minimal(self):
        """Test valid output with only required field."""
        optimizer = PromptOptimizer(client=Mock())
        output = {"optimized_prompt": "Improved prompt"}

        assert optimizer._is_valid_output(output) is True

    def test_valid_output_complete(self):
        """Test valid output with all optional fields."""
        optimizer = PromptOptimizer(client=Mock())
        output = {
            "optimized_prompt": "Improved prompt",
            "steps": ["Step 1", "Step 2"],
            "explanations": ["Explanation 1", "Explanation 2"],
            "metrics": {"clarity": 8.5, "specificity": 9.0},
        }

        assert optimizer._is_valid_output(output) is True

    def test_missing_required_field(self):
        """Test invalid output missing optimized_prompt."""
        optimizer = PromptOptimizer(client=Mock())
        output = {"steps": ["Step 1"]}

        assert optimizer._is_valid_output(output) is False

    def test_invalid_steps_type(self):
        """Test invalid output with wrong steps type."""
        optimizer = PromptOptimizer(client=Mock())
        output = {"optimized_prompt": "Test", "steps": "not a list"}

        assert optimizer._is_valid_output(output) is False

    def test_invalid_explanations_items(self):
        """Test invalid output with non-string explanations."""
        optimizer = PromptOptimizer(client=Mock())
        output = {"optimized_prompt": "Test", "explanations": [123, 456]}

        assert optimizer._is_valid_output(output) is False

    def test_invalid_metrics_type(self):
        """Test invalid output with wrong metrics type."""
        optimizer = PromptOptimizer(client=Mock())
        output = {"optimized_prompt": "Test", "metrics": "not a dict"}

        assert optimizer._is_valid_output(output) is False


class TestResponseParsing:
    """Test OpenAI response parsing."""

    def test_parse_plain_json(self):
        """Test parsing plain JSON response."""
        optimizer = PromptOptimizer(client=Mock())
        response_text = json.dumps({"optimized_prompt": "Improved prompt", "steps": ["Step 1"]})

        result = optimizer._parse_ai_response(response_text, "original")
        assert result["optimized_prompt"] == "Improved prompt"
        assert result["steps"] == ["Step 1"]

    def test_parse_markdown_code_block(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        optimizer = PromptOptimizer(client=Mock())
        response_text = """```json
{
  "optimized_prompt": "Improved prompt",
  "steps": ["Step 1"]
}
```"""

        result = optimizer._parse_ai_response(response_text, "original")
        assert result["optimized_prompt"] == "Improved prompt"
        assert result["steps"] == ["Step 1"]

    def test_parse_invalid_json(self):
        """Test error handling for invalid JSON."""
        optimizer = PromptOptimizer(client=Mock())
        response_text = "This is not JSON"

        with pytest.raises(Exception) as exc_info:
            optimizer._parse_ai_response(response_text, "original")

        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_missing_required_field(self):
        """Test error when optimized_prompt is missing."""
        optimizer = PromptOptimizer(client=Mock())
        response_text = json.dumps({"steps": ["Step 1"]})

        with pytest.raises(Exception) as exc_info:
            optimizer._parse_ai_response(response_text, "original")

        assert "optimized_prompt" in str(exc_info.value)

    def test_parse_tolerates_extra_trailing_brace(self):
        """Some small optimizer models occasionally emit one extra closing brace."""
        optimizer = PromptOptimizer(client=Mock())
        response_text = json.dumps({"optimized_prompt": "Improved prompt"}) + "}"

        result = optimizer._parse_ai_response(response_text, "original")

        assert result["optimized_prompt"] == "Improved prompt"

    def test_parse_rejects_answer_instead_of_rewrite_for_short_prompt(self):
        """Short prompts should not be replaced by a full factual answer."""
        optimizer = PromptOptimizer(client=Mock())
        response_text = json.dumps(
            {
                "optimized_prompt": (
                    "The operation that resulted in the death of Osama bin Laden, codenamed "
                    "\"Operation Neptune Spear,\" took place on May 2, 2011.\n\n"
                    "**Location:** The operation was conducted at a fortified compound in "
                    "Bilal Town, Abbottabad, Pakistan.\n\n"
                    "**Operation Details:** The SEALs entered the compound and completed "
                    "the raid in approximately 40 minutes."
                )
            }
        )

        with pytest.raises(Exception) as exc_info:
            optimizer._parse_ai_response(response_text, "how osama was killed")

        assert "appears to answer" in str(exc_info.value)

    def test_parse_rejects_introduced_placeholder(self):
        optimizer = PromptOptimizer(client=Mock())
        response_text = json.dumps(
            {
                "optimized_prompt": (
                    "Provide a detailed range of estimates for [specific topic or item], "
                    "and explain why estimates vary."
                )
            }
        )

        with pytest.raises(Exception) as exc_info:
            optimizer._parse_ai_response(response_text, "give me the detailed range")

        assert "unresolved placeholder" in str(exc_info.value)

    def test_parse_allows_user_provided_placeholder_template(self):
        optimizer = PromptOptimizer(client=Mock())
        original = "Draft an email to [customer_name] about [issue]."
        response_text = json.dumps(
            {
                "optimized_prompt": (
                    "Draft a concise, professional email to [customer_name] about [issue], "
                    "including the impact, next step, and a polite closing."
                )
            }
        )

        result = optimizer._parse_ai_response(response_text, original)

        assert result["optimized_prompt"].startswith("Draft a concise")


class TestPromptQualityClassification:
    """Test local prompt specificity classification used for retry policy."""

    def test_vague_prompt_classifies_as_weak(self):
        optimizer = PromptOptimizer(client=Mock())

        assert optimizer.classify_prompt_quality("write something about ai") == "weak"

    def test_clear_prompt_classifies_as_strong(self):
        optimizer = PromptOptimizer(client=Mock())
        prompt = (
            "Create a concise implementation plan for adding request-level observability "
            "to /v1/optimize, including timeout, retry, and fallback logging. Do not log raw prompt text."
        )

        assert optimizer.classify_prompt_quality(prompt) == "strong"

    def test_follow_up_prompt_classifies_as_reference_dependent(self):
        optimizer = PromptOptimizer(client=Mock())

        assert optimizer.classify_prompt_quality("what about the second one?") == "reference_dependent"

    def test_possessive_follow_up_classifies_as_reference_dependent(self):
        optimizer = PromptOptimizer(client=Mock())

        assert (
            optimizer.classify_prompt_quality("How many of their cadres were actually killed?")
            == "reference_dependent"
        )

    def test_prior_offer_follow_up_classifies_as_reference_dependent(self):
        optimizer = PromptOptimizer(client=Mock())

        assert (
            optimizer.classify_prompt_quality("Give me the detailed range of estimates.")
            == "reference_dependent"
        )

    def test_compact_context_preserves_assistant_messages_for_references(self):
        optimizer = PromptOptimizer(client=Mock())
        context = {
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Compare OpenAI, Gemini, and Claude for prompt optimization.",
                },
                {
                    "role": "assistant",
                    "content": "1. OpenAI: strong quality. 2. Gemini: low latency. 3. Claude: careful writing.",
                },
            ]
        }

        compact = optimizer._compact_context(context)

        assert "- assistant:" in compact
        assert "Gemini" in compact

    def test_compact_context_for_fifth_follow_up_uses_expanded_reference_window(self):
        optimizer = PromptOptimizer(client=Mock())
        context = {
            "conversation_history": [
                {"role": "user", "content": "root marker: compare OpenAI, Gemini, and Claude"},
                {"role": "assistant", "content": "root answer marker: second one is Gemini"},
                {"role": "user", "content": "follow-up one marker"},
                {"role": "assistant", "content": "follow-up one answer marker"},
                {"role": "user", "content": "follow-up two marker"},
                {"role": "assistant", "content": "follow-up two answer marker"},
                {"role": "user", "content": "follow-up three marker"},
                {"role": "assistant", "content": "follow-up three answer marker"},
                {"role": "user", "content": "follow-up four marker"},
                {"role": "assistant", "content": "follow-up four answer marker"},
            ]
        }

        compact = optimizer._compact_context(context, prompt_quality="reference_dependent")

        assert "root marker" in compact
        assert "root answer marker" in compact
        assert "follow-up one marker" in compact
        assert "follow-up two marker" in compact
        assert "follow-up three marker" in compact
        assert "follow-up three answer marker" in compact
        assert "follow-up four marker" in compact
        assert "follow-up four answer marker" in compact
        assert compact.count("- user:") == 5
        assert compact.count("- assistant:") == 5

    def test_compact_context_for_non_reference_still_uses_last_four_mixed_messages(self):
        optimizer = PromptOptimizer(client=Mock())
        context = {
            "conversation_history": [
                {"role": "user", "content": "root marker: compare OpenAI, Gemini, and Claude"},
                {"role": "assistant", "content": "root answer marker: second one is Gemini"},
                {"role": "user", "content": "follow-up one marker"},
                {"role": "assistant", "content": "follow-up one answer marker"},
                {"role": "user", "content": "follow-up two marker"},
                {"role": "assistant", "content": "follow-up two answer marker"},
                {"role": "user", "content": "follow-up three marker"},
                {"role": "assistant", "content": "follow-up three answer marker"},
                {"role": "user", "content": "follow-up four marker"},
                {"role": "assistant", "content": "follow-up four answer marker"},
            ]
        }

        compact = optimizer._compact_context(context)

        assert "follow-up three marker" in compact
        assert "follow-up three answer marker" in compact
        assert "follow-up four marker" in compact
        assert "follow-up four answer marker" in compact
        assert "root marker" not in compact
        assert "root answer marker" not in compact
        assert "follow-up one marker" not in compact
        assert "follow-up two marker" not in compact
        assert compact.count("- user:") == 2
        assert compact.count("- assistant:") == 2

    def test_compact_context_trims_each_message_before_building_hint(self):
        optimizer = PromptOptimizer(client=Mock())
        context = {
            "conversation_history": [
                {"role": "user", "content": "short setup"},
                {"role": "assistant", "content": "short answer"},
                {"role": "user", "content": "x" * 700},
                {"role": "assistant", "content": "y" * 700},
            ]
        }

        compact = optimizer._compact_context(context)

        assert "x" * 500 in compact
        assert "x" * 501 not in compact
        assert "y" * 500 in compact
        assert "y" * 501 not in compact


class TestOptimizationFlow:
    """Test the complete optimization flow with mocked OpenAI."""

    def test_successful_optimization(self):
        """Test successful optimization flow."""
        # Setup mock
        mock_client = Mock()

        mock_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps(
                {
                    "optimized_prompt": "Write a Python function to sort a list of integers in ascending order",
                    "steps": [
                        "Added specificity about programming language",
                        "Clarified the sorting order",
                        "Made the data type explicit",
                    ],
                    "explanations": [
                        "Specifying Python makes the request unambiguous",
                        "Ascending order is more common but should be explicit",
                    ],
                    "metrics": {"clarity_score": 9.0, "specificity_score": 8.5},
                }
            ),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.return_value = mock_response

        # Test
        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt({"prompt": "write code for sorting"})

        # Assertions
        assert "optimized_prompt" in result
        assert "Python" in result["optimized_prompt"]
        assert "steps" in result
        assert len(result["steps"]) == 3
        assert "explanations" in result
        assert "metrics" in result
        assert "error" not in result

    def test_optimization_with_settings(self):
        """Test optimization with additional settings."""
        # Setup mock
        mock_client = Mock()

        mock_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps(
                {
                    "optimized_prompt": "Create a clear, beginner-friendly Python tutorial on sorting",
                    "steps": ["Added clarity focus", "Made it beginner-friendly"],
                }
            ),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.return_value = mock_response

        # Test
        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt(
            {
                "prompt": "write code for sorting",
                "settings": {"focus": "clarity", "audience": "beginners"},
            }
        )

        # Assertions
        assert "optimized_prompt" in result
        assert "error" not in result

    def test_optimization_with_context_hint(self):
        """Test optimization prompt includes compact context for follow-up prompts."""
        mock_client = Mock()
        mock_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps(
                {
                    "optimized_prompt": "Explain why humans mine asteroids.",
                    "steps": ["Resolved follow-up reference from context"],
                }
            ),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.return_value = mock_response

        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt(
            {
                "prompt": "I was talking about mining the asteroids",
                "context_hint": "Recent topic: asteroid mining.",
                "max_retries": 1,
            }
        )

        assert result["optimized_prompt"] == "Explain why humans mine asteroids."
        sent_messages = mock_client.get_completion.call_args.kwargs["messages"]
        user_message = sent_messages[1]["content"]
        assert "Recent topic: asteroid mining." in user_message
        assert "Latest user prompt to rewrite" in user_message
        assert mock_client.get_completion.call_count == 1

    def test_placeholder_output_is_rejected_and_returns_original(self):
        mock_client = Mock()
        original = "give me the detailed range"
        mock_client.get_completion.return_value = UnifiedResponse(
            request_id="test-123",
            text=json.dumps(
                {
                    "optimized_prompt": (
                        "Provide a detailed range of estimates for [specific topic or item], "
                        "and explain why estimates vary."
                    )
                }
            ),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt({"prompt": original, "max_retries": 1})

        assert result["optimized_prompt"] == original
        assert result["error"]["code"] == "optimization_rejected"
        assert result["retry_reasons"] == ["optimizer_output_rejected"]

    def test_weak_prompt_retries_once_when_optimizer_returns_original(self):
        mock_client = Mock()
        original = "write something about ai"
        unchanged_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps({"optimized_prompt": original}),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        improved_response = UnifiedResponse(
            request_id="test-456",
            text=json.dumps(
                {
                    "optimized_prompt": (
                        "Write a concise overview of artificial intelligence for a general audience, "
                        "covering what it is, common use cases, benefits, risks, and practical examples."
                    )
                }
            ),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=80, total_tokens=130),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.side_effect = [unchanged_response, improved_response]

        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt({"prompt": original, "max_retries": 2})

        assert result["optimized_prompt"] != original
        assert result["prompt_quality"] == "weak"
        assert result["unchanged_retry_used"] is True
        assert result["retry_reasons"] == ["unchanged_weak_prompt"]
        assert mock_client.get_completion.call_count == 2
        assert mock_client.get_completion.call_args.kwargs["response_format"] == {
            "type": "json_object"
        }

    def test_strong_prompt_does_not_retry_when_optimizer_returns_original(self):
        mock_client = Mock()
        original = (
            "Create a concise implementation plan for adding request-level observability "
            "to /v1/optimize, including timeout, retry, and fallback logging. Do not log raw prompt text."
        )
        unchanged_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps({"optimized_prompt": original}),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.return_value = unchanged_response

        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt({"prompt": original, "max_retries": 2})

        assert result["optimized_prompt"] == original
        assert result["prompt_quality"] == "strong"
        assert result["unchanged_retry_used"] is False
        assert mock_client.get_completion.call_count == 1

    def test_weak_prompt_returns_original_when_unchanged_after_retry(self):
        mock_client = Mock()
        original = "fix this code"
        unchanged_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps({"optimized_prompt": original}),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=50, total_tokens=100),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.side_effect = [unchanged_response, unchanged_response]

        optimizer = PromptOptimizer(provider="openai", client=mock_client)
        result = optimizer.optimize_prompt({"prompt": original, "max_retries": 2})

        assert result["optimized_prompt"] == original
        assert result["fallback_reason"] == "unchanged_after_retry"
        assert result["unchanged_retry_used"] is True
        assert mock_client.get_completion.call_count == 2

    def test_request_max_retries_overrides_optimizer_default(self):
        """Test explicit route calls can use fewer retries than the optimizer default."""
        mock_client = Mock()
        invalid_response = UnifiedResponse(
            request_id="test-123",
            text="not json",
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.return_value = invalid_response

        optimizer = PromptOptimizer(provider="openai", max_retries=3, client=mock_client)
        result = optimizer.optimize_prompt({"prompt": "write code for sorting", "max_retries": 1})

        assert result["optimized_prompt"] == "write code for sorting"
        assert "error" in result
        assert mock_client.get_completion.call_count == 1

    def test_api_error_handling(self):
        """Test handling of OpenAI API errors."""
        # Setup mock
        mock_client = Mock()

        mock_error_response = UnifiedResponse(
            request_id="test-123",
            text="",
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=100,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=NormalizedError(
                code="rate_limit", message="Rate limit exceeded", provider="openai", retryable=True
            ),
            metadata={},
        )
        mock_client.get_completion.return_value = mock_error_response

        # Test
        optimizer = PromptOptimizer(provider="openai", max_retries=2, client=mock_client)
        result = optimizer.optimize_prompt({"prompt": "write code for sorting"})

        # Assertions
        assert "error" in result
        assert "optimized_prompt" in result  # Should return original as fallback
        assert result["optimized_prompt"] == "write code for sorting"

    def test_answer_like_optimizer_output_falls_back_to_original(self):
        """A valid JSON wrapper is still rejected if the content is a full answer."""
        mock_client = Mock()
        mock_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps(
                {
                    "optimized_prompt": (
                        "The operation that killed Osama bin Laden happened on May 2, 2011.\n\n"
                        "**Location:** Abbottabad, Pakistan.\n\n"
                        "**Forces:** U.S. Navy SEALs carried out the raid after years of "
                        "intelligence work."
                    )
                }
            ),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        mock_client.get_completion.return_value = mock_response

        optimizer = PromptOptimizer(provider="openai", max_retries=1, client=mock_client)
        result = optimizer.optimize_prompt({"prompt": "how osama was killed"})

        assert result["optimized_prompt"] == "how osama was killed"
        assert result["error"]["code"] == "optimization_rejected"


class TestSelfCorrection:
    """Test self-correction mechanisms."""

    def test_retry_on_invalid_json(self):
        """Test retry when OpenAI returns invalid JSON."""
        # Setup mock
        mock_client = Mock()

        # First call returns invalid JSON, second call returns valid
        invalid_response = UnifiedResponse(
            request_id="test-123",
            text="This is not JSON",
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

        valid_response = UnifiedResponse(
            request_id="test-456",
            text=json.dumps({"optimized_prompt": "Improved prompt"}),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

        mock_client.get_completion.side_effect = [invalid_response, valid_response]

        # Test
        optimizer = PromptOptimizer(provider="openai", max_retries=3, client=mock_client)
        result = optimizer.optimize_prompt({"prompt": "write code for sorting"})

        # Should succeed on second attempt
        assert "optimized_prompt" in result
        assert result["optimized_prompt"] == "Improved prompt"
        assert mock_client.get_completion.call_count == 2


@pytest.mark.integration
class TestIntegration:
    """Integration tests with real OpenAI API (requires API key)."""

    @pytest.mark.skip(reason="Requires valid OpenAI API key and makes real API calls")
    def test_real_optimization(self):
        """Test with real OpenAI API."""
        import os

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        optimizer = PromptOptimizer(api_key=api_key)
        result = optimizer.optimize_prompt(
            {"prompt": "write code for sorting", "settings": {"focus": "clarity"}}
        )

        # Assertions
        assert "optimized_prompt" in result
        assert len(result["optimized_prompt"]) > len("write code for sorting")
        assert "error" not in result or result.get("error") is None
