"""E2E-only helpers that make browser-visible streaming easier to assert.

The production app can stream in very large chunks. For the browser suite we split
responses into smaller pieces and add a small delay so incremental DOM updates are
reliably observable.
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split raw text into smaller visible chunks when a provider returns one giant block."""
    raw = str(text or "")
    if not raw:
        return []
    return [raw[index:index + chunk_size] for index in range(0, len(raw), chunk_size)]


def _patch_streaming_module(module, *, chunk_size: int, line_delay_s: float) -> None:
    """Patch one route module in place without changing shipped app code."""
    original_iter = module._iter_stream_lines

    def patched_iter_stream_lines(text: str):
        raw = str(text or "")
        if not raw:
            return []

        chunks = list(original_iter(raw))
        if len(chunks) <= 1:
            return _chunk_text(raw, chunk_size)

        tuned: list[str] = []
        for chunk in chunks:
            if len(chunk) > chunk_size:
                tuned.extend(_chunk_text(chunk, chunk_size))
            else:
                tuned.append(chunk)
        return tuned

    module._iter_stream_lines = patched_iter_stream_lines
    module.STREAM_LINE_DELAY_S = line_delay_s


def install_stream_tuning() -> None:
    """Apply the stream patch to both chat and compare routes when E2E tuning is enabled."""
    if not _env_bool("E2E_TUNE_STREAMING", default=True):
        return

    chunk_size = max(20, int(str(os.getenv("E2E_STREAM_CHUNK_SIZE", "48") or "48")))
    line_delay_s = max(0.05, float(str(os.getenv("E2E_STREAM_LINE_DELAY_S", "0.15") or "0.15")))

    from server.routes import chat, compare

    _patch_streaming_module(chat, chunk_size=chunk_size, line_delay_s=line_delay_s)
    _patch_streaming_module(compare, chunk_size=chunk_size, line_delay_s=line_delay_s)