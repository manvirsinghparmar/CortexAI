"""Shared helpers for session-scoped route authorization."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger

from fastapi import HTTPException, status

from server.dependencies import AuthResult


def auth_mode(auth: AuthResult) -> str:
    """Return a compact auth-mode label for logs."""
    if auth.user_id is not None:
        return "session_cookie"
    if auth.is_cognito:
        return "cognito"
    if auth.api_key_or_none():
        return "api_key"
    return "unknown"


@dataclass(frozen=True)
class SessionScopedAuthGuard:
    """Reusable guard for routes that require identity-backed session auth."""

    route_label: str
    rejection_event: str
    logger: Logger
    log_message: str | None = None

    def require(self, *, auth: AuthResult, request_id: str) -> None:
        if auth.user_id is not None or auth.is_cognito:
            return

        self.logger.warning(
            self.log_message or f"{self.route_label} route rejected non-session auth",
            extra={
                "extra_fields": {
                    "event": self.rejection_event,
                    "request_id": request_id,
                    "auth_mode": auth_mode(auth),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "session_auth_required",
                "message": (
                    f"{self.route_label} routes require session-based auth "
                    "(cortex_session cookie or Authorization: Bearer)."
                ),
            },
        )
