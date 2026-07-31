#!/usr/bin/env python3
"""One-command tenant onboarding for CortexAI B2B.

Creates/gets a tenant user, creates/gets an API key mapping, applies baseline
settings, optionally stores BYOK credentials, and prints ready-to-run curl
examples for integration.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import insert, select

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db import (
    SessionLocal,
    create_api_key,
    generate_api_key,
    get_table,
    upsert_api_key_settings,
)
from server import byok_service


def _ensure_database_url() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required for onboarding script")


def _resolve_baseline(
    *,
    baseline_model_id: str | None,
    baseline_provider: str | None,
    baseline_model: str | None,
) -> tuple[str, str]:
    if baseline_model_id:
        raw = baseline_model_id.strip()
        if ":" not in raw:
            raise ValueError("--baseline-model-id must be formatted as provider:model")
        provider, model = raw.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if not provider or not model:
            raise ValueError("--baseline-model-id must be formatted as provider:model")
        return provider, model

    provider = (baseline_provider or os.getenv("BASELINE_PROVIDER") or "").strip().lower()
    model = (baseline_model or os.getenv("BASELINE_MODEL") or "").strip()

    if provider and model:
        return provider, model

    model_id = (os.getenv("BASELINE_MODEL_ID") or "").strip()
    if model_id and ":" in model_id:
        p, m = model_id.split(":", 1)
        p = p.strip().lower()
        m = m.strip()
        if p and m:
            return p, m

    return ("openai", "gpt-4o-mini")


def _tenant_user_auth_subject(email: str) -> str:
    return f"tenant:{email.strip().lower()}"


def _get_or_create_tenant_user(
    db_session,
    *,
    email: str,
    display_name: str,
) -> UUID:
    users = get_table("users")
    stmt = select(users.c.id).where(users.c.email == email)
    existing = db_session.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing

    cols = {col.name for col in users.columns}
    values: dict[str, Any] = {"email": email}
    if "display_name" in cols:
        values["display_name"] = display_name
    if "is_active" in cols:
        values["is_active"] = True
    if "auth_provider" in cols:
        values["auth_provider"] = "tenant"
    if "auth_subject" in cols:
        values["auth_subject"] = _tenant_user_auth_subject(email)
    if "auth_issuer" in cols:
        values["auth_issuer"] = "cortexai"

    stmt = insert(users).values(**values).returning(users.c.id)
    return db_session.execute(stmt).scalar_one()


def _collect_byok_provider_keys(args: argparse.Namespace) -> dict[str, str]:
    provider_keys: dict[str, str] = {}
    if args.byok_openai:
        provider_keys["openai"] = args.byok_openai
    if args.byok_gemini:
        provider_keys["gemini"] = args.byok_gemini
    if args.byok_deepseek:
        provider_keys["deepseek"] = args.byok_deepseek
    if args.byok_grok:
        provider_keys["grok"] = args.byok_grok
    return provider_keys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Onboard one B2B tenant in one command")
    parser.add_argument("--email", required=True, help="Tenant owner email")
    parser.add_argument("--name", default="Startup Tenant", help="Tenant display name")
    parser.add_argument("--label", default="tenant-primary", help="API key label")
    parser.add_argument(
        "--api-key", default=None, help="Explicit API key (optional; generated if omitted)"
    )
    parser.add_argument("--api-key-prefix", default="cortex", help="Prefix for generated API key")

    parser.add_argument(
        "--baseline-model-id", default=None, help="Baseline in provider:model format"
    )
    parser.add_argument("--baseline-provider", default=None, help="Baseline provider")
    parser.add_argument("--baseline-model", default=None, help="Baseline model")
    parser.add_argument("--requests-per-minute", type=int, default=None, help="Tenant RPM override")

    parser.add_argument("--byok-openai", default=None, help="Optional BYOK OpenAI API key")
    parser.add_argument("--byok-gemini", default=None, help="Optional BYOK Gemini API key")
    parser.add_argument("--byok-deepseek", default=None, help="Optional BYOK DeepSeek API key")
    parser.add_argument("--byok-grok", default=None, help="Optional BYOK Grok API key")

    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000", help="Base URL for printed examples"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _ensure_database_url()

    raw_api_key = (args.api_key or "").strip() or generate_api_key(prefix=args.api_key_prefix)
    baseline_provider, baseline_model = _resolve_baseline(
        baseline_model_id=args.baseline_model_id,
        baseline_provider=args.baseline_provider,
        baseline_model=args.baseline_model,
    )

    byok_keys = _collect_byok_provider_keys(args)

    db_session = SessionLocal()
    try:
        user_id = _get_or_create_tenant_user(
            db_session,
            email=args.email,
            display_name=args.name,
        )
        api_key_id, owner_user_id = create_api_key(
            db_session,
            user_id=user_id,
            raw_api_key=raw_api_key,
            label=args.label,
        )

        upsert_api_key_settings(
            db_session,
            api_key_id=api_key_id,
            baseline_provider=baseline_provider,
            baseline_model=baseline_model,
            requests_per_minute=args.requests_per_minute,
        )

        updated_byok: list[str] = []
        if byok_keys:
            updated_byok = byok_service.set_byok_keys(
                db_session,
                api_key_id=api_key_id,
                provider_keys=byok_keys,
                baseline_provider=baseline_provider,
                baseline_model=baseline_model,
                requests_per_minute=args.requests_per_minute,
            )

        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()

    base_url = args.base_url.rstrip("/")

    print("Tenant onboarding complete.")
    print(f"user_id: {owner_user_id}")
    print(f"api_key_id: {api_key_id}")
    print(f"email: {args.email}")
    print(f"label: {args.label}")
    print(f"baseline: {baseline_provider}:{baseline_model}")
    print(
        f"requests_per_minute: {args.requests_per_minute if args.requests_per_minute is not None else '(default)'}"
    )
    print(f"byok_providers: {updated_byok if updated_byok else '[]'}")
    print()
    print("Use this API key header:")
    print(f"X-API-Key: {raw_api_key}")
    print()
    print("Quick curl checks:")
    print(f'curl -H "X-API-Key: {raw_api_key}" {base_url}/v1/whoami')
    print(
        "curl -X POST "
        f"{base_url}/v1/chat "
        f'-H "X-API-Key: {raw_api_key}" '
        '-H "Content-Type: application/json" '
        f'-d \'{{"prompt":"hello from {args.email}","provider":"openai","model":"gpt-4o-mini"}}\''
    )
    print("curl -H " f'"X-API-Key: {raw_api_key}" ' f'"{base_url}/v1/usage?group_by=day"')
    print()
    print("Reminder: ensure API_KEYS in your server environment includes this key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
