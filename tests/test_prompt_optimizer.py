"""
Tests for Prompt Optimizer Module

Comprehensive test suite covering input validation, optimization flow,
output schema validation, error handling, and self-correction mechanisms.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from utils.prompt_optimizer import PromptOptimizer
from models.unified_response import UnifiedResponse, TokenUsage, NormalizedError


class TestInputValidation:
    """Test input validation logic."""
    
    def test_valid_input_with_prompt_only(self):
        """Test valid input with only prompt field."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = {"prompt": "write code for sorting"}
        
        error = optimizer._validate_input(input_data)
        assert error is None
    
    def test_valid_input_with_settings(self):
        """Test valid input with prompt and settings."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = {
            "prompt": "write code for sorting",
            "settings": {"focus": "clarity", "language": "python"}
        }
        
        error = optimizer._validate_input(input_data)
        assert error is None
    
    def test_missing_prompt_field(self):
        """Test error when prompt field is missing."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = {"settings": {"focus": "clarity"}}
        
        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "prompt" in error["error"]["message"].lower()
    
    def test_empty_prompt(self):
        """Test error when prompt is empty."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = {"prompt": "   "}
        
        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "empty" in error["error"]["message"].lower()
    
    def test_non_string_prompt(self):
        """Test error when prompt is not a string."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = {"prompt": 123}
        
        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "string" in error["error"]["message"].lower()
    
    def test_non_dict_input(self):
        """Test error when input is not a dictionary."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = "not a dict"
        
        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "dictionary" in error["error"]["message"].lower()
    
    def test_invalid_settings_type(self):
        """Test error when settings is not a dictionary."""
        optimizer = PromptOptimizer(api_key="test-key")
        input_data = {
            "prompt": "test prompt",
            "settings": "not a dict"
        }
        
        error = optimizer._validate_input(input_data)
        assert error is not None
        assert "error" in error
        assert "settings" in error["error"]["message"].lower()


class TestOutputValidation:
    """Test output schema validation."""
    
    def test_valid_output_minimal(self):
        """Test valid output with only required field."""
        optimizer = PromptOptimizer(api_key="test-key")
        output = {"optimized_prompt": "Improved prompt"}
        
        assert optimizer._is_valid_output(output) is True
    
    def test_valid_output_complete(self):
        """Test valid output with all optional fields."""
        optimizer = PromptOptimizer(api_key="test-key")
        output = {
            "optimized_prompt": "Improved prompt",
            "steps": ["Step 1", "Step 2"],
            "explanations": ["Explanation 1", "Explanation 2"],
            "metrics": {"clarity": 8.5, "specificity": 9.0}
        }
        
        assert optimizer._is_valid_output(output) is True
    
    def test_missing_required_field(self):
        """Test invalid output missing optimized_prompt."""
        optimizer = PromptOptimizer(api_key="test-key")
        output = {"steps": ["Step 1"]}
        
        assert optimizer._is_valid_output(output) is False
    
    def test_invalid_steps_type(self):
        """Test invalid output with wrong steps type."""
        optimizer = PromptOptimizer(api_key="test-key")
        output = {
            "optimized_prompt": "Test",
            "steps": "not a list"
        }
        
        assert optimizer._is_valid_output(output) is False
    
    def test_invalid_explanations_items(self):
        """Test invalid output with non-string explanations."""
        optimizer = PromptOptimizer(api_key="test-key")
        output = {
            "optimized_prompt": "Test",
            "explanations": [123, 456]
        }
        
        assert optimizer._is_valid_output(output) is False
    
    def test_invalid_metrics_type(self):
        """Test invalid output with wrong metrics type."""
        optimizer = PromptOptimizer(api_key="test-key")
        output = {
            "optimized_prompt": "Test",
            "metrics": "not a dict"
        }
        
        assert optimizer._is_valid_output(output) is False


class TestResponseParsing:
    """Test OpenAI response parsing."""
    
    def test_parse_plain_json(self):
        """Test parsing plain JSON response."""
        optimizer = PromptOptimizer(api_key="test-key")
        response_text = json.dumps({
            "optimized_prompt": "Improved prompt",
            "steps": ["Step 1"]
        })
        
        result = optimizer._parse_openai_response(response_text, "original")
        assert result["optimized_prompt"] == "Improved prompt"
        assert result["steps"] == ["Step 1"]
    
    def test_parse_markdown_code_block(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        optimizer = PromptOptimizer(api_key="test-key")
        response_text = """```json
{
  "optimized_prompt": "Improved prompt",
  "steps": ["Step 1"]
}
```"""
        
        result = optimizer._parse_openai_response(response_text, "original")
        assert result["optimized_prompt"] == "Improved prompt"
        assert result["steps"] == ["Step 1"]
    
    def test_parse_invalid_json(self):
        """Test error handling for invalid JSON."""
        optimizer = PromptOptimizer(api_key="test-key")
        response_text = "This is not JSON"
        
        with pytest.raises(Exception) as exc_info:
            optimizer._parse_openai_response(response_text, "original")
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_parse_missing_required_field(self):
        """Test error when optimized_prompt is missing."""
        optimizer = PromptOptimizer(api_key="test-key")
        response_text = json.dumps({"steps": ["Step 1"]})
        
        with pytest.raises(Exception) as exc_info:
            optimizer._parse_openai_response(response_text, "original")
        
        assert "optimized_prompt" in str(exc_info.value)


class TestOptimizationFlow:
    """Test the complete optimization flow with mocked OpenAI."""
    
    @patch('utils.prompt_optimizer.OpenAIClient')
    def test_successful_optimization(self, mock_client_class):
        """Test successful optimization flow."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps({
                "optimized_prompt": "Write a Python function to sort a list of integers in ascending order",
                "steps": [
                    "Added specificity about programming language",
                    "Clarified the sorting order",
                    "Made the data type explicit"
                ],
                "explanations": [
                    "Specifying Python makes the request unambiguous",
                    "Ascending order is more common but should be explicit"
                ],
                "metrics": {"clarity_score": 9.0, "specificity_score": 8.5}
            }),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={}
        )
        mock_client.get_completion.return_value = mock_response
        
        # Test
        optimizer = PromptOptimizer(api_key="test-key")
        result = optimizer.optimize_prompt({
            "prompt": "write code for sorting"
        })
        
        # Assertions
        assert "optimized_prompt" in result
        assert "Python" in result["optimized_prompt"]
        assert "steps" in result
        assert len(result["steps"]) == 3
        assert "explanations" in result
        assert "metrics" in result
        assert "error" not in result
    
    @patch('utils.prompt_optimizer.OpenAIClient')
    def test_optimization_with_settings(self, mock_client_class):
        """Test optimization with additional settings."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = UnifiedResponse(
            request_id="test-123",
            text=json.dumps({
                "optimized_prompt": "Create a clear, beginner-friendly Python tutorial on sorting",
                "steps": ["Added clarity focus", "Made it beginner-friendly"]
            }),
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=500,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
            estimated_cost=0.001,
            finish_reason="stop",
            error=None,
            metadata={}
        )
        mock_client.get_completion.return_value = mock_response
        
        # Test
        optimizer = PromptOptimizer(api_key="test-key")
        result = optimizer.optimize_prompt({
            "prompt": "write code for sorting",
            "settings": {"focus": "clarity", "audience": "beginners"}
        })
        
        # Assertions
        assert "optimized_prompt" in result
        assert "error" not in result
    
    @patch('utils.prompt_optimizer.OpenAIClient')
    def test_api_error_handling(self, mock_client_class):
        """Test handling of OpenAI API errors."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
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
                code="rate_limit",
                message="Rate limit exceeded",
                provider="openai",
                retryable=True
            ),
            metadata={}
        )
        mock_client.get_completion.return_value = mock_error_response
        
        # Test
        optimizer = PromptOptimizer(api_key="test-key", max_retries=2)
        result = optimizer.optimize_prompt({
            "prompt": "write code for sorting"
        })
        
        # Assertions
        assert "error" in result
        assert "optimized_prompt" in result  # Should return original as fallback
        assert result["optimized_prompt"] == "write code for sorting"


class TestSelfCorrection:
    """Test self-correction mechanisms."""
    
    @patch('utils.prompt_optimizer.OpenAIClient')
    def test_retry_on_invalid_json(self, mock_client_class):
        """Test retry when OpenAI returns invalid JSON."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
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
            metadata={}
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
            metadata={}
        )
        
        mock_client.get_completion.side_effect = [invalid_response, valid_response]
        
        # Test
        optimizer = PromptOptimizer(api_key="test-key", max_retries=3)
        result = optimizer.optimize_prompt({
            "prompt": "write code for sorting"
        })
        
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
        result = optimizer.optimize_prompt({
            "prompt": "write code for sorting",
            "settings": {"focus": "clarity"}
        })
        
        # Assertions
        assert "optimized_prompt" in result
        assert len(result["optimized_prompt"]) > len("write code for sorting")
        assert "error" not in result or result.get("error") is None
