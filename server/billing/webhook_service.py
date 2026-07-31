"""Verified, idempotent Stripe webhook lifecycle synchronization."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Literal, Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from db.billing_repository import (
    LIVE_SUBSCRIPTION_STATUSES,
    SubscriptionSnapshot,
    claim_stripe_customer_id,
    create_webhook_event_if_absent,
    get_billing_account_by_id,
    get_billing_account_by_stripe_customer_id,
    get_latest_subscription_for_account,
    get_subscription_by_provider_id,
    lock_webhook_event,
    mark_webhook_event_failed,
    mark_webhook_event_processed,
    upsert_subscription_snapshot,
)
from server.billing.errors import (
    BillingConfigurationError,
    BillingProviderError,
    BillingWebhookProcessingError,
)
from server.billing.plan_catalog import PlanCatalog, get_plan_catalog
from server.billing.stripe_gateway import StripeBillingConfig
from server.billing.subscription_service import (
    resolve_effective_subscription,
    subscription_payment_grace_days,
)
from utils.logger import get_logger

logger = get_logger(__name__)

_REQUIRED_EVENT_TYPES = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.paid",
        "invoice.payment_failed",
    }
)
_TERMINAL_EVENT_STATUSES = frozenset({"processed", "ignored"})

BillingUowFactory = Callable[[], AbstractContextManager[Session]]
NowFactory = Callable[[], datetime]


class StripeWebhookGateway(Protocol):
    def verify_webhook_event(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> Mapping[str, Any]: ...

    async def retrieve_subscription(
        self,
        subscription_id: str,
    ) -> Mapping[str, Any]: ...

    async def list_customer_subscriptions(
        self,
        *,
        customer_id: str,
    ) -> tuple[Mapping[str, Any], ...]: ...


@dataclass(frozen=True)
class WebhookLifecycleResult:
    event_type: str
    outcome: Literal["processed", "ignored", "duplicate", "stale", "reconciled"]


@dataclass(frozen=True)
class _StripeSubscriptionState:
    subscription_id: str
    customer_id: str
    billing_account_id: UUID | None
    price_id: str
    plan_code: str
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None
    trial_end: datetime | None
    latest_invoice_id: str | None


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raise BillingWebhookProcessingError(f"{label} is not an object")


def _text(value: Any, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BillingWebhookProcessingError(f"{label} is missing")
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise BillingWebhookProcessingError(f"{label} is not a boolean")
    return value


def _expandable_id(value: Any, *, prefix: str, label: str) -> str:
    if isinstance(value, Mapping):
        value = value.get("id")
    identifier = _text(value, label)
    if not identifier.startswith(prefix):
        raise BillingWebhookProcessingError(f"{label} is invalid")
    return identifier


def _optional_expandable_id(value: Any, *, prefix: str, label: str) -> str | None:
    if value is None:
        return None
    return _expandable_id(value, prefix=prefix, label=label)


def _timestamp(value: Any, label: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BillingWebhookProcessingError(f"{label} is not a timestamp")
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise BillingWebhookProcessingError(f"{label} is not a valid timestamp") from exc


def _created_sort_key(value: Mapping[str, Any]) -> float:
    created = value.get("created")
    if isinstance(created, (int, float)) and not isinstance(created, bool):
        return float(created)
    return 0.0


def _metadata_account_id(*values: Any) -> UUID | None:
    resolved: UUID | None = None
    for value in values:
        if value is None:
            continue
        if isinstance(value, Mapping):
            value = value.get("cortex_billing_account_id")
        raw = _optional_text(value)
        if raw is None:
            continue
        try:
            candidate = UUID(raw)
        except ValueError as exc:
            raise BillingWebhookProcessingError(
                "Stripe billing-account metadata is invalid"
            ) from exc
        if resolved is not None and resolved != candidate:
            raise BillingWebhookProcessingError("Stripe billing-account references do not match")
        resolved = candidate
    return resolved


def _subscription_item(subscription: Mapping[str, Any]) -> Mapping[str, Any]:
    items = _mapping(subscription.get("items"), "Stripe subscription items")
    data = items.get("data")
    if not isinstance(data, Sequence) or isinstance(data, (str, bytes)) or len(data) != 1:
        raise BillingWebhookProcessingError(
            "Stripe subscription must contain exactly one recurring Price"
        )
    return _mapping(data[0], "Stripe subscription item")


def _parse_subscription_state(
    subscription: Mapping[str, Any],
    *,
    config: StripeBillingConfig,
) -> _StripeSubscriptionState:
    subscription_id = _expandable_id(
        subscription.get("id"), prefix="sub_", label="Stripe Subscription ID"
    )
    customer_id = _expandable_id(
        subscription.get("customer"), prefix="cus_", label="Stripe Customer ID"
    )
    item = _subscription_item(subscription)
    price_id = _expandable_id(item.get("price"), prefix="price_", label="Stripe Price ID")
    plan_code = config.require_plan_code_for_price(price_id)
    status = _text(subscription.get("status"), "Stripe subscription status").lower()

    start_value = subscription.get("current_period_start")
    if start_value is None:
        start_value = item.get("current_period_start")
    end_value = subscription.get("current_period_end")
    if end_value is None:
        end_value = item.get("current_period_end")

    period_start = _timestamp(start_value, "Stripe current period start", optional=True)
    period_end = _timestamp(end_value, "Stripe current period end", optional=True)
    if (period_start is None) != (period_end is None):
        raise BillingWebhookProcessingError("Stripe subscription period is incomplete")
    if period_start is not None and period_end is not None and period_end <= period_start:
        raise BillingWebhookProcessingError("Stripe subscription period is invalid")

    return _StripeSubscriptionState(
        subscription_id=subscription_id,
        customer_id=customer_id,
        billing_account_id=_metadata_account_id(subscription.get("metadata")),
        price_id=price_id,
        plan_code=plan_code,
        status=status,
        current_period_start=period_start,
        current_period_end=period_end,
        cancel_at_period_end=_boolean(
            subscription.get("cancel_at_period_end", False),
            "Stripe cancel_at_period_end",
        ),
        canceled_at=_timestamp(
            subscription.get("canceled_at"), "Stripe canceled_at", optional=True
        ),
        trial_end=_timestamp(subscription.get("trial_end"), "Stripe trial_end", optional=True),
        latest_invoice_id=_optional_expandable_id(
            subscription.get("latest_invoice"),
            prefix="in_",
            label="Stripe latest Invoice ID",
        ),
    )


def _resolve_billing_account(
    db: Session,
    *,
    billing_account_id: UUID | None,
    customer_id: str,
) -> dict[str, Any]:
    by_id = (
        get_billing_account_by_id(db, billing_account_id)
        if billing_account_id is not None
        else None
    )
    by_customer = get_billing_account_by_stripe_customer_id(db, customer_id)
    if billing_account_id is not None and by_id is None:
        raise BillingWebhookProcessingError("Stripe billing-account metadata is unknown")
    if by_id is not None and by_customer is not None and by_id["id"] != by_customer["id"]:
        raise BillingWebhookProcessingError("Stripe Customer ownership is inconsistent")
    account = by_id or by_customer
    if account is None:
        raise BillingWebhookProcessingError("Stripe event does not match a billing account")
    if account.get("owner_type") != "user":
        raise BillingWebhookProcessingError("Stripe event owner type is unsupported")

    persisted_customer = _optional_text(account.get("stripe_customer_id"))
    if persisted_customer is None:
        account = claim_stripe_customer_id(db, account["id"], customer_id)
        persisted_customer = _optional_text(account.get("stripe_customer_id"))
    if persisted_customer != customer_id:
        raise BillingWebhookProcessingError("Stripe Customer ownership could not be verified")
    return account


def _stored_event_at(snapshot: Mapping[str, Any] | None) -> datetime | None:
    if snapshot is None:
        return None
    value = snapshot.get("last_provider_event_at")
    if not isinstance(value, datetime):
        return None
    return _as_utc(value)


def _apply_subscription_state(
    db: Session,
    *,
    state: _StripeSubscriptionState,
    observed_at: datetime,
    effective_at: datetime,
    event_type: str,
    invoice_id: str | None = None,
    payment_failed_at: datetime | None = None,
    catalog: PlanCatalog,
) -> Literal["processed", "stale"]:
    account = _resolve_billing_account(
        db,
        billing_account_id=state.billing_account_id,
        customer_id=state.customer_id,
    )
    existing = get_subscription_by_provider_id(db, "stripe", state.subscription_id)
    if existing is not None and existing.get("billing_account_id") != account["id"]:
        raise BillingWebhookProcessingError("Stripe Subscription ownership could not be verified")
    previous_event_at = _stored_event_at(existing)
    if previous_event_at is not None and observed_at < previous_event_at:
        logger.info(
            "Ignoring stale Stripe subscription snapshot",
            extra={
                "extra_fields": {
                    "event": "billing.subscription.stale",
                    "billing_account_id": str(account["id"]),
                    "subscription_status": state.status,
                }
            },
        )
        return "stale"

    grace_until: datetime | None = None
    if state.status == "past_due":
        if payment_failed_at is not None:
            grace_until = payment_failed_at + timedelta(days=subscription_payment_grace_days())
        elif existing is not None and isinstance(existing.get("grace_until"), datetime):
            grace_until = _as_utc(existing["grace_until"])

    persisted = upsert_subscription_snapshot(
        db,
        SubscriptionSnapshot(
            billing_account_id=account["id"],
            provider="stripe",
            provider_subscription_id=state.subscription_id,
            provider_price_id=state.price_id,
            plan_code=state.plan_code,
            status=state.status,
            current_period_start=state.current_period_start,
            current_period_end=state.current_period_end,
            cancel_at_period_end=state.cancel_at_period_end,
            canceled_at=state.canceled_at,
            trial_end=state.trial_end,
            grace_until=grace_until,
            latest_invoice_id=(
                invoice_id
                or state.latest_invoice_id
                or (_optional_text(existing.get("latest_invoice_id")) if existing else None)
            ),
            last_provider_event_at=observed_at,
        ),
    )
    persisted_event_at = _stored_event_at(persisted)
    if persisted_event_at is not None and persisted_event_at > observed_at:
        return "stale"

    owner_id = account.get("owner_id")
    if not isinstance(owner_id, UUID):
        try:
            owner_id = UUID(str(owner_id))
        except ValueError as exc:
            raise BillingWebhookProcessingError("Billing account owner is invalid") from exc
    resolve_effective_subscription(db, owner_id, now=effective_at, catalog=catalog)
    logger.info(
        "Stripe subscription snapshot synchronized",
        extra={
            "extra_fields": {
                "event": "billing.subscription.updated",
                "billing_account_id": str(account["id"]),
                "plan_code": persisted["plan_code"],
                "subscription_status": persisted["status"],
                "source_event_type": event_type,
            }
        },
    )
    return "processed"


def _invoice_subscription_id(invoice: Mapping[str, Any]) -> str:
    direct = invoice.get("subscription")
    if direct is not None:
        return _expandable_id(direct, prefix="sub_", label="Stripe invoice Subscription ID")
    parent = invoice.get("parent")
    if isinstance(parent, Mapping):
        details = parent.get("subscription_details")
        if isinstance(details, Mapping) and details.get("subscription") is not None:
            return _expandable_id(
                details.get("subscription"),
                prefix="sub_",
                label="Stripe invoice Subscription ID",
            )
    raise BillingWebhookProcessingError("Stripe invoice Subscription ID is missing")


def _process_checkout_completed(
    db: Session,
    *,
    event_object: Mapping[str, Any],
    subscription: Mapping[str, Any],
    config: StripeBillingConfig,
    observed_at: datetime,
    effective_at: datetime,
    catalog: PlanCatalog,
) -> Literal["processed", "stale"]:
    if event_object.get("mode") != "subscription":
        raise BillingWebhookProcessingError("Stripe Checkout Session is not subscription mode")
    customer_id = _expandable_id(
        event_object.get("customer"), prefix="cus_", label="Stripe Customer ID"
    )
    billing_account_id = _metadata_account_id(
        event_object.get("metadata"), event_object.get("client_reference_id")
    )
    _resolve_billing_account(
        db,
        billing_account_id=billing_account_id,
        customer_id=customer_id,
    )
    subscription_id = _expandable_id(
        event_object.get("subscription"),
        prefix="sub_",
        label="Stripe Subscription ID",
    )
    if (
        _expandable_id(subscription.get("id"), prefix="sub_", label="Stripe Subscription ID")
        != subscription_id
    ):
        raise BillingWebhookProcessingError("Checkout and retrieved Subscription IDs do not match")
    state = _parse_subscription_state(subscription, config=config)
    if state.customer_id != customer_id:
        raise BillingWebhookProcessingError("Checkout and Subscription Customer do not match")
    if state.billing_account_id is None:
        state = replace(state, billing_account_id=billing_account_id)
    return _apply_subscription_state(
        db,
        state=state,
        observed_at=observed_at,
        effective_at=effective_at,
        event_type="checkout.session.completed",
        catalog=catalog,
    )


def _process_subscription_event(
    db: Session,
    *,
    event_type: str,
    event_object: Mapping[str, Any],
    config: StripeBillingConfig,
    observed_at: datetime,
    effective_at: datetime,
    catalog: PlanCatalog,
) -> Literal["processed", "stale"]:
    state = _parse_subscription_state(event_object, config=config)
    if event_type == "customer.subscription.deleted" and state.status != "canceled":
        state = replace(state, status="canceled")
    return _apply_subscription_state(
        db,
        state=state,
        observed_at=observed_at,
        effective_at=effective_at,
        event_type=event_type,
        catalog=catalog,
    )


def _process_invoice_event(
    db: Session,
    *,
    event_type: str,
    event_object: Mapping[str, Any],
    subscription: Mapping[str, Any],
    config: StripeBillingConfig,
    observed_at: datetime,
    effective_at: datetime,
    event_created_at: datetime,
    catalog: PlanCatalog,
) -> Literal["processed", "stale"]:
    invoice_id = _expandable_id(event_object.get("id"), prefix="in_", label="Stripe Invoice ID")
    subscription_id = _invoice_subscription_id(event_object)
    if (
        _expandable_id(subscription.get("id"), prefix="sub_", label="Stripe Subscription ID")
        != subscription_id
    ):
        raise BillingWebhookProcessingError("Invoice and retrieved Subscription IDs do not match")
    state = _parse_subscription_state(subscription, config=config)
    invoice_customer = event_object.get("customer")
    if invoice_customer is not None:
        customer_id = _expandable_id(
            invoice_customer, prefix="cus_", label="Stripe invoice Customer ID"
        )
        if customer_id != state.customer_id:
            raise BillingWebhookProcessingError("Invoice and Subscription Customer do not match")
    return _apply_subscription_state(
        db,
        state=state,
        observed_at=observed_at,
        effective_at=effective_at,
        event_type=event_type,
        invoice_id=invoice_id,
        payment_failed_at=(event_created_at if event_type == "invoice.payment_failed" else None),
        catalog=catalog,
    )


def _dispatch_event(
    db: Session,
    *,
    event_type: str,
    event_object: Mapping[str, Any],
    event_created_at: datetime,
    retrieved_subscription: Mapping[str, Any] | None,
    config: StripeBillingConfig,
    effective_at: datetime,
    catalog: PlanCatalog,
) -> Literal["processed", "stale"]:
    if event_type == "checkout.session.completed":
        # Checkout contains only a Subscription reference. The retrieved
        # snapshot is authoritative as of processing time.
        if retrieved_subscription is None:
            raise BillingWebhookProcessingError("Checkout Subscription state was not retrieved")
        return _process_checkout_completed(
            db,
            event_object=event_object,
            subscription=retrieved_subscription,
            config=config,
            observed_at=effective_at,
            effective_at=effective_at,
            catalog=catalog,
        )
    if event_type.startswith("customer.subscription."):
        return _process_subscription_event(
            db,
            event_type=event_type,
            event_object=event_object,
            config=config,
            observed_at=event_created_at,
            effective_at=effective_at,
            catalog=catalog,
        )
    if retrieved_subscription is None:
        raise BillingWebhookProcessingError("Invoice Subscription state was not retrieved")
    return _process_invoice_event(
        db,
        event_type=event_type,
        event_object=event_object,
        subscription=retrieved_subscription,
        config=config,
        observed_at=event_created_at,
        effective_at=effective_at,
        event_created_at=event_created_at,
        catalog=catalog,
    )


async def _retrieve_event_subscription(
    *,
    event_type: str,
    event_object: Mapping[str, Any],
    gateway: StripeWebhookGateway,
) -> Mapping[str, Any] | None:
    """Retrieve current provider state without holding a database transaction."""
    if event_type == "checkout.session.completed":
        if event_object.get("mode") != "subscription":
            raise BillingWebhookProcessingError("Stripe Checkout Session is not subscription mode")
        subscription_id = _expandable_id(
            event_object.get("subscription"),
            prefix="sub_",
            label="Stripe Subscription ID",
        )
        return await gateway.retrieve_subscription(subscription_id)
    if event_type in {"invoice.paid", "invoice.payment_failed"}:
        return await gateway.retrieve_subscription(_invoice_subscription_id(event_object))
    return None


def _mark_failed(
    uow_factory: BillingUowFactory,
    *,
    provider_event_id: str,
    error_code: str,
) -> None:
    try:
        with uow_factory() as db:
            event = lock_webhook_event(db, provider="stripe", provider_event_id=provider_event_id)
            if event is not None and event.get("processing_status") not in _TERMINAL_EVENT_STATUSES:
                mark_webhook_event_failed(
                    db,
                    event["id"],
                    error_message=error_code,
                )
    except Exception:
        logger.exception(
            "Failed to persist Stripe webhook failure state",
            extra={
                "extra_fields": {
                    "event": "billing.webhook.failed",
                    "provider_event_id": provider_event_id,
                }
            },
        )


async def process_stripe_webhook(
    *,
    uow_factory: BillingUowFactory,
    gateway: StripeWebhookGateway,
    config: StripeBillingConfig,
    payload: bytes,
    signature: str,
    catalog: PlanCatalog | None = None,
    now_factory: NowFactory = _now_utc,
) -> WebhookLifecycleResult:
    """Verify, persist, and synchronize one Stripe event with retry safety."""
    event = gateway.verify_webhook_event(payload=payload, signature=signature)
    provider_event_id = _text(event.get("id"), "Stripe Event ID")
    if not provider_event_id.startswith("evt_"):
        raise BillingWebhookProcessingError("Stripe Event ID is invalid")
    event_type = _text(event.get("type"), "Stripe event type")
    event_created_at = _timestamp(event.get("created"), "Stripe event created")
    if event_created_at is None:  # pragma: no cover - narrowed by non-optional parse
        raise BillingWebhookProcessingError("Stripe event created is missing")
    event_data = _mapping(event.get("data"), "Stripe event data")
    event_object = _mapping(event_data.get("object"), "Stripe event object")
    digest = hashlib.sha256(payload).hexdigest()
    resolved_catalog = catalog or get_plan_catalog()
    effective_at = _as_utc(now_factory())

    try:
        with uow_factory() as db:
            persisted_event, was_created = create_webhook_event_if_absent(
                db,
                provider="stripe",
                provider_event_id=provider_event_id,
                event_type=event_type,
                payload_hash=digest,
            )
    except ValueError as exc:
        raise BillingWebhookProcessingError(
            "Stripe Event ID conflicts with a previously received payload"
        ) from exc
    logger.info(
        "Stripe webhook received",
        extra={
            "extra_fields": {
                "event": "billing.webhook.received",
                "provider_event_id": provider_event_id,
                "event_type": event_type,
            }
        },
    )
    if not was_created:
        logger.info(
            "Duplicate Stripe webhook received",
            extra={
                "extra_fields": {
                    "event": "billing.webhook.duplicate",
                    "provider_event_id": provider_event_id,
                    "processing_status": persisted_event.get("processing_status"),
                }
            },
        )

    try:
        # Check terminal/unknown state under the event-row lock, then release
        # the transaction before any Stripe API retrieval.
        with uow_factory() as db:
            locked_event = lock_webhook_event(
                db,
                provider="stripe",
                provider_event_id=provider_event_id,
            )
            if locked_event is None:
                raise BillingWebhookProcessingError(
                    "Persisted Stripe webhook event could not be locked"
                )
            if locked_event.get("processing_status") in _TERMINAL_EVENT_STATUSES:
                return WebhookLifecycleResult(event_type=event_type, outcome="duplicate")
            if event_type not in _REQUIRED_EVENT_TYPES:
                mark_webhook_event_processed(db, locked_event["id"], ignored=True)
                return WebhookLifecycleResult(event_type=event_type, outcome="ignored")

        retrieved_subscription = await _retrieve_event_subscription(
            event_type=event_type,
            event_object=event_object,
            gateway=gateway,
        )

        # A concurrent delivery may have completed during provider retrieval.
        # Re-lock and re-check before applying any local lifecycle mutation.
        with uow_factory() as db:
            locked_event = lock_webhook_event(
                db,
                provider="stripe",
                provider_event_id=provider_event_id,
            )
            if locked_event is None:
                raise BillingWebhookProcessingError(
                    "Persisted Stripe webhook event could not be locked"
                )
            if locked_event.get("processing_status") in _TERMINAL_EVENT_STATUSES:
                return WebhookLifecycleResult(event_type=event_type, outcome="duplicate")
            outcome = _dispatch_event(
                db,
                event_type=event_type,
                event_object=event_object,
                event_created_at=event_created_at,
                retrieved_subscription=retrieved_subscription,
                config=config,
                effective_at=effective_at,
                catalog=resolved_catalog,
            )
            mark_webhook_event_processed(db, locked_event["id"])
    except Exception as exc:
        error_code = (
            "provider_unavailable"
            if isinstance(exc, BillingProviderError)
            else "lifecycle_synchronization_failed"
        )
        _mark_failed(
            uow_factory,
            provider_event_id=provider_event_id,
            error_code=error_code,
        )
        logger.exception(
            "Stripe webhook processing failed",
            extra={
                "extra_fields": {
                    "event": "billing.webhook.failed",
                    "provider_event_id": provider_event_id,
                    "event_type": event_type,
                }
            },
        )
        if isinstance(exc, (BillingConfigurationError, BillingWebhookProcessingError)):
            raise
        raise BillingWebhookProcessingError(
            "Verified Stripe event could not be synchronized"
        ) from exc

    logger.info(
        "Stripe webhook processed",
        extra={
            "extra_fields": {
                "event": "billing.webhook.processed",
                "provider_event_id": provider_event_id,
                "event_type": event_type,
                "outcome": outcome,
            }
        },
    )
    return WebhookLifecycleResult(event_type=event_type, outcome=outcome)


async def reconcile_billing_account(
    *,
    uow_factory: BillingUowFactory,
    gateway: StripeWebhookGateway,
    config: StripeBillingConfig,
    billing_account_id: UUID,
    catalog: PlanCatalog | None = None,
    now_factory: NowFactory = _now_utc,
) -> WebhookLifecycleResult:
    """Refresh one account from Stripe for an authorized operational caller.

    This is deliberately a service helper, not an HTTP endpoint. The current
    repository has tenant authentication but no administrator authorization
    primitive strong enough for cross-account reconciliation.
    """
    with uow_factory() as db:
        account = get_billing_account_by_id(db, billing_account_id)
        if account is None or account.get("owner_type") != "user":
            raise BillingWebhookProcessingError("Billing account is unavailable")
        customer_id = _optional_text(account.get("stripe_customer_id"))
        if customer_id is None:
            raise BillingWebhookProcessingError("Billing account has no Stripe Customer")
        local_snapshot = get_latest_subscription_for_account(db, billing_account_id)

    subscriptions = await gateway.list_customer_subscriptions(customer_id=customer_id)
    resolved_catalog = catalog or get_plan_catalog()
    effective_at = _as_utc(now_factory())
    live_subscriptions = [
        subscription
        for subscription in subscriptions
        if _optional_text(subscription.get("status")) in LIVE_SUBSCRIPTION_STATUSES
    ]
    if len(live_subscriptions) > 1:
        raise BillingWebhookProcessingError(
            "Multiple live Stripe Subscriptions require manual review"
        )

    selected: _StripeSubscriptionState | None = None
    selected_subscription: Mapping[str, Any] | None = None
    if live_subscriptions:
        selected_subscription = live_subscriptions[0]
    elif subscriptions:
        selected_subscription = max(
            subscriptions,
            key=_created_sort_key,
        )
    if selected_subscription is not None:
        selected = _parse_subscription_state(selected_subscription, config=config)
        if selected.customer_id != customer_id:
            raise BillingWebhookProcessingError(
                "Reconciliation returned a Subscription for another Customer"
            )

    with uow_factory() as db:
        if selected is None:
            if local_snapshot is None:
                return WebhookLifecycleResult(event_type="reconciliation", outcome="reconciled")
            selected = _StripeSubscriptionState(
                subscription_id=str(local_snapshot["provider_subscription_id"]),
                customer_id=customer_id,
                billing_account_id=billing_account_id,
                price_id=str(local_snapshot.get("provider_price_id") or ""),
                plan_code=str(local_snapshot["plan_code"]),
                status="canceled",
                current_period_start=local_snapshot.get("current_period_start"),
                current_period_end=local_snapshot.get("current_period_end"),
                cancel_at_period_end=False,
                canceled_at=effective_at,
                trial_end=local_snapshot.get("trial_end"),
                latest_invoice_id=local_snapshot.get("latest_invoice_id"),
            )
        if selected.billing_account_id is None:
            selected = replace(selected, billing_account_id=billing_account_id)
        _apply_subscription_state(
            db,
            state=selected,
            observed_at=effective_at,
            effective_at=effective_at,
            event_type="reconciliation",
            catalog=resolved_catalog,
        )
    return WebhookLifecycleResult(event_type="reconciliation", outcome="reconciled")
