#!/usr/bin/env python3
"""Run the CortexAI app with E2E-only bootstrap behavior.

This wrapper loads test-specific env, enables DB-backed API mode, and installs the
E2E-only stream tuning and fault injection hooks before the FastAPI app starts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import uvicorn
from dotenv import load_dotenv


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_env_files() -> None:
    """Load repo-level secrets first, then allow E2E-local env to override where needed."""
    if _env_bool("E2E_LOAD_ROOT_DOTENV", default=True):
        load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(REPO_ROOT / "e2e" / ".env", override=False)
    load_dotenv(REPO_ROOT / "e2e" / ".env.local", override=False)


def _require(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if not value:
        raise SystemExit(f"Missing required E2E environment variable: {name}")
    return value


def _prepare_runtime_env() -> tuple[str, int]:
    """Apply the env switches that make the app behave like the live E2E target."""
    if not _env_bool("E2E_LIVE_ENABLED", default=False):
        raise SystemExit("E2E_LIVE_ENABLED must be true for the E2E server bootstrap.")

    host = str(os.getenv("E2E_HOST", "127.0.0.1") or "127.0.0.1").strip()
    port = int(str(os.getenv("E2E_PORT", "8010") or "8010"))

    os.environ["DATABASE_URL"] = _require("E2E_DATABASE_URL")
    os.environ["API_KEYS"] = _require("E2E_API_KEY")
    os.environ["AUTO_REGISTER_UNMAPPED_API_KEYS"] = "true"
    os.environ.setdefault("SERVE_FRONTEND", "true")

    db_schema = str(os.getenv("E2E_DB_SCHEMA", "") or "").strip()
    if db_schema:
        os.environ["DB_SCHEMA"] = db_schema

    return host, port


def main() -> None:
    _load_env_files()
    host, port = _prepare_runtime_env()

    from e2e.server.fault_injection import install_fault_injection
    from e2e.server.stream_tuning import install_stream_tuning
    from server.app import create_app

    install_stream_tuning()
    app = create_app()
    install_fault_injection(app)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()