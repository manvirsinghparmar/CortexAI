#!/usr/bin/env python3
"""FastAPI server entry point for CortexAI."""

import sys

import uvicorn
from dotenv import load_dotenv

from server.runtime_checks import check_claude_runtime

load_dotenv()


def _print_runtime_diagnostics() -> None:
    check = check_claude_runtime()
    print(f"[cortexai] Python interpreter: {sys.executable}")
    if not check.sdk_available:
        print(
            "[cortexai] Claude disabled: anthropic SDK not installed in this interpreter. "
            f"Install with: {sys.executable} -m pip install -r requirements.txt"
        )
    elif not check.api_key_present:
        print(
            "[cortexai] Claude env fallback unavailable: ANTHROPIC_API_KEY is not set "
            "(BYOK keys can still enable Claude per API key)."
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CortexAI FastAPI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()
    _print_runtime_diagnostics()

    uvicorn.run(
        "server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
