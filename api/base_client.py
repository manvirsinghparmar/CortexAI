"""
Base AI Client with Unified Response Contract

All provider clients MUST inherit from this class and return UnifiedResponse.
This enforces the "locked" contract across all providers.
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any
import re

from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
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
        self.model_name = kwargs.get("model_name")
        self.provider_name = self.__class__.__name__.replace("Client", "").lower()

    @abstractmethod
    def get_completion(
        self,
        prompt: str | None = None,
        *,
        messages: list | None = None,
        save_full: bool = False,
        **kwargs,
    ) -> UnifiedResponse:
        """
        Get a completion from the AI model.

        THIS IS THE LOCKED CONTRACT. All providers MUST return UnifiedResponse.

        Args:
            prompt: (Legacy) Single string prompt - converted to [{"role": "user", "content": prompt}]
            messages: (Multi-turn) List of message dicts with 'role' and 'content' keys.
                     Format: [{"role": "system|user|assistant", "content": str}, ...]
            save_full: If True, include raw provider response in response.raw
            **kwargs: Additional parameters for the API call

        Returns:
            UnifiedResponse: Normalized response object

        IMPORTANT:
        - If messages is provided, use it as the full conversation context
        - If messages is None but prompt is provided, convert prompt to messages format
        - If both are None, return UnifiedResponse with error
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

    def _normalize_input(
        self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        Normalize input to messages format.

        Converts legacy prompt parameter to messages format for backward compatibility.

        Args:
            prompt: Single string prompt (legacy)
            messages: List of message dicts (new multi-turn format)

        Returns:
            List of message dicts in standard format

        Raises:
            ValueError: If both prompt and messages are None
        """
        if messages is not None:
            # Use provided messages
            if not isinstance(messages, list):
                raise ValueError("messages must be a list")
            return messages

        if prompt is not None:
            # Convert prompt to messages format
            if not isinstance(prompt, str):
                raise ValueError("prompt must be a string")
            return [{"role": "user", "content": prompt}]

        # Neither provided
        raise ValueError("Either 'prompt' or 'messages' must be provided")

    @staticmethod
    def _extract_text_from_content(content: Any) -> str:
        """Extract plain text from provider-neutral message content."""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content or "")

        text_chunks: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "").strip().lower()
            if block_type in {"text", "input_text", "output_text"}:
                value = block.get("text")
                if value is None:
                    value = block.get("content")
                if value:
                    text_chunks.append(str(value))
        return "".join(text_chunks).strip()

    @classmethod
    def _normalize_message_text(cls, message: dict[str, Any]) -> str:
        return cls._extract_text_from_content(message.get("content"))

    @staticmethod
    def _normalize_inference_attachments(attachments: Any) -> list[dict[str, Any]]:
        """Normalize attachment payloads passed from API layer to provider clients."""
        if not attachments:
            return []
        if not isinstance(attachments, list):
            raise ValueError("attachments must be a list when provided")

        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(attachments):
            if not isinstance(item, dict):
                raise ValueError(f"attachments[{idx}] must be an object")

            mime_type = str(item.get("mime_type") or "").strip().lower()
            data_base64 = str(item.get("data_base64") or "").strip()
            extracted_text = str(item.get("extracted_text") or "").strip()
            if not mime_type:
                raise ValueError(f"attachments[{idx}].mime_type is required")
            if not data_base64 and not extracted_text:
                raise ValueError(
                    f"attachments[{idx}] must include either data_base64 or extracted_text"
                )

            normalized.append(
                {
                    "file_id": str(item.get("file_id") or ""),
                    "filename": str(item.get("filename") or "file"),
                    "mime_type": mime_type,
                    "data_base64": data_base64,
                    "extracted_text": extracted_text,
                    "usage_role": str(item.get("usage_role") or "primary"),
                    "transform_mode": str(item.get("transform_mode") or "auto"),
                    "order_index": int(item.get("order_index", idx)),
                }
            )
        return normalized

    @classmethod
    def _merge_text_attachments_into_messages(
        cls,
        messages: list[dict[str, Any]],
        attachments: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Merge extracted text attachments into the last user message.

        Returns:
            (messages_with_text_context, binary_attachments_only)
        """
        if not attachments:
            return messages, []

        text_attachments = [item for item in attachments if str(item.get("extracted_text") or "").strip()]
        binary_attachments = [item for item in attachments if str(item.get("data_base64") or "").strip()]
        if not text_attachments:
            return messages, binary_attachments

        text_block = cls._build_text_attachment_context(text_attachments)
        if not text_block:
            return messages, binary_attachments

        merged_messages: list[dict[str, Any]] = [dict(message) for message in (messages or [])]
        last_user_index = None
        for idx, message in enumerate(merged_messages):
            role = str(message.get("role") or "").strip().lower()
            if role == "user":
                last_user_index = idx

        if last_user_index is None:
            merged_messages.append({"role": "user", "content": text_block})
            return merged_messages, binary_attachments

        current = merged_messages[last_user_index]
        current_content = current.get("content")
        if isinstance(current_content, str):
            combined = current_content.strip()
            if combined:
                combined = f"{combined}\n\n{text_block}"
            else:
                combined = text_block
            current["content"] = combined
            return merged_messages, binary_attachments

        if isinstance(current_content, list):
            next_content = list(current_content)
            next_content.append({"type": "text", "text": text_block})
            current["content"] = next_content
            return merged_messages, binary_attachments

        current["content"] = f"{cls._extract_text_from_content(current_content)}\n\n{text_block}".strip()
        return merged_messages, binary_attachments

    @staticmethod
    def _build_text_attachment_context(attachments: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for attachment in attachments:
            filename = str(attachment.get("filename") or "file").strip() or "file"
            mime_type = str(attachment.get("mime_type") or "").strip().lower()
            extracted_text = str(attachment.get("extracted_text") or "").strip()
            if not extracted_text:
                continue
            parts.append(
                f"[Attachment: {filename} ({mime_type})]\n{extracted_text}"
            )
        if not parts:
            return ""
        return "Attachment context:\n\n" + "\n\n".join(parts)

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
        self, exception: Exception, provider: str | None = None
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
        if "timeout" in exc_str or "timed out" in exc_str:
            return NormalizedError(
                code="timeout",
                message=f"Request timed out: {exception}",
                provider=provider,
                retryable=True,
                details={"exception_type": exc_type},
            )

        # Authentication errors
        if (
            "401" in exc_str
            or "403" in exc_str
            or "unauthorized" in exc_str
            or "api key" in exc_str
            or "authentication" in exc_str
        ):
            return NormalizedError(
                code="auth",
                message=f"Authentication failed: {exception}",
                provider=provider,
                retryable=False,
                details={"exception_type": exc_type},
            )

        # Rate limit errors
        if "429" in exc_str or "rate limit" in exc_str or "too many requests" in exc_str:
            return NormalizedError(
                code="rate_limit",
                message=f"Rate limit exceeded: {exception}",
                provider=provider,
                retryable=True,
                details={"exception_type": exc_type},
            )

        # Bad request errors
        if "400" in exc_str or "bad request" in exc_str or "invalid" in exc_str:
            return NormalizedError(
                code="bad_request",
                message=f"Invalid request: {exception}",
                provider=provider,
                retryable=False,
                details={"exception_type": exc_type},
            )

        # Provider errors (5xx)
        if (
            any(code in exc_str for code in ["500", "502", "503", "504"])
            or "server error" in exc_str
        ):
            return NormalizedError(
                code="provider_error",
                message=f"Provider error: {exception}",
                provider=provider,
                retryable=True,
                details={"exception_type": exc_type},
            )

        # Unknown error
        return NormalizedError(
            code="unknown",
            message=f"Unexpected error: {exception}",
            provider=provider,
            retryable=False,
            details={"exception_type": exc_type},
        )

    def _normalize_finish_reason(
        self, provider_reason: str | None, provider: str | None = None
    ) -> str | None:
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
        if reason_lower in ("stop", "end_turn", "complete", "finished"):
            return "stop"

        # Max tokens/length
        if (
            "length" in reason_lower
            or "max_tokens" in reason_lower
            or "token_limit" in reason_lower
        ):
            return "length"

        # Tool/function call
        if "tool" in reason_lower or "function" in reason_lower:
            return "tool"

        # Content filter
        if "content_filter" in reason_lower or "safety" in reason_lower or "policy" in reason_lower:
            return "content_filter"

        # Error
        if "error" in reason_lower:
            return "error"

        # Unknown - log for debugging
        logger.debug(
            f"Unknown finish reason from {provider or self.provider_name}: {provider_reason}",
            extra={"extra_fields": {"provider_reason": provider_reason}},
        )
        return None

    def _create_error_response(
        self, request_id: str, error: NormalizedError, latency_ms: int = 0, model: str | None = None
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
            metadata={},
        )

    @staticmethod
    def _extract_unsupported_parameter(exception: Exception) -> str | None:
        """
        Try to parse unsupported parameter name from provider error messages.
        """
        message = str(exception)
        patterns = (
            r"Unsupported parameter:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?",
            r"Unknown parameter:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?",
            r"Unrecognized request argument supplied:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?",
            r"Parameter\s+['\"]?([A-Za-z0-9_.-]+)['\"]?\s+is not supported",
            r"Unsupported argument:\s*['\"]?([A-Za-z0-9_.-]+)['\"]?",
        )
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return str(match.group(1) or "").strip().lower() or None
        return None

    def _build_retry_payload_without_unsupported_parameter(
        self,
        payload: dict[str, Any],
        exception: Exception,
        *,
        safe_parameters: set[str] | None = None,
    ) -> tuple[str | None, dict[str, Any] | None]:
        """
        Return (dropped_param, retry_payload) when adaptive retry is safe, else (None, None).
        """
        unsupported = self._extract_unsupported_parameter(exception)
        if not unsupported:
            return None, None

        allowed = safe_parameters or {
            "temperature",
            "max_tokens",
            "max_completion_tokens",
            "max_output_tokens",
            "top_p",
            "presence_penalty",
            "frequency_penalty",
            "reasoning_effort",
        }
        if unsupported not in allowed:
            return None, None

        key_lookup = {str(key).strip().lower(): key for key in payload.keys()}
        matching_key = key_lookup.get(unsupported)
        if matching_key is None:
            return None, None

        retry_payload = dict(payload)
        retry_payload.pop(matching_key, None)
        return str(matching_key), retry_payload
