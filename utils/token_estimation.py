"""Shared conservative token estimation used by routing and billing."""

from __future__ import annotations

from math import ceil


def estimate_tokens(
    text: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> int:
    """Estimate tokens without requiring provider SDK tokenizers.

    UTF-8 bytes divided by three is deliberately conservative for the mixed
    prose, code, and multilingual inputs accepted by Cortex. Provider/model
    parameters reserve a stable extension point for exact tokenizers.
    """

    del provider, model
    normalized = str(text or "")
    return max(1, ceil(len(normalized.encode("utf-8")) / 3)) if normalized else 0
