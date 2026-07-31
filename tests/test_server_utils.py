from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
from server.utils import (
    clamp_max_tokens,
    effective_output_token_limit,
    normalize_empty_success_response,
    redact_sensitive_headers,
    sanitize_provider_error_response,
)


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


def test_effective_output_limit_matches_provider_clamp_and_default():
    assert effective_output_token_limit(128) == 128
    assert effective_output_token_limit(2048) == 2048
    assert effective_output_token_limit(2049) == 2048
    assert effective_output_token_limit(100_000_000) == 2048
    assert effective_output_token_limit(None) == 2048


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


def test_sanitize_provider_error_response_hides_raw_transient_capacity_payload():
    original = _build_response(
        text="",
        finish_reason="error",
        error=NormalizedError(
            code="provider_error",
            message=(
                "Provider error: 503 UNAVAILABLE. {'error': {'message': "
                "'This model is currently experiencing high demand. Please try again later.'}}"
            ),
            provider="gemini",
            retryable=True,
            details={"exception_type": "ServerError"},
        ),
    )

    sanitized = sanitize_provider_error_response(original)

    assert sanitized.error is not None
    assert (
        sanitized.error.message
        == "This model is temporarily busy. Try again shortly or switch to another model."
    )
    assert sanitized.error.details["kind"] == "transient_capacity"
    assert sanitized.error.details["client_safe"] is True
    assert "UNAVAILABLE" not in sanitized.error.message


def test_sanitize_provider_error_response_preserves_explicit_bad_request_message():
    original = _build_response(
        text="",
        finish_reason="error",
        error=NormalizedError(
            code="bad_request",
            message="Model 'not-real' for provider 'openai' is not configured in model_registry.yaml",
            provider="openai",
            retryable=False,
        ),
    )

    assert sanitize_provider_error_response(original) == original
