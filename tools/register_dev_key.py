"""
Register a deterministic dev API key mapping for local IDE/Postman testing.

Zero-argument usage:
  python tools/register_dev_key.py
  python -m tools.register_dev_key

Environment overrides:
  DEV_TEST_API_KEY            (default: dev-key-1)
  DEV_TEST_API_KEY_LABEL      (default: ide-dev-key)
  API_KEY_FALLBACK_USER_EMAIL (default: api@cortexai.local)
  API_KEY_FALLBACK_USER_NAME  (default: API Service User)
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure repo root is importable when script is executed via path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import (  # noqa: E402
    SessionLocal,
    compute_api_key_hash,
    create_api_key,
    get_or_create_service_user,
)


def main() -> None:
    raw_key = os.getenv("DEV_TEST_API_KEY", "dev-key-1")
    label = os.getenv("DEV_TEST_API_KEY_LABEL", "ide-dev-key")
    email = os.getenv("API_KEY_FALLBACK_USER_EMAIL", "api@cortexai.local")
    name = os.getenv("API_KEY_FALLBACK_USER_NAME", "API Service User")

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL is not set. Configure it in .env before running this script."
        )

    db = SessionLocal()
    try:
        user_id = get_or_create_service_user(db, email=email, display_name=name)
        api_key_id, owner_user_id = create_api_key(
            db,
            user_id=user_id,
            raw_api_key=raw_key,
            label=label,
        )
        key_hash = compute_api_key_hash(raw_key)
        db.commit()

        print("Dev API key registration complete.")
        print(f"user_id: {owner_user_id}")
        print(f"api_key_id: {api_key_id}")
        print(f"label: {label}")
        print(f"key_hash: {key_hash}")
        print()
        print("Use this in Postman:")
        print(f"X-API-Key: {raw_key}")
        print()
        print("Make sure .env has this key in API_KEYS.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
