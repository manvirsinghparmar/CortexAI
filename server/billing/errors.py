"""Safe, structured HTTP errors for subscription and entitlement failures."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status


class BillingIdentityError(RuntimeError):
    """The authenticated identity cannot own a billing account."""


class BillingConfigurationError(RuntimeError):
    """Billing persistence or configuration is internally inconsistent."""


class UsageReservationConflictError(RuntimeError):
    """An idempotency key was reused for a different metering operation."""

    code = "usage_reservation_conflict"


class UsageReservationNotFoundError(LookupError):
    """A requested usage reservation does not exist."""

    code = "usage_reservation_not_found"


class UsageReservationStateError(RuntimeError):
    """A terminal reservation cannot perform the requested transition."""

    code = "usage_reservation_state_conflict"


class UsageAllowanceExceededError(RuntimeError):
    """A reservation would exceed one server-owned plan allowance."""

    code = "monthly_allowance_exhausted"

    def __init__(
        self,
        *,
        meter: str,
        requested: int,
        used: int,
        reserved: int,
        limit: int,
        plan_code: str,
        reset_at: datetime,
    ) -> None:
        self.meter = meter
        self.requested = requested
        self.used = used
        self.reserved = reserved
        self.limit = limit
        self.remaining = max(0, limit - used - reserved)
        self.plan_code = plan_code
        self.current_plan = plan_code
        self.reset_at = reset_at
        super().__init__(f"The {plan_code} plan's monthly {meter} allowance has been exhausted.")


_ENTITLEMENT_STATUS_CODES = {
    "feature_not_in_plan": status.HTTP_403_FORBIDDEN,
    "model_not_in_plan": status.HTTP_403_FORBIDDEN,
    "monthly_allowance_exhausted": status.HTTP_429_TOO_MANY_REQUESTS,
    "subscription_payment_required": status.HTTP_402_PAYMENT_REQUIRED,
    "subscription_configuration_error": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def entitlement_http_exception(denial: Any) -> HTTPException:
    """Convert a domain denial to a provider-safe FastAPI error."""
    code = str(getattr(denial, "code", "subscription_configuration_error"))
    detail = {
        "code": code,
        "message": str(
            getattr(
                denial,
                "message",
                "Subscription access could not be evaluated safely.",
            )
        ),
        "feature": getattr(denial, "feature", None),
        "meter": getattr(denial, "meter", None),
        "model": getattr(denial, "model", None),
        "billing_class": getattr(denial, "billing_class", None),
        "current_plan": getattr(denial, "current_plan", None),
        "recommended_plan": getattr(denial, "recommended_plan", None),
        "used": getattr(denial, "used", None),
        "limit": getattr(denial, "limit", None),
        "remaining": getattr(denial, "remaining", None),
        "reset_at": getattr(denial, "reset_at", None),
    }
    return HTTPException(
        status_code=_ENTITLEMENT_STATUS_CODES.get(
            code,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
        detail=detail,
    )


def billing_identity_http_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "billing_identity_not_found",
            "message": "The authenticated user could not be resolved for billing.",
        },
    )


def billing_configuration_http_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "code": "subscription_configuration_error",
            "message": "Subscription access could not be evaluated safely.",
        },
    )


def billing_database_required_http_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "billing_database_required",
            "message": "Subscription entitlements require database-backed runtime mode.",
        },
    )
