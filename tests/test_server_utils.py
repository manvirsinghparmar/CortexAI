from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
from server.utils import clamp_max_tokens, normalize_empty_success_response, redact_sensitive_headers


def _build_response(
    *,
    text: str,
    finish_reason: str | None = "stop",
    error: NormalizedError | None = None,
    metadata: dict | None = None,
) -> UnifiedResponse:
    return UnifiedResponse(
        request_id="req_utils",
        text=text,
        provider="openai",
        model="gpt-5.1",
        latency_ms=5,
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        estimated_cost=0.0,
        finish_reason=finish_reason,
        error=error,
        metadata=metadata or {},
    )


def test_clamp_max_tokens_returns_none_when_unset():
    assert clamp_max_tokens(None) is None


def test_clamp_max_tokens_caps_at_server_limit():
    assert clamp_max_tokens(99999) == 2048


def test_clamp_max_tokens_preserves_small_values():
    assert clamp_max_tokens(128) == 128


def test_normalize_empty_success_keeps_non_empty_response():
    original = _build_response(text="useful answer", finish_reason="stop")
    normalized = normalize_empty_success_response(original)
    assert normalized == original


def test_normalize_empty_success_keeps_existing_error_unchanged():
    original = _build_response(
        text="",
        finish_reason="error",
        error=NormalizedError(
            code="provider_error",
            message="already errored",
            provider="openai",
            retryable=True,
        ),
    )
    normalized = normalize_empty_success_response(original)
    assert normalized == original


def test_normalize_empty_success_converts_empty_length_to_provider_error():
    original = _build_response(
        text="",
        finish_reason="length",
        metadata={"endpoint": "chat.completions"},
    )
    normalized = normalize_empty_success_response(original)
    assert normalized.is_error
    assert normalized.error is not None
    assert normalized.error.code == "provider_error"
    assert normalized.error.retryable is True
    assert normalized.error.details["finish_reason"] == "length"
    assert normalized.error.details["endpoint"] == "chat.completions"
    assert normalized.finish_reason == "error"


def test_normalize_empty_success_content_filter_is_non_retryable():
    original = _build_response(text="", finish_reason="content_filter")
    normalized = normalize_empty_success_response(original)
    assert normalized.is_error
    assert normalized.error is not None
    assert normalized.error.retryable is False
    assert "filtered" in normalized.error.message.lower()


def test_normalize_empty_success_works_without_metadata():
    original = _build_response(text="", finish_reason=None, metadata=None)
    normalized = normalize_empty_success_response(original)
    assert normalized.is_error
    assert normalized.error is not None
    assert normalized.error.code == "provider_error"
    assert normalized.error.details == {}


def test_redact_sensitive_headers_is_case_insensitive():
    headers = {
        "x-api-key": "secret-key",
        "Authorization": "Bearer xyz",
        "Content-Type": "application/json",
    }
    redacted = redact_sensitive_headers(headers)
    assert redacted["x-api-key"] == "[REDACTED]"
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"
