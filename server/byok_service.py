"""BYOK management with encrypted-at-rest provider credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from config.provider_catalog import get_byok_supported_providers
from db import (
    delete_byok_provider_keys,
    get_api_key_settings,
    list_byok_provider_keys,
    upsert_api_key_settings,
    upsert_byok_provider_key,
)
from utils.logger import get_logger

logger = get_logger(__name__)

ALLOWED_PROVIDERS = set(get_byok_supported_providers())
ENC_VERSION = "v1"


def _normalize_provider(provider: str) -> str:
    return (provider or "").strip().lower()


def validate_provider(provider: str) -> str:
    normalized = _normalize_provider(provider)
    if normalized not in ALLOWED_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'")
    return normalized


def _master_key_bytes(required: bool = True) -> bytes | None:
    master_key = os.getenv("MASTER_KEY", "")
    if not master_key.strip():
        if required:
            raise ValueError("MASTER_KEY environment variable is required for BYOK")
        return None
    return hashlib.sha256(master_key.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        block = hmac.new(
            key,
            nonce + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:length])


def encrypt_secret(raw_secret: str) -> str:
    key = _master_key_bytes(required=True)
    assert key is not None
    plaintext = raw_secret.encode("utf-8")
    nonce = secrets.token_bytes(16)
    stream = _keystream(key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))
    tag = hmac.new(key, b"tag:" + nonce + ciphertext, hashlib.sha256).digest()
    payload = base64.urlsafe_b64encode(nonce + ciphertext + tag).decode("ascii")
    return f"{ENC_VERSION}:{payload}"


def decrypt_secret(token: str) -> str:
    key = _master_key_bytes(required=True)
    assert key is not None
    if not token or ":" not in token:
        raise ValueError("Invalid encrypted secret format")
    version, payload = token.split(":", 1)
    if version != ENC_VERSION:
        raise ValueError(f"Unsupported encrypted secret version '{version}'")
    raw = base64.urlsafe_b64decode(payload.encode("ascii"))
    if len(raw) < 16 + 32:
        raise ValueError("Encrypted secret payload too short")
    nonce = raw[:16]
    tag = raw[-32:]
    ciphertext = raw[16:-32]
    expected = hmac.new(key, b"tag:" + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("Encrypted secret authentication failed")
    stream = _keystream(key, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream, strict=True))
    return plaintext.decode("utf-8")


def key_fingerprint(raw_secret: str) -> str:
    return hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()


def set_byok_keys(
    db_session: Session,
    *,
    api_key_id: UUID,
    provider_keys: dict[str, str],
    baseline_provider: str | None = None,
    baseline_model: str | None = None,
    requests_per_minute: int | None = None,
) -> list[str]:
    if (
        not provider_keys
        and baseline_provider is None
        and baseline_model is None
        and requests_per_minute is None
    ):
        return []

    _master_key_bytes(required=True)

    updated: list[str] = []
    for provider, raw_secret in provider_keys.items():
        provider_norm = validate_provider(provider)
        if not raw_secret or not str(raw_secret).strip():
            raise ValueError(f"Missing secret for provider '{provider_norm}'")
        raw_secret = str(raw_secret).strip()
        encrypted = encrypt_secret(raw_secret)
        fingerprint = key_fingerprint(raw_secret)
        upsert_byok_provider_key(
            db_session,
            api_key_id=api_key_id,
            provider=provider_norm,
            encrypted_key=encrypted,
            key_fingerprint=fingerprint,
            key_last4=raw_secret[-4:],
        )
        updated.append(provider_norm)

    if (
        baseline_provider is not None
        or baseline_model is not None
        or requests_per_minute is not None
    ):
        baseline_provider_norm = validate_provider(baseline_provider) if baseline_provider else None
        upsert_api_key_settings(
            db_session,
            api_key_id=api_key_id,
            baseline_provider=baseline_provider_norm,
            baseline_model=baseline_model,
            requests_per_minute=requests_per_minute,
        )

    return sorted(set(updated))


def get_byok_status(
    db_session: Session,
    *,
    api_key_id: UUID,
) -> dict:
    rows = list_byok_provider_keys(db_session, api_key_id=api_key_id)
    providers = []
    for row in rows:
        providers.append(
            {
                "provider": str(row.get("provider") or ""),
                "configured": True,
                "key_last4": row.get("key_last4"),
                "fingerprint_prefix": str(row.get("key_fingerprint") or "")[:12],
                "updated_at": (
                    str(row.get("updated_at")) if row.get("updated_at") is not None else None
                ),
            }
        )

    settings = get_api_key_settings(db_session, api_key_id)
    baseline_provider = None
    baseline_model = None
    requests_per_minute = None
    if settings:
        baseline_provider = settings.get("baseline_provider")
        baseline_model = settings.get("baseline_model")
        requests_per_minute = settings.get("requests_per_minute")

    return {
        "providers": providers,
        "baseline_provider": baseline_provider,
        "baseline_model": baseline_model,
        "requests_per_minute": requests_per_minute,
    }


def delete_byok(
    db_session: Session,
    *,
    api_key_id: UUID,
    provider: str | None = None,
) -> int:
    provider_norm = validate_provider(provider) if provider else None
    return delete_byok_provider_keys(
        db_session,
        api_key_id=api_key_id,
        provider=provider_norm,
    )


def resolve_provider_api_keys(
    db_session: Session,
    *,
    api_key_id: UUID | None,
    providers: Iterable[str] | None = None,
) -> dict[str, str]:
    """
    Resolve decrypted BYOK provider keys for runtime use.

    If MASTER_KEY is not configured or key decryption fails, provider keys are skipped
    and the caller can fall back to environment keys.
    """
    if api_key_id is None:
        return {}

    wanted = None
    if providers is not None:
        wanted = {validate_provider(provider) for provider in providers if provider}

    rows = list_byok_provider_keys(db_session, api_key_id=api_key_id)
    if not rows:
        return {}

    if _master_key_bytes(required=False) is None:
        logger.warning("BYOK rows exist but MASTER_KEY is not configured; ignoring BYOK at runtime")
        return {}

    resolved: dict[str, str] = {}
    for row in rows:
        provider = str(row.get("provider") or "").strip().lower()
        if not provider or provider not in ALLOWED_PROVIDERS:
            continue
        if wanted is not None and provider not in wanted:
            continue

        encrypted = row.get("encrypted_key")
        if not encrypted:
            continue
        try:
            resolved[provider] = decrypt_secret(str(encrypted))
        except Exception:
            logger.exception(
                "Failed to decrypt BYOK provider key",
                extra={"extra_fields": {"provider": provider}},
            )
            continue

    return resolved
