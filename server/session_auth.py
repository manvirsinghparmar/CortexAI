"""Helpers for cookie-based user sessions."""

import base64
import hashlib
import hmac
import os
from uuid import UUID

SESSION_COOKIE_NAME = "cortex_session"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret")


def sign_session(user_id: UUID) -> str:
    """Create a signed session token for the given user_id."""
    raw = str(user_id).encode("utf-8")
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw + b"." + sig).decode("ascii")


def parse_session(cookie_value: str | None) -> UUID | None:
    """Validate a session cookie and return user_id when valid, else None."""
    if not cookie_value:
        return None
    try:
        data = base64.urlsafe_b64decode(cookie_value.encode("ascii"))
        user_bytes, sig = data.split(b".", 1)
        expected = hmac.new(SESSION_SECRET.encode("utf-8"), user_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        return UUID(user_bytes.decode("utf-8"))
    except Exception:
        return None

