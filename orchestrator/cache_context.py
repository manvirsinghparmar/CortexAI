"""Provider-neutral, privacy-safe prompt-cache affinity context."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Iterable, Mapping, Any

from config.cache_optimization import CORTEX_PROMPT_STRUCTURE_VERSION


@dataclass(frozen=True)
class CacheContext:
    enabled: bool = False
    cache_scope_key: str = ""
    stable_prefix_version: str = CORTEX_PROMPT_STRUCTURE_VERSION
    retention_policy: str = "ephemeral"
    stable_context_hash: str = ""


def stable_context_digest(messages: Iterable[Mapping[str, Any]]) -> str:
    """Hash reusable context without retaining or logging its contents."""

    digest = hashlib.sha256()
    for message in messages:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        # The final user message is intentionally excluded from stable-prefix
        # affinity; attachments and earlier turns still influence the digest.
        digest.update(role.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def build_cache_context(
    *,
    scope_id: str,
    provider: str,
    model: str,
    mode: str,
    stable_context_hash: str,
    stable_prefix_version: str = CORTEX_PROMPT_STRUCTURE_VERSION,
    retention_policy: str = "ephemeral",
    secret: str | None = None,
) -> CacheContext:
    """Create an opaque HMAC cache key, or disable caching when unsafe."""

    secret_value = str(secret if secret is not None else os.getenv("CACHE_KEY_SECRET", ""))
    normalized_scope = str(scope_id or "").strip()
    if not secret_value or not normalized_scope:
        return CacheContext(
            enabled=False,
            stable_prefix_version=stable_prefix_version,
            retention_policy=retention_policy,
            stable_context_hash=stable_context_hash,
        )
    material = "\n".join(
        (
            normalized_scope,
            str(provider or "").strip().lower(),
            str(model or "").strip(),
            str(mode or "").strip().lower(),
            str(stable_context_hash or "").strip().lower(),
            stable_prefix_version,
        )
    )
    value = hmac.new(
        secret_value.encode("utf-8"),
        material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return CacheContext(
        enabled=True,
        cache_scope_key=f"cortex_pc_{value}",
        stable_prefix_version=stable_prefix_version,
        retention_policy=retention_policy,
        stable_context_hash=str(stable_context_hash or ""),
    )
