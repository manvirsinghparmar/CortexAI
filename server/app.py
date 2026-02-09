"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.middleware import RequestIDMiddleware
from server.routes import chat, compare, health
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown logic."""
    logger.info("FastAPI server starting up")

    required_keys = ["API_KEYS"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        logger.warning(f"Missing environment variables: {missing}")

    yield

    logger.info("FastAPI server shutting down")


def create_app() -> FastAPI:
    """Factory function to create FastAPI application."""
    app = FastAPI(
        title="CortexAI API",
        description="Unified API for multiple AI providers",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIDMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(compare.router)

    return app
