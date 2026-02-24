"""Privacy and storage policy helpers for DB persistence."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import replace
from typing import Any

from models.unified_response import NormalizedError, UnifiedResponse

EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"
)
CARDISH_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_metadata_only() -> bool:
    policy = (os.getenv("STORAGE_POLICY", "") or "").strip().lower()
    if policy in {"metadata", "metadata_only"}:
        return True
    if policy in {"full", "store_full"}:
        return False

    # Enterprise-safe default: metadata-only when no explicit storage policy is provided.
    if os.getenv("METADATA_ONLY") is None:
        return True
    return env_bool("METADATA_ONLY", default=True)


def redact_pii_enabled() -> bool:
    return env_bool("REDACT_PII", default=False)


def text_sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        checksum += value
    return checksum % 10 == 0


def redact_pii_text(value: str) -> str:
    """Basic PII redaction for email/phone/credit card patterns."""
    if not value:
        return value

    redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)

    def _replace_card(match: re.Match) -> str:
        token = match.group(0)
        digits = re.sub(r"\D", "", token)
        if _luhn_ok(digits):
            return "[REDACTED_CARD]"
        return token

    redacted = CARDISH_RE.sub(_replace_card, redacted)
    return redacted


def sanitize_user_message_for_storage(prompt: str) -> str:
    if is_metadata_only():
        return f"[metadata-only prompt sha256={text_sha256(prompt)}]"
    if redact_pii_enabled():
        return redact_pii_text(prompt)
    return prompt


def sanitize_assistant_message_for_storage(text: str) -> str:
    if is_metadata_only():
        return f"[metadata-only response sha256={text_sha256(text)}]"
    if redact_pii_enabled():
        return redact_pii_text(text)
    return text


def sanitize_error_message_for_storage(message: str | None) -> str | None:
    if not message:
        return message
    if redact_pii_enabled():
        return redact_pii_text(message)
    return message


def sanitize_response_for_storage(response: UnifiedResponse) -> UnifiedResponse:
    """Apply storage policy/redaction rules to UnifiedResponse persistence payload."""
    text = response.text
    if is_metadata_only():
        text = ""
    elif redact_pii_enabled():
        text = redact_pii_text(text)

    error = response.error
    if error is not None:
        sanitized_message = sanitize_error_message_for_storage(error.message)
        if sanitized_message != error.message:
            error = NormalizedError(
                code=error.code,
                message=sanitized_message or "",
                provider=error.provider,
                retryable=error.retryable,
                details=error.details or {},
            )

    return replace(response, text=text, error=error)


def _redact_nested(value: Any) -> Any:
    if isinstance(value, str):
        return redact_pii_text(value)
    if isinstance(value, dict):
        return {k: _redact_nested(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_nested(item) for item in value]
    return value


def sanitize_routing_payload_for_storage(
    routing_metadata: dict[str, Any],
    attempts: list[dict[str, Any]],
    features: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """
    Sanitize routing telemetry before persistence.

    In metadata-only mode, store only non-content routing fields.
    """
    if is_metadata_only():
        base: dict[str, Any] = {
            "mode": routing_metadata.get("mode"),
            "initial_tier": routing_metadata.get("initial_tier"),
            "final_tier": routing_metadata.get("final_tier"),
            "attempt_count": routing_metadata.get("attempt_count"),
            "fallback_used": bool(routing_metadata.get("fallback_used", False)),
        }
        slim_attempts: list[dict[str, Any]] = []
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            slim_attempts.append(
                {
                    "attempt_number": attempt.get("attempt_number"),
                    "tier": attempt.get("tier"),
                    "provider": attempt.get("provider"),
                    "model": attempt.get("model"),
                    "validation": attempt.get("validation"),
                    "latency_ms": attempt.get("latency_ms"),
                    "error_type": attempt.get("error_type"),
                }
            )
        if slim_attempts:
            base["attempts"] = slim_attempts
        return base, slim_attempts, {}

    if redact_pii_enabled():
        safe_routing = _redact_nested(routing_metadata)
        safe_attempts = _redact_nested(attempts)
        safe_features = _redact_nested(features)
        return safe_routing, safe_attempts, safe_features

    return routing_metadata, attempts, features
