"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from server.frontend_runtime_config import render_frontend_runtime_config_js
from server.middleware import RequestIDMiddleware
from server.runtime_checks import check_claude_runtime
from server.routes import (
    admin,
    auth as auth_routes,
    byok,
    catalog,
    chat,
    client_diagnostics,
    compare,
    cortex_analysis,
    files,
    health,
    history,
    optimize,
    reporting,
    whoami,
)

from utils.logger import get_logger

logger = get_logger(__name__)


def _trusted_proxy_ips() -> str:
    """Return comma-separated trusted proxy IP list from env, defaulting to '*' (all).

    In production behind AWS CloudFront or ALB, set TRUSTED_PROXY_IPS to the
    ALB/CloudFront CIDR ranges for tighter security. Accepts '*' to trust all
    upstream IPs (safe when the service is not directly internet-exposed).
    """
    return str(os.getenv("TRUSTED_PROXY_IPS", "*") or "*").strip() or "*"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class NoCacheHTMLStaticFiles(StaticFiles):
    """StaticFiles that forces HTML revalidation.

    A heuristically cached index.html can reference hashed assets deleted by
    the next deploy, leaving users on a broken page until a hard refresh.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["cache-control"] = "no-cache"
        return response


def _resolve_frontend_dir() -> str:
    configured = (os.getenv("FRONTEND_DIR") or "").strip()
    if configured:
        return configured
    root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(root, "frontend-react", "dist")


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except Exception:
        logger.warning("Invalid %s value '%s'; using default %s", name, raw, default)
        return default
    if value <= 0:
        logger.warning("Non-positive %s value '%s'; using default %s", name, raw, default)
        return default
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown logic."""
    cleanup_task: asyncio.Task | None = None
    cleanup_stop_event: asyncio.Event | None = None

    runtime_check = check_claude_runtime()
    logger.info(
        "FastAPI server starting up",
        extra={
            "extra_fields": {
                "python_executable": runtime_check.python_executable,
            }
        },
    )

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. PostgreSQL is the only supported runtime data store."
        )
    if not database_url.startswith(("postgresql://", "postgresql+")):
        if _env_bool("ALLOW_NON_POSTGRES_DATABASE_URL", default=False):
            logger.warning("Non-PostgreSQL DATABASE_URL accepted by ALLOW_NON_POSTGRES_DATABASE_URL")
        else:
            raise RuntimeError(
                "DATABASE_URL must use a PostgreSQL URL "
                "(postgresql:// or postgresql+psycopg://)."
            )

    required_keys = ["API_KEYS"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        logger.warning(f"Missing environment variables: {missing}")

    if not runtime_check.sdk_available:
        logger.warning(
            "Claude SDK is unavailable in current interpreter",
            extra={
                "extra_fields": {
                    "provider": "claude",
                    "sdk_module": runtime_check.sdk_module,
                    "python_executable": runtime_check.python_executable,
                    "install_command": (
                        f"{runtime_check.python_executable} -m pip install -r requirements.txt"
                    ),
                }
            },
        )
    elif not runtime_check.api_key_present:
        logger.warning(
            "Claude environment API key is not configured",
            extra={
                "extra_fields": {
                    "provider": "claude",
                    "api_key_env": runtime_check.api_key_env,
                    "python_executable": runtime_check.python_executable,
                    "note": "BYOK runtime keys can still satisfy Claude requests per API key.",
                }
            },
        )
    else:
        logger.info(
            "Claude runtime readiness check passed",
            extra={
                "extra_fields": {
                    "provider": "claude",
                    "sdk_module": runtime_check.sdk_module,
                    "api_key_env": runtime_check.api_key_env,
                }
            },
        )

    if _env_bool("ENABLE_ATTACHMENTS_CLEANUP_WORKER", default=False):
        from server import attachment_cleanup as attachment_cleanup_service

        interval_seconds = _parse_positive_int_env(
            "ATTACHMENTS_CLEANUP_INTERVAL_SECONDS",
            default=300,
        )
        cleanup_stop_event = asyncio.Event()

        async def _cleanup_loop():
            while not cleanup_stop_event.is_set():
                try:
                    stats = await asyncio.to_thread(attachment_cleanup_service.run_cleanup_cycle)
                    logger.info(
                        "Attachment cleanup cycle completed",
                        extra={"extra_fields": {"stats": stats}},
                    )
                except Exception:
                    logger.exception("Attachment cleanup cycle failed")

                try:
                    await asyncio.wait_for(cleanup_stop_event.wait(), timeout=interval_seconds)
                except TimeoutError:
                    continue

        cleanup_task = asyncio.create_task(_cleanup_loop(), name="attachment-cleanup-worker")
        logger.info(
            "Attachment cleanup worker started",
            extra={"extra_fields": {"interval_seconds": interval_seconds}},
        )

    yield

    if cleanup_stop_event is not None:
        cleanup_stop_event.set()
    if cleanup_task is not None:
        try:
            await asyncio.wait_for(cleanup_task, timeout=5)
        except Exception:
            cleanup_task.cancel()

    logger.info("FastAPI server shutting down")


def create_app() -> FastAPI:
    """Factory function to create FastAPI application."""
    app = FastAPI(
        title="CortexAI API",
        description="Unified API for multiple AI providers",
        version="1.0.0",
        lifespan=lifespan
    )

    # Proxy headers middleware must be outermost so that downstream middleware
    # and route handlers see the correct scheme/host when behind AWS CloudFront
    # or an ALB.  Without this, request.base_url resolves to http:// even on
    # HTTPS deployments, which breaks Cognito redirect_uri construction and
    # causes a login redirect loop that looks like an automatic page refresh.
    #
    # Control trusted upstream IPs via TRUSTED_PROXY_IPS env var (default "*").
    # For direct-internet deployments (no proxy), set ENABLE_PROXY_HEADERS=false.
    if _env_bool("ENABLE_PROXY_HEADERS", default=True):
        try:
            from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
            trusted = _trusted_proxy_ips()
            app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)
            logger.info(
                "ProxyHeadersMiddleware enabled",
                extra={"extra_fields": {"trusted_proxy_ips": trusted}},
            )
        except ImportError:
            logger.warning(
                "uvicorn.middleware.proxy_headers not available; "
                "X-Forwarded-Proto/Host headers will not be trusted. "
                "Cognito redirect_uri may be wrong in HTTPS deployments."
            )

    app.add_middleware(RequestIDMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes - registered first so /v1/* takes precedence over static files
    app.include_router(health.router)
    # Cognito callback at /auth (when app client callback URL is e.g. .../auth)
    @app.get("/auth")
    async def auth_callback(request: Request, response: Response, code: str | None = None):
        return await auth_routes.handle_oauth_callback(request, response, code)
    app.include_router(auth_routes.router)
    app.include_router(chat.router)
    app.include_router(client_diagnostics.router)
    app.include_router(compare.router)
    app.include_router(cortex_analysis.router)
    app.include_router(optimize.router)
    app.include_router(history.router)
    app.include_router(admin.router)
    app.include_router(reporting.router)
    app.include_router(byok.router)
    app.include_router(whoami.router)
    app.include_router(catalog.router)
    app.include_router(files.router)

    @app.get("/runtime-config.js", include_in_schema=False)
    async def frontend_runtime_config(request: Request):
        return render_frontend_runtime_config_js(request)

    # Optional static frontend mount for monolith mode.
    serve_frontend = _env_bool("SERVE_FRONTEND", default=True)
    frontend_dir = _resolve_frontend_dir()
    if serve_frontend and os.path.isdir(frontend_dir):
        app.mount("/", NoCacheHTMLStaticFiles(directory=frontend_dir, html=True), name="frontend")
    elif serve_frontend:
        logger.warning(f"Frontend directory not found at {frontend_dir}; skipping static mount")
    else:
        logger.info("SERVE_FRONTEND=false; static frontend mount disabled")

    return app

