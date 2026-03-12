#!/usr/bin/env python3
"""Launch Playwright MCP via npm scripts.

This gives Python-focused IDEs (for example PyCharm Community) a simple
entrypoint that can be run from a regular Python Run Configuration.
"""

from __future__ import annotations

import argparse
import signal
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_BY_MODE = {
    "headed": "mcp",
    "headless": "mcp:headless",
    "sse": "mcp:sse",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Playwright MCP from this repository.",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(SCRIPT_BY_MODE.keys()),
        default="headed",
        help="Select MCP startup mode (default: headed).",
    )
    return parser.parse_args()


def resolve_npm() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise SystemExit(
            "Could not find npm in PATH. Install Node.js or configure PATH, then retry.",
        )
    return npm


def main() -> int:
    args = parse_args()
    npm = resolve_npm()
    script_name = SCRIPT_BY_MODE[args.mode]
    command = [npm, "run", "--prefix", "e2e", script_name]

    print(f"[playwright-mcp] cwd={REPO_ROOT}", flush=True)
    print(f"[playwright-mcp] cmd={' '.join(command)}", flush=True)
    print("[playwright-mcp] Starting server...", flush=True)

    process = subprocess.Popen(command, cwd=str(REPO_ROOT))
    print(
        f"[playwright-mcp] MCP process running (pid={process.pid}). "
        "Play button spinning is expected.",
        flush=True,
    )
    print(
        "[playwright-mcp] Waiting for an MCP client connection. "
        "Stop the run config to exit.",
        flush=True,
    )

    try:
        return int(process.wait())
    except KeyboardInterrupt:
        process.send_signal(signal.SIGINT)
        return int(process.wait())


if __name__ == "__main__":
    sys.exit(main())
