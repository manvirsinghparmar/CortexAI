"""
Create and register an API key in public.api_keys for local/dev usage.

Usage:
  python tools/create_api_key.py --email api@cortexai.local --name "API Service User" --label "postman"
  python tools/create_api_key.py --email you@example.com --key "dev-key-1" --label "env-dev-key"
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure repo root is importable when script is executed via path (tools/create_api_key.py).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import (  # noqa: E402
    SessionLocal,
    compute_api_key_hash,
    create_api_key,
    generate_api_key,
    get_or_create_service_user,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/register API key in DB")
    parser.add_argument("--email", default="api@cortexai.local", help="User email to own the key")
    parser.add_argument("--name", default="API Service User", help="Display name for fallback user")
    parser.add_argument("--label", default="dev-key", help="Key label")
    parser.add_argument(
        "--key",
        default=None,
        help="Raw API key to register. If omitted, a new random key is generated.",
    )
    parser.add_argument("--prefix", default="cortex", help="Prefix for generated key")
    args = parser.parse_args()

    raw_key = args.key or generate_api_key(prefix=args.prefix)
    db = SessionLocal()

    try:
        user_id = get_or_create_service_user(db, email=args.email, display_name=args.name)
        api_key_id, owner_user_id = create_api_key(
            db, user_id=user_id, raw_api_key=raw_key, label=args.label
        )
        key_hash = compute_api_key_hash(raw_key)
        db.commit()

        print("API key registered successfully.")
        print(f"user_id: {owner_user_id}")
        print(f"api_key_id: {api_key_id}")
        print(f"label: {args.label}")
        print(f"key_hash: {key_hash}")
        print("\nUse this header in Postman:")
        print(f"X-API-Key: {raw_key}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
