"""Shared utilities for FastAPI routes."""

from dataclasses import replace
from collections.abc import Mapping
import re

from models.unified_response import NormalizedError, UnifiedResponse
from utils.logger import get_logger

MAX_CONTEXT_MESSAGES = 10
MAX_CONTEXT_CHARS = 20000
MAX_OUTPUT_TOKENS = 2048
SENSITIVE_HEADERS = {"x-api-key", "authorization", "cookie", "set-cookie"}
logger = get_logger(__name__)
CLIENT_SAFE_PROVIDER_ERROR_MESSAGES = {
    "timeout": "The provider request timed out. Please retry in a moment.",
    "auth": "Provider authentication failed. Check the configured API key.",
    "rate_limited": "The provider is rate limiting requests. Please retry in a moment.",
    "quota_exceeded": "Provider quota is exhausted. Check billing or API key limits.",
    "bad_request": "The provider rejected the request. Check the selected model and request settings.",
    "transient_capacity": "This model is temporarily busy. Try again shortly or switch to another model.",
    "provider_5xx": "The provider is temporarily unavailable. Please retry in a moment.",
    "unknown": "The provider request failed unexpectedly. Please retry or choose another model.",
}


def validate_and_trim_context(context_req):
    """Trim conversation history to prevent token explosion without rejecting long chats."""
    if not context_req or not context_req.conversation_history:
        return context_req

    history = context_req.conversation_history
    original_message_count = len(history)

    # Trim to last N messages
    if len(history) > MAX_CONTEXT_MESSAGES:
        history = history[-MAX_CONTEXT_MESSAGES:]

    original_chars = sum(len(str(getattr(item, "content", "") or "")) for item in history)
    history = _trim_history_to_char_budget(history, MAX_CONTEXT_CHARS)

    if original_message_count > len(history) or original_chars > MAX_CONTEXT_CHARS:
        logger.info(
            "Conversation context trimmed",
            extra={
                "event": "context.trimmed",
                "original_message_count": original_message_count,
                "retained_message_count": len(history),
                "original_chars_after_message_trim": original_chars,
                "retained_chars": sum(
                    len(str(getattr(item, "content", "") or "")) for item in history
                ),
                "max_messages": MAX_CONTEXT_MESSAGES,
                "max_chars": MAX_CONTEXT_CHARS,
            },
        )

    context_req.conversation_history = history
    return context_req


def _copy_history_item_with_content(item, content: str):
    model_copy = getattr(item, "model_copy", None)
    if callable(model_copy):
        return model_copy(update={"content": content})
    copy = replace(item)
    copy.content = content
    return copy


def _trim_history_to_char_budget(history, max_chars: int):
    """Keep newest context first and truncate only when needed."""
    if max_chars <= 0:
        return []

    retained_reversed = []
    used_chars = 0
    for item in reversed(history):
        content = str(getattr(item, "content", "") or "")
        if not content:
            continue

        remaining = max_chars - used_chars
        if remaining <= 0:
            break

        if len(content) > remaining:
            content = content[:remaining].rstrip()

        if content:
            retained_reversed.append(_copy_history_item_with_content(item, content))
            used_chars += len(content)

    return list(reversed(retained_reversed))


def clamp_max_tokens(max_tokens):
    """Clamp max_tokens to prevent excessive output."""
    if max_tokens is None:
        return None
    return min(max_tokens, MAX_OUTPUT_TOKENS)


def effective_output_token_limit(max_tokens: int | None) -> int:
    """Return the exact output limit shared by execution and billing."""

    if max_tokens is None:
        return MAX_OUTPUT_TOKENS
    if isinstance(max_tokens, bool) or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    return min(int(max_tokens), MAX_OUTPUT_TOKENS)


def redact_sensitive_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """
    Redact auth-bearing headers before logging.
    """
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS and value:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def _extract_status_code(message: str) -> int | None:
    match = re.search(r"\b(400|401|403|408|429|500|502|503|504)\b", message or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _infer_provider_error_kind(error: NormalizedError) -> str | None:
    details = error.details if isinstance(error.details, dict) else {}
    explicit_kind = str(details.get("kind") or details.get("error_kind") or "").strip().lower()
    if explicit_kind:
        return explicit_kind

    message = str(error.message or "").strip().lower()
    status_code = _extract_status_code(message)

    if error.code == "timeout" or status_code in {408, 504}:
        return "timeout"

    if error.code == "auth":
        return "auth" if _looks_like_raw_provider_error(message) else None

    quota_phrases = (
        "insufficient quota",
        "quota exceeded",
        "exceeded your current quota",
        "billing",
        "hard limit",
    )
    if any(phrase in message for phrase in quota_phrases):
        return "quota_exceeded"

    if (
        error.code == "rate_limit"
        or status_code == 429
        or "rate limit" in message
        or "too many requests" in message
        or "resource exhausted" in message
    ):
        return "rate_limited"

    if error.code == "bad_request":
        return "bad_request" if _looks_like_raw_provider_error(message) else None

    transient_phrases = (
        "circuit open",
        "high demand",
        "overloaded",
        "temporarily busy",
        "temporarily unavailable",
        "temporary unavailable",
        "service unavailable",
        "currently unavailable",
        "currently experiencing",
        "try again later",
        "server busy",
        "capacity",
        "unavailable",
    )
    if status_code == 503 or any(phrase in message for phrase in transient_phrases):
        return "transient_capacity"

    if status_code in {500, 502, 504} or "server error" in message:
        return "provider_5xx"

    if error.code == "unknown" and _looks_like_raw_provider_error(message):
        return "unknown"

    return None


def _looks_like_raw_provider_error(message: str) -> bool:
    lowered = str(message or "").lower()
    raw_markers = (
        "provider error:",
        "error code:",
        "http ",
        "{'error'",
        '"error"',
        "traceback",
        "exception",
        "authentication failed",
        "api key",
        "bad request",
        "invalid request",
        "unavailable",
        "too many requests",
        "rate limit",
        "timed out",
    )
    return any(marker in lowered for marker in raw_markers)


def get_client_safe_provider_error_message(error: NormalizedError) -> str:
    """
    Convert provider-native failure text into stable, user-facing copy.

    The detailed provider payload stays out of API/UI/history surfaces while
    `error.details.kind` remains available for telemetry and targeted UI behavior.
    """
    kind = _infer_provider_error_kind(error)
    if kind and kind in CLIENT_SAFE_PROVIDER_ERROR_MESSAGES:
        return CLIENT_SAFE_PROVIDER_ERROR_MESSAGES[kind]
    return str(error.message or "")


def get_client_safe_error_display_text(error: NormalizedError) -> str:
    """Format an error for response-card stream text."""
    message = get_client_safe_provider_error_message(error).strip() or "Request failed."
    kind = _infer_provider_error_kind(error)
    if kind == "transient_capacity":
        return message
    return f"Error: {message}"


def sanitize_provider_error_response(response: UnifiedResponse) -> UnifiedResponse:
    """Return a copy with client-safe provider error text when needed."""
    if not response.is_error or not response.error:
        return response

    kind = _infer_provider_error_kind(response.error)
    if not kind:
        return response

    safe_message = CLIENT_SAFE_PROVIDER_ERROR_MESSAGES.get(kind)
    if not safe_message or safe_message == response.error.message:
        return response

    details = dict(response.error.details or {})
    details.setdefault("kind", kind)
    details["client_safe"] = True

    return replace(
        response,
        error=NormalizedError(
            code=response.error.code,
            message=safe_message,
            provider=response.error.provider,
            retryable=response.error.retryable,
            details=details,
        ),
    )


def normalize_empty_success_response(response: UnifiedResponse) -> UnifiedResponse:
    """
    Transport-level safeguard against blank successful payloads.

    Orchestrator normally normalizes empty-success responses already, but
    API routes should still protect the DTO/stream contract as a last resort.
    """
    if response.is_error:
        return response

    text_value = str(response.text or "")
    if text_value.strip():
        return response

    finish_reason = str(response.finish_reason or "").strip().lower()
    blocked_by_filter = finish_reason == "content_filter"
    message = (
        "Provider returned no text because content was filtered."
        if blocked_by_filter
        else "Provider returned an empty response."
    )
    retryable = not blocked_by_filter

    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    details: dict[str, str] = {}
    if response.finish_reason:
        details["finish_reason"] = str(response.finish_reason)
    provider_finish_reason = metadata.get("provider_finish_reason")
    if provider_finish_reason:
        details["provider_finish_reason"] = str(provider_finish_reason)
    endpoint = metadata.get("endpoint")
    if endpoint:
        details["endpoint"] = str(endpoint)

    return replace(
        response,
        text="",
        finish_reason="error",
        error=NormalizedError(
            code="provider_error",
            message=message,
            provider=response.provider,
            retryable=retryable,
            details=details,
        ),
    )
