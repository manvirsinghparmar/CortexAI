"""Billing-account ownership services."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.billing_repository import get_or_create_billing_account_for_user
from server.billing.errors import BillingConfigurationError, BillingIdentityError


@dataclass(frozen=True)
class BillingAccount:
    id: UUID
    owner_type: str
    owner_id: UUID
    stripe_customer_id: str | None
    currency: str
    country: str | None


def get_or_create_user_billing_account(db: Session, user_id: UUID) -> BillingAccount:
    """Validate ownership and lazily create one billing account for a user."""
    from db.tables import get_table

    try:
        users = get_table("users")
        user_exists = db.execute(
            select(users.c.id).where(users.c.id == user_id)
        ).scalar_one_or_none()
        if user_exists is None:
            raise BillingIdentityError("Authenticated user does not exist")

        record = get_or_create_billing_account_for_user(db, user_id)
        return BillingAccount(
            id=record["id"],
            owner_type=str(record["owner_type"]),
            owner_id=record["owner_id"],
            stripe_customer_id=record.get("stripe_customer_id"),
            currency=str(record.get("currency") or "USD"),
            country=record.get("country"),
        )
    except BillingIdentityError:
        raise
    except Exception as exc:
        raise BillingConfigurationError("Billing account could not be resolved") from exc
