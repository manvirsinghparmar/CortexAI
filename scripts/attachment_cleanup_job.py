#!/usr/bin/env python3
"""Run attachment retention cleanup (expiry enqueue + deletion queue processing)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.attachment_cleanup import run_cleanup_cycle  # noqa: E402


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run attachment cleanup cycle(s).",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously instead of one cycle.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Sleep interval between loop cycles (default: 60).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max rows/jobs per cycle step.",
    )
    return parser.parse_args(argv)


def _load_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


def _run_once(limit: int) -> dict:
    summary = run_cleanup_cycle(
        now_utc=datetime.now(timezone.utc),
        limit=limit,
    )
    print(json.dumps(summary, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    _load_env()
    args = parse_args(argv)

    if not _env_bool("ENABLE_ATTACHMENTS", default=False):
        print('{"skipped":"attachments_disabled"}')
        return 0

    if not args.loop:
        _run_once(limit=args.limit)
        return 0

    interval = max(1, int(args.interval_seconds))
    while True:
        _run_once(limit=args.limit)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
