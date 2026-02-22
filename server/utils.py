"""Shared utilities for FastAPI routes."""

from collections.abc import Mapping

from fastapi import HTTPException, status

MAX_CONTEXT_MESSAGES = 10
MAX_CONTEXT_CHARS = 8000
MAX_OUTPUT_TOKENS = 1024
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
