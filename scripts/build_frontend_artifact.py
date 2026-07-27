#!/usr/bin/env python3
"""Build a deployment artifact from the compiled React frontend."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build React frontend static artifact")
    parser.add_argument(
        "--source-dir",
        default="frontend-react/dist",
        help="Compiled React frontend directory (default: frontend-react/dist)",
    )
    parser.add_argument(
        "--output-dir",
        default="dist/frontend-react",
        help="Output directory for built artifact (default: dist/frontend-react)",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_manifest_files(base_dir: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for item in sorted(base_dir.rglob("*")):
        if item.is_dir():
            continue
        rel = item.relative_to(base_dir).as_posix()
        files.append(
            {
                "path": rel,
                "sha256": sha256_file(item),
                "bytes": str(item.stat().st_size),
            }
        )
    return files


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        raise SystemExit(f"Frontend source directory not found: {source_dir}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, output_dir)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "files": collect_manifest_files(output_dir),
    }
    manifest_path = output_dir / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    archive_base = output_dir.parent / "react-frontend-artifact"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=output_dir)

    print(f"Frontend artifact directory: {output_dir}")
    print(f"Frontend artifact manifest:  {manifest_path}")
    print(f"Frontend artifact zip:       {archive_path}")


if __name__ == "__main__":
    main()
