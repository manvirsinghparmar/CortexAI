"""
Base AI Client with Unified Response Contract

All provider clients MUST inherit from this class and return UnifiedResponse.
This enforces the "locked" contract across all providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import uuid
import time
from models.unified_response import UnifiedResponse, TokenUsage, NormalizedError
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseAIClient(ABC):
    """
    Abstract base class for AI model clients.

    All provider-specific clients MUST:
    1. Inherit from this class
    2. Implement get_completion() returning UnifiedResponse
    3. Use provided helpers for timing, request_id, error normalization
    4. Never raise exceptions - return UnifiedResponse with error instead
    """

    def __init__(self, api_key: str, **kwargs):
        """
        Initialize the AI client.

        Args:
            api_key: API key for the AI service
            **kwargs: Additional model-specific parameters
        """
        self.api_key = api_key
        self.model_name = kwargs.get('model_name')
        self.provider_name = self.__class__.__name__.replace('Client', '').lower()

    @abstractmethod
    def get_completion(
        self,
        prompt: str,
        *,
        save_full: bool = False,
        **kwargs
    ) -> UnifiedResponse:
        """
        Get a completion from the AI model.

        THIS IS THE LOCKED CONTRACT. All providers MUST return UnifiedResponse.

        Args:
            prompt: The input prompt to send to the model
            save_full: If True, include raw provider response in response.raw
            **kwargs: Additional parameters for the API call

        Returns:
            UnifiedResponse: Normalized response object

        IMPORTANT:
        - NEVER raise exceptions - catch all errors and return UnifiedResponse with error
        - Use helper methods: _generate_request_id(), _measure_latency(), _normalize_error()
        - Fill all required fields (text, provider, model, token_usage, etc.)
        - Use CostCalculator for estimated_cost
        """
        pass

    @classmethod
    @abstractmethod
    def list_available_models(cls, api_key: str = None, **kwargs) -> None:
        """
        List all available models for this client.

        Args:
            api_key: Optional API key (if not provided during initialization)
            **kwargs: Additional parameters for the API call
        """
        pass

    # ============================================================
    # HELPER METHODS - Use these in provider implementations
    # ============================================================

    def _generate_request_id(self) -> str:
        """
        Generate a unique request ID for tracking.

        Returns:
            UUID string
        """
        return str(uuid.uuid4())

    def _measure_latency(self, start_time: float) -> int:
        """
        Calculate request latency in milliseconds.

        Args:
            start_time: Start time from time.time()

        Returns:
            Latency in milliseconds
        """
        return int((time.time() - start_time) * 1000)

    def _normalize_error(
        self,
        exception: Exception,
        provider: Optional[str] = None
    ) -> NormalizedError:
        """
        Normalize provider-specific exceptions into standard error codes.

        Error Code Mapping:
        - timeout: Request timeout, connection timeout
        - auth: 401, 403, API key errors
        - rate_limit: 429, rate limit exceeded
        - bad_request: 400, invalid parameters
        - provider_error: 500, 502, 503, 504
        - unknown: All other errors

        Args:
            exception: The exception to normalize
            provider: Provider name (defaults to self.provider_name)

        Returns:
            NormalizedError with appropriate code and retryable flag
        """
        provider = provider or self.provider_name
        exc_str = str(exception).lower()
        exc_type = type(exception).__name__

        # Timeout errors
        if 'timeout' in exc_str or 'timed out' in exc_str:
            return NormalizedError(
                code="timeout",
                message=f"Request timed out: {exception}",
                provider=provider,
                retryable=True,
                details={"exception_type": exc_type}
            )

        # Authentication errors
        if '401' in exc_str or '403' in exc_str or 'unauthorized' in exc_str or 'api key' in exc_str or 'authentication' in exc_str:
            return NormalizedError(
                code="auth",
                message=f"Authentication failed: {exception}",
                provider=provider,
                retryable=False,
                details={"exception_type": exc_type}
            )

        # Rate limit errors
        if '429' in exc_str or 'rate limit' in exc_str or 'too many requests' in exc_str:
            return NormalizedError(
                code="rate_limit",
                message=f"Rate limit exceeded: {exception}",
                provider=provider,
                retryable=True,
                details={"exception_type": exc_type}
            )

        # Bad request errors
        if '400' in exc_str or 'bad request' in exc_str or 'invalid' in exc_str:
            return NormalizedError(
                code="bad_request",
                message=f"Invalid request: {exception}",
                provider=provider,
                retryable=False,
                details={"exception_type": exc_type}
            )

        # Provider errors (5xx)
        if any(code in exc_str for code in ['500', '502', '503', '504']) or 'server error' in exc_str:
            return NormalizedError(
                code="provider_error",
                message=f"Provider error: {exception}",
                provider=provider,
                retryable=True,
                details={"exception_type": exc_type}
            )

        # Unknown error
        return NormalizedError(
            code="unknown",
            message=f"Unexpected error: {exception}",
            provider=provider,
            retryable=False,
            details={"exception_type": exc_type}
        )

    def _normalize_finish_reason(
        self,
        provider_reason: Optional[str],
        provider: Optional[str] = None
    ) -> Optional[str]:
        """
        Normalize provider-specific finish reasons into standard codes.

        Standard Finish Reasons:
        - "stop": Natural completion
        - "length": Max tokens reached
        - "tool": Function/tool call
        - "content_filter": Content policy violation
        - "error": Request failed
        - None: Unknown/not provided

        Args:
            provider_reason: Provider-specific finish reason
            provider: Provider name (for logging)

        Returns:
            Normalized finish reason or None
        """
        if not provider_reason:
            return None

        reason_lower = provider_reason.lower()

        # Natural completion
        if reason_lower in ('stop', 'end_turn', 'complete', 'finished'):
            return "stop"

        # Max tokens/length
        if 'length' in reason_lower or 'max_tokens' in reason_lower or 'token_limit' in reason_lower:
            return "length"

        # Tool/function call
        if 'tool' in reason_lower or 'function' in reason_lower:
            return "tool"

        # Content filter
        if 'content_filter' in reason_lower or 'safety' in reason_lower or 'policy' in reason_lower:
            return "content_filter"

        # Error
        if 'error' in reason_lower:
            return "error"

        # Unknown - log for debugging
        logger.debug(
            f"Unknown finish reason from {provider or self.provider_name}: {provider_reason}",
            extra={"extra_fields": {"provider_reason": provider_reason}}
        )
        return None

    def _create_error_response(
        self,
        request_id: str,
        error: NormalizedError,
        latency_ms: int = 0,
        model: Optional[str] = None
    ) -> UnifiedResponse:
        """
        Create a UnifiedResponse for error cases.

        Helper to ensure consistent error responses across all providers.

        Args:
            request_id: Request ID
            error: Normalized error
            latency_ms: Request latency
            model: Model name (defaults to self.model_name)

        Returns:
            UnifiedResponse with error details
        """
        return UnifiedResponse(
            request_id=request_id,
            text="",
            provider=self.provider_name,
            model=model or self.model_name or "unknown",
            latency_ms=latency_ms,
            token_usage=TokenUsage(),
            estimated_cost=0.0,
            finish_reason="error",
            error=error,
            metadata={}
        )
