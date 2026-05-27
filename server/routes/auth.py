"""Auth-related endpoints (Cognito config + cookie login + code callback)."""

import hmac
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from db import get_or_create_cli_user, get_or_create_user_by_cognito
from db.tables import get_table
from server.cognito import (
    exchange_code_for_tokens,
    get_cognito_authorize_url,
    get_cognito_config_for_frontend,
    cognito_enabled,
    verify_cognito_id_token,
)
from server.session_auth import SESSION_COOKIE_NAME, sign_session
from server.dependencies import get_session_user_id
from server.persistence import db_uow
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["Auth"])
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


def _dev_login_enabled() -> bool:
    return _env_bool("ENABLE_DEV_SESSION_LOGIN", default=False)


def _ensure_dev_login_allowed(request: Request) -> None:
    if not _dev_login_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    runtime_env = _runtime_environment()
    if runtime_env in PRODUCTION_ENV_VALUES:
        logger.warning(
            "Dev session login blocked in production runtime",
            extra={
                "extra_fields": {
                    "event": "auth.dev_login.blocked.production",
                    "runtime_env": runtime_env,
                    "path": str(request.url.path),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev session login is disabled in production environments",
        )

    expected_token = str(os.getenv("DEV_SESSION_LOGIN_TOKEN", "") or "").strip()
    if not expected_token:
        return
    provided = str(request.headers.get("X-Dev-Login-Token") or "")
    if not hmac.compare_digest(provided, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dev login token",
        )


@router.get("/cognito-config")
async def cognito_config():
    """
    Return public Cognito configuration for frontend (no auth required).
    Used to bootstrap Hosted UI or Amplify Auth (e.g. Sign in with Google).
    """
    return get_cognito_config_for_frontend()


def _redirect_uri_from_request(request: Request) -> str:
    """Build callback URL for Cognito (must match app client allowed callback). Uses request path so /auth and /v1/auth/callback both work."""
    configured = (os.getenv("COGNITO_REDIRECT_URI") or "").strip()
    if configured:
        return configured.rstrip("/")
    base = str(request.base_url).rstrip("/")
    path = (request.scope.get("path") or "/v1/auth/callback").strip() or "/v1/auth/callback"
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def _with_query_param(url: str, key: str, value: str) -> str:
    """Return URL with a single query parameter added or replaced."""
    parts = urlsplit(url)
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    pairs.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


async def handle_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
) -> RedirectResponse:
    """
    Shared OAuth2 code callback: exchange code for tokens, verify user,
    set session cookie, redirect to index.html. On failure redirect to Cognito login.
    Used by both GET /auth and GET /v1/auth/callback.
    """
    redirect_uri = _redirect_uri_from_request(request)
    login_url = get_cognito_authorize_url(redirect_uri)
    if not cognito_enabled() or not login_url:
        return RedirectResponse(url="/index.html", status_code=status.HTTP_302_FOUND)

    if not code or not code.strip():
        return RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)

    tokens = exchange_code_for_tokens(code.strip(), redirect_uri)
   
    if not tokens or not tokens.get("id_token"):
        return RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)
    
    claims = verify_cognito_id_token(tokens["id_token"])
    if not claims:
        return RedirectResponse(url=login_url, status_code=status.HTTP_302_FOUND)

    with db_uow() as session:
        user_id: UUID = get_or_create_user_by_cognito(
            session,
            sub=claims.sub,
            email=claims.email,
            issuer=claims.iss,
        )

    cookie_val = sign_session(user_id)
    success_url = _with_query_param(
        (os.getenv("COGNITO_SUCCESS_REDIRECT_URI") or "").strip() or "/index.html",
        "fresh_login",
        "1",
    )
    redir = RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)
    redir.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_val,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return redir


@router.post("/dev-login")
async def dev_login(request: Request, response: Response) -> dict:
    """
    Local-development helper: create a deterministic dev user and set session cookie.
    Disabled by default and blocked in production-like runtimes.
    """
    _ensure_dev_login_allowed(request)

    with db_uow() as session:
        user_id: UUID = get_or_create_cli_user(session)
        users = get_table("users")
        row = session.execute(
            select(users.c.email, users.c.display_name).where(users.c.id == user_id)
        ).first()
        email = row[0] if row else "cli@cortexai.local"
        display_name = row[1] if row else "CLI User"

    cookie_val = sign_session(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_val,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    logger.info(
        "Dev session login completed",
        extra={
            "extra_fields": {
                "event": "auth.dev_login.success",
                "user_id": str(user_id),
                "email": email,
            }
        },
    )
    return {
        "ok": True,
        "user_id": str(user_id),
        "email": email,
        "display_name": display_name,
    }


@router.get("/callback")
async def auth_callback(
    request: Request,
    response: Response,
    code: str | None = None,
):
    """OAuth2 authorization code callback at /v1/auth/callback."""
    return await handle_oauth_callback(request, response, code)


class LoginRequest(BaseModel):
    id_token: str


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> dict:
    """
    Verify Cognito ID token, upsert user in DB, and set a signed session cookie.
    """
    claims = verify_cognito_id_token(body.id_token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired ID token",
        )

    # Upsert user via Cognito identity
    with db_uow() as session:
        user_id: UUID = get_or_create_user_by_cognito(
            session,
            sub=claims.sub,
            email=claims.email,
            issuer=claims.iss,
        )

    # Set cookie
    cookie_val = sign_session(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_val,
        httponly=True,
        secure=False,  # set True behind HTTPS in production
        samesite="lax",
        path="/",
    )

    logger.info("User logged in via Cognito", extra={"extra_fields": {"user_id": str(user_id)}})

    return {
        "user_id": str(user_id),
        "email": claims.email,
        "email_verified": claims.email_verified,
    }


@router.post("/logout")
async def logout(response: Response) -> dict:
    """
    Clear the session cookie (local logout).
    """
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user_id: UUID = Depends(get_session_user_id)) -> dict:
    """
    Return basic user info for the current session.
    """
    with db_uow(commit_on_success=False) as session:
        users = get_table("users")
        row = session.execute(
            select(users.c.email, users.c.display_name).where(users.c.id == user_id)
        ).first()

    email = row[0] if row else None
    display_name = row[1] if row else None

    return {
        "user_id": str(user_id),
        "email": email,
        "display_name": display_name,
    }

