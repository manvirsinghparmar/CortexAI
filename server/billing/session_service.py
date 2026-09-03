"""Checkout and Customer Portal orchestration around short database units of work."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Callable, Literal, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from db.billing_repository import (
    claim_stripe_customer_id,
    get_live_subscription_for_account,
)
from server.billing.account_service import BillingAccount, get_or_create_user_billing_account
from server.billing.errors import (
    BillingConfigurationError,
    BillingPlanSelectionError,
    StripeCustomerRequiredError,
)
from server.billing.plan_catalog import PlanCatalog, get_plan_catalog
from server.billing.stripe_gateway import StripeBillingConfig


class HostedBillingGateway(Protocol):
    async def create_customer(
        self,
        *,
        billing_account_id: UUID,
        user_id: UUID,
        email: str | None,
    ) -> str: ...

    async def create_checkout_session(
        self,
        *,
        billing_account_id: UUID,
        user_id: UUID,
        customer_id: str,
        plan_code: str,
        price_id: str,
        idempotency_key: str,
    ) -> str: ...

    async def create_portal_session(self, *, customer_id: str) -> str: ...


BillingUowFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class BillingSessionRedirect:
    url: str
    destination: Literal["checkout", "portal"]


def _load_account_state(
    uow_factory: BillingUowFactory,
    user_id: UUID,
) -> tuple[BillingAccount, bool]:
    try:
        with uow_factory() as db_session:
            account = get_or_create_user_billing_account(db_session, user_id)
            live_subscription = get_live_subscription_for_account(db_session, account.id)
            return account, live_subscription is not None
    except BillingConfigurationError:
        raise
    except Exception as exc:
        raise BillingConfigurationError("Billing account state could not be loaded") from exc


def _claim_customer(
    uow_factory: BillingUowFactory,
    *,
    account: BillingAccount,
    customer_id: str,
) -> str:
    try:
        with uow_factory() as db_session:
            persisted = claim_stripe_customer_id(db_session, account.id, customer_id)
            if (
                persisted.get("owner_type") != "user"
                or persisted.get("owner_id") != account.owner_id
            ):
                raise BillingConfigurationError("Stripe Customer ownership could not be verified")
            winning_customer_id = str(persisted.get("stripe_customer_id") or "").strip()
            if not winning_customer_id:
                raise BillingConfigurationError("Stripe Customer identity was not persisted")
            return winning_customer_id
    except BillingConfigurationError:
        raise
    except Exception as exc:
        raise BillingConfigurationError("Stripe Customer identity could not be persisted") from exc


async def create_checkout_redirect(
    *,
    uow_factory: BillingUowFactory,
    gateway: HostedBillingGateway,
    config: StripeBillingConfig,
    user_id: UUID,
    plan_code: str,
    billing_period: str,
    catalog: PlanCatalog | None = None,
) -> BillingSessionRedirect:
    plan_catalog = catalog or get_plan_catalog()
    plan = plan_catalog.get(plan_code)
    if plan is None:
        raise BillingPlanSelectionError(
            code="invalid_subscription_plan",
            message="The selected subscription plan is not available.",
        )
    if billing_period != "monthly":
        raise BillingPlanSelectionError(
            code="unsupported_billing_period",
            message="The selected billing period is not supported.",
        )
    if plan.code == "free" or plan.monthly_price_usd <= 0:
        raise BillingPlanSelectionError(
            code="paid_subscription_plan_required",
            message="Checkout requires a paid subscription plan.",
        )

    account, has_live_subscription = _load_account_state(uow_factory, user_id)
    if has_live_subscription:
        if not account.stripe_customer_id:
            raise StripeCustomerRequiredError("Live subscription has no Stripe Customer")
        portal_url = await gateway.create_portal_session(customer_id=account.stripe_customer_id)
        return BillingSessionRedirect(url=portal_url, destination="portal")

    customer_id = account.stripe_customer_id
    if not customer_id:
        created_customer_id = await gateway.create_customer(
            billing_account_id=account.id,
            user_id=user_id,
            email=account.email,
        )
        customer_id = _claim_customer(
            uow_factory,
            account=account,
            customer_id=created_customer_id,
        )

    checkout_url = await gateway.create_checkout_session(
        billing_account_id=account.id,
        user_id=user_id,
        customer_id=customer_id,
        plan_code=plan.code,
        price_id=config.require_price_id(plan.code),
        idempotency_key=(f"cortex-checkout-{account.id}-{plan.code}-{billing_period}"),
    )
    return BillingSessionRedirect(url=checkout_url, destination="checkout")


async def create_portal_redirect(
    *,
    uow_factory: BillingUowFactory,
    gateway: HostedBillingGateway,
    user_id: UUID,
) -> BillingSessionRedirect:
    account, _ = _load_account_state(uow_factory, user_id)
    if not account.stripe_customer_id:
        raise StripeCustomerRequiredError("Billing account has no Stripe Customer")
    portal_url = await gateway.create_portal_session(customer_id=account.stripe_customer_id)
    return BillingSessionRedirect(url=portal_url, destination="portal")
