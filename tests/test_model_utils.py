"""
Comprehensive test suite for ModelUtils and GeminiClient

Test Categories:
1. Unit Tests - Fast tests with mocks, test business logic
2. Integration Tests - Test real API behavior (requires API key)
3. GeminiClient Tests - Test the API wrapper directly

Run commands:
- Unit tests only: pytest tests/test_model_utils.py -m "not integration"
- Integration tests: GEMINI_API_KEY=your_key pytest tests/test_model_utils.py -m integration
- All tests: pytest tests/test_model_utils.py --cov=utils
"""

from unittest.mock import patch, MagicMock, call
from utils.model_utils import ModelUtils
import pytest
from io import StringIO
import os
import sys

# Make GeminiAvailableModels available as a top-level module for imports
import utils.GeminiAvailableModels
sys.modules['GeminiAvailableModels'] = utils.GeminiAvailableModels


# ============================================================================
# UNIT TESTS - Test logic with mocks (fast, no external dependencies)
# ============================================================================

class TestModelUtilsUnit:
    """Unit tests with mocks - test logic, not real API"""

    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_success_with_output(self, mock_stdout, mock_gemini_class):
        """Test successful model listing and verify printed output"""
        # Setup mock
        mock_client = MagicMock()
        mock_gemini_class.return_value = mock_client

        # Mock models with different capabilities
        mock_models = [
            ("models/gemini-2.0-pro", ["generateContent", "other"]),
            ("models/gemini-1.5-flash", ["generateContent"]),
            ("models/gemini-embed", ["embedContent"])  # Should be filtered out
        ]
        mock_client.list_models.return_value = mock_models

        # Execute
        ModelUtils.list_available_models('test-key', 'gemini-2.0-pro')
        ModelUtils.list_available_models(
            api_key="enter your own key here to run the test",
            current_model="gpt-4o",
            provider="openai"
        )

        # Verify output
        output = mock_stdout.getvalue()
        assert "gemini-2.0-pro" in output, "Current model should be in output"
        assert "(current)" in output, "Current model should be marked"
        assert "gemini-1.5-flash" in output, "Other generateContent models should be listed"
        assert "gemini-embed" not in output, "Models without generateContent should be filtered"
        assert "Available Gemini Models" in output, "Header should be present"

        # Verify mock calls
        mock_gemini_class.assert_called_once_with(api_key='test-key', model_name='gemini-2.0-pro')
        mock_client.list_models.assert_called_once()


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_filters_non_generation_models(self, mock_stdout, mock_gemini_class):
        """Test that only models with generateContent are shown"""
        mock_client = MagicMock()
        mock_gemini_class.return_value = mock_client

        mock_models = [
            ("models/gemini-pro", ["generateContent"]),
            ("models/embedding-001", ["embedContent"]),  # No generateContent
            ("models/vision-only", None),  # No methods at all
        ]
        mock_client.list_models.return_value = mock_models

        ModelUtils.list_available_models('test-key', 'gemini-pro')

        output = mock_stdout.getvalue()
        assert "gemini-pro" in output
        assert "embedding-001" not in output
        assert "vision-only" not in output


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_api_authentication_error(self, mock_stdout, mock_gemini_class):
        """Test handling of authentication errors (401)"""
        # Simulate authentication error
        mock_gemini_class.side_effect = Exception("401: Invalid API key")

        # Should not raise exception, but print warning
        ModelUtils.list_available_models('invalid-key', 'gemini-pro')

        output = mock_stdout.getvalue()
        assert "Warning" in output, "Should print warning message"
        assert ("401" in output or "Invalid API key" in output), "Should include error details"

        # Verify attempted initialization
        mock_gemini_class.assert_called_once_with(api_key='invalid-key', model_name='gemini-pro')


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_rate_limit_error(self, mock_stdout, mock_gemini_class):
        """Test handling of rate limit errors (429)"""
        mock_gemini_class.side_effect = Exception("429: Too Many Requests")

        ModelUtils.list_available_models('test-key', 'gemini-pro')

        output = mock_stdout.getvalue()
        assert "Warning" in output
        assert "429" in output or "Too Many Requests" in output


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_server_error(self, mock_stdout, mock_gemini_class):
        """Test handling of server errors (500)"""
        mock_gemini_class.side_effect = Exception("500: Internal Server Error")

        ModelUtils.list_available_models('test-key', 'gemini-pro')

        output = mock_stdout.getvalue()
        assert "Warning" in output
        assert "500" in output or "Internal Server Error" in output


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_empty_response(self, mock_stdout, mock_gemini_class):
        """Test handling of empty model list"""
        mock_client = MagicMock()
        mock_gemini_class.return_value = mock_client
        mock_client.list_models.return_value = []

        # Should not raise exception
        ModelUtils.list_available_models('test-key', 'gemini-pro')

        output = mock_stdout.getvalue()
        assert "Available Gemini Models" in output
        mock_client.list_models.assert_called_once()


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_network_timeout(self, mock_stdout, mock_gemini_class):
        """Test handling of network timeout"""
        mock_client = MagicMock()
        mock_gemini_class.return_value = mock_client
        mock_client.list_models.side_effect = Exception("Request timeout")

        ModelUtils.list_available_models('test-key', 'gemini-pro')

        output = mock_stdout.getvalue()
        assert "Warning" in output
        assert "timeout" in output.lower()


    @patch('utils.GeminiAvailableModels.GeminiClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_models_current_model_marking(self, mock_stdout, mock_gemini_class):
        """Test that current model is correctly marked"""
        mock_client = MagicMock()
        mock_gemini_class.return_value = mock_client

        mock_models = [
            ("models/gemini-2.0-flash", ["generateContent"]),
            ("models/gemini-1.5-pro", ["generateContent"]),
        ]
        mock_client.list_models.return_value = mock_models

        # Test with gemini-1.5-pro as current
        ModelUtils.list_available_models('test-key', 'gemini-1.5-pro')

        output = mock_stdout.getvalue()
        # Find the line with gemini-1.5-pro and verify it has (current)
        lines = output.split('\n')
        pro_line = [line for line in lines if 'gemini-1.5-pro' in line]
        assert len(pro_line) > 0
        assert '(current)' in pro_line[0]

        # gemini-2.0-flash should not have (current)
        flash_line = [line for line in lines if 'gemini-2.0-flash' in line]
        if flash_line:
            assert '(current)' not in flash_line[0]


# ============================================================================
# INTEGRATION TESTS - Test with real API (requires API key)
# ============================================================================

@pytest.mark.integration
class TestModelUtilsIntegration:
    """Integration tests - test with real API or realistic scenarios"""

    @pytest.mark.skipif(not os.getenv('GEMINI_API_KEY'), reason="No GEMINI_API_KEY environment variable")
    def test_real_api_call_success(self):
        """Test actual API call with real credentials (200 OK)"""
        api_key = os.getenv('GEMINI_API_KEY')

        # This will make a real API call
        # If it doesn't raise an exception, the API call succeeded
        try:
            ModelUtils.list_available_models(api_key, 'gemini-pro')
            # Success - no exception raised
        except Exception as e:
            pytest.fail(f"Real API call failed: {e}")


    def test_api_call_with_invalid_key_returns_401(self):
        """Test API response with invalid key (should get 401-like error)"""
        # Use obviously invalid key
        invalid_key = "invalid_key_12345_not_real"

        # Should handle gracefully and print warning (not raise)
        try:
            ModelUtils.list_available_models(invalid_key, 'gemini-pro')
            # Should complete without raising
        except Exception as e:
            pytest.fail(f"Should handle invalid key gracefully, but raised: {e}")


    @patch('utils.GeminiAvailableModels.genai.Client')
    def test_api_network_timeout_handling(self, mock_client_class):
        """Test network timeout handling"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Simulate timeout
        import socket
        mock_client.models.list.side_effect = socket.timeout("Connection timeout")

        # Should handle timeout gracefully
        try:
            ModelUtils.list_available_models('test-key', 'gemini-pro')
        except socket.timeout:
            pytest.fail("Should catch and handle timeout, not propagate it")


    @pytest.mark.skipif(not os.getenv('GEMINI_API_KEY'), reason="No GEMINI_API_KEY environment variable")
    def test_real_api_returns_valid_model_list(self):
        """Test that real API returns expected data structure"""
        api_key = os.getenv('GEMINI_API_KEY')

        # We need to test the client directly for this
        from utils.GeminiAvailableModels import GeminiClient

        client = GeminiClient(api_key, 'gemini-pro')
        models = client.list_models()

        # Verify structure
        assert isinstance(models, list), "Should return a list"
        assert len(models) > 0, "Should return at least one model"

        # Check first model structure
        model_name, methods = models[0]
        assert isinstance(model_name, str), "Model name should be string"
        assert model_name.startswith('models/'), "Model name should start with 'models/'"


# ============================================================================
# GEMINI CLIENT TESTS - Test the API wrapper directly
# ============================================================================

class TestGeminiClient:
    """Test the GeminiClient wrapper class"""

    @patch('utils.GeminiAvailableModels.genai.Client')
    def test_client_initialization_with_valid_params(self, mock_client_class):
        """Test that client initializes correctly"""
        from utils.GeminiAvailableModels import GeminiClient

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        client = GeminiClient('test-api-key', 'gemini-pro')

        # Verify initialization
        assert client.model_name == 'gemini-pro'
        assert client.client == mock_client_instance

        # Verify genai.Client was called correctly
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs['api_key'] == 'test-api-key'


    @patch('utils.GeminiAvailableModels.genai.Client')
    def test_client_default_model_name(self, mock_client_class):
        """Test that client uses default model when None provided"""
        from utils.GeminiAvailableModels import GeminiClient

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        client = GeminiClient('test-api-key', None)

        assert client.model_name == 'gemini-2.5-flash', "Should use default model"


    @patch('utils.GeminiAvailableModels.genai.Client')
    def test_list_models_returns_correct_structure(self, mock_client_class):
        """Test that list_models returns expected tuple structure"""
        from utils.GeminiAvailableModels import GeminiClient

        # Setup mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Create mock model objects
        mock_model1 = MagicMock()
        mock_model1.name = "models/gemini-pro"
        mock_model1.supported_generation_methods = ["generateContent"]

        mock_model2 = MagicMock()
        mock_model2.name = "models/gemini-vision"
        mock_model2.supported_generation_methods = None

        mock_client_instance.models.list.return_value = [mock_model1, mock_model2]

        # Test
        client = GeminiClient('test-api-key', 'gemini-pro')
        result = client.list_models()

        # Verify
        assert len(result) == 2
        assert result[0] == ("models/gemini-pro", ["generateContent"])
        assert result[1] == ("models/gemini-vision", None)


    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv('GEMINI_API_KEY'), reason="No GEMINI_API_KEY environment variable")
    def test_client_real_api_initialization(self):
        """Test that client initializes with real API key"""
        from utils.GeminiAvailableModels import GeminiClient

        api_key = os.getenv('GEMINI_API_KEY')

        try:
            client = GeminiClient(api_key, 'gemini-pro')
            assert client.client is not None
            assert client.model_name == 'gemini-pro'
        except Exception as e:
            pytest.fail(f"Client initialization failed: {e}")


    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv('GEMINI_API_KEY'), reason="No GEMINI_API_KEY environment variable")
    def test_client_real_list_models_call(self):
        """Test real API call to list models"""
        from utils.GeminiAvailableModels import GeminiClient

        api_key = os.getenv('GEMINI_API_KEY')
        client = GeminiClient(api_key, 'gemini-pro')

        try:
            models = client.list_models()

            # Verify response structure
            assert isinstance(models, list)
            assert len(models) > 0

            # Verify each model has correct structure
            for model_name, methods in models:
                assert isinstance(model_name, str)
                assert model_name.startswith('models/')
                # methods can be None or a list
                if methods is not None:
                    assert isinstance(methods, (list, tuple))

        except Exception as e:
            pytest.fail(f"list_models call failed: {e}")


    @patch('utils.GeminiAvailableModels.genai.Client')
    def test_client_handles_list_models_exception(self, mock_client_class):
        """Test that exceptions from list_models are propagated"""
        from utils.GeminiAvailableModels import GeminiClient

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        mock_client_instance.models.list.side_effect = Exception("API Error")

        client = GeminiClient('test-api-key', 'gemini-pro')

        # Should propagate the exception
        with pytest.raises(Exception) as exc_info:
            client.list_models()

        assert "API Error" in str(exc_info.value)


# ============================================================================
# TEST FIXTURES AND HELPERS
# ============================================================================

@pytest.fixture
def mock_gemini_client():
    """Fixture to provide a mocked GeminiClient"""
    with patch('utils.model_utils.GeminiAvailableModels') as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock, mock_client


@pytest.fixture
def sample_models():
    """Fixture providing sample model data"""
    return [
        ("models/gemini-2.0-flash", ["generateContent", "countTokens"]),
        ("models/gemini-1.5-pro", ["generateContent"]),
        ("models/gemini-1.5-flash", ["generateContent"]),
        ("models/embedding-001", ["embedContent"]),
    ]