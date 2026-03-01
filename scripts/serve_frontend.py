#!/usr/bin/env python3
"""Serve the frontend as a standalone static component."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve CortexAI frontend as static files")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument(
        "--dir",
        default="frontend",
        help="Frontend directory to serve (default: frontend)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frontend_dir = Path(args.dir).resolve()
    if not frontend_dir.exists() or not frontend_dir.is_dir():
        raise SystemExit(f"Frontend directory not found: {frontend_dir}")

    handler = partial(SimpleHTTPRequestHandler, directory=str(frontend_dir))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Serving frontend from {frontend_dir} at {url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down frontend server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
