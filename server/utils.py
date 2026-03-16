"""Shared utilities for FastAPI routes."""

from dataclasses import replace
from collections.abc import Mapping

from fastapi import HTTPException, status

from models.unified_response import NormalizedError, UnifiedResponse

MAX_CONTEXT_MESSAGES = 10
MAX_CONTEXT_CHARS = 20000
MAX_OUTPUT_TOKENS = 2048
SENSITIVE_HEADERS = {"x-api-key", "authorization"}


def validate_and_trim_context(context_req):
    """Validate and trim conversation history to prevent token explosion."""
    if not context_req or not context_req.conversation_history:
        return context_req

    history = context_req.conversation_history

    # Trim to last N messages
    if len(history) > MAX_CONTEXT_MESSAGES:
        history = history[-MAX_CONTEXT_MESSAGES:]

    # Check total character count
    total_chars = sum(len(item.content) for item in history)
    if total_chars > MAX_CONTEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conversation history exceeds {MAX_CONTEXT_CHARS} characters",
        )

    context_req.conversation_history = history
    return context_req


def clamp_max_tokens(max_tokens):
    """Clamp max_tokens to prevent excessive output."""
    if max_tokens is None:
        return None
    return min(max_tokens, MAX_OUTPUT_TOKENS)


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
