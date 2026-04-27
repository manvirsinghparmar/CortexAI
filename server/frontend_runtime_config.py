"""Runtime frontend-config helpers for environment-specific UI behavior."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import Request, Response

PRODUCTION_ENV_VALUES = {"prod", "production"}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _runtime_environment() -> str:
    for key in ("APP_ENV", "ENVIRONMENT", "ENV"):
        value = str(os.getenv(key, "") or "").strip().lower()
        if value:
            return value
    return ""


def _normalize_api_base(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _resolve_request_api_base(request: Request) -> str:
    return _normalize_api_base(str(request.base_url))


def build_frontend_runtime_config(request: Request) -> dict[str, Any]:
    """Build browser runtime config from environment with safe defaults."""
    configured_api_base = _normalize_api_base(os.getenv("FRONTEND_RUNTIME_API_BASE", ""))
    api_base = configured_api_base or _resolve_request_api_base(request)

    runtime_env = _runtime_environment()
    explicit_frontend_dev_login = os.getenv("FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN")
    if explicit_frontend_dev_login is None:
        enable_dev_session_login = _env_bool("ENABLE_DEV_SESSION_LOGIN", default=False)
    else:
        enable_dev_session_login = _env_bool("FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN", default=False)
    if runtime_env in PRODUCTION_ENV_VALUES:
        enable_dev_session_login = False

    payload: dict[str, Any] = {
        "apiBase": api_base,
        "enableDevSessionLogin": bool(enable_dev_session_login),
    }

    frontend_dev_login_token = str(
        os.getenv("FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN", "") or ""
    ).strip()
    if frontend_dev_login_token:
        payload["devSessionLoginToken"] = frontend_dev_login_token

    return payload


def render_frontend_runtime_config_js(request: Request) -> Response:
    """Serialize frontend runtime config as JavaScript."""
    payload = build_frontend_runtime_config(request)
    body = (
        "window.CORTEX_RUNTIME_CONFIG = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    return Response(
        content=body,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )
