"""Shared API key utilities."""

import hashlib
import secrets


def compute_api_key_hash(api_key: str) -> str:
    """Return SHA-256 hex hash for an API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key(prefix: str = "cortex") -> str:
    """Generate a random API key string with prefix."""
    safe_prefix = (prefix or "cortex").strip().lower().replace(" ", "-")
    token = secrets.token_urlsafe(32)
    return f"{safe_prefix}_{token}"
