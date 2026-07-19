"""SQLAlchemy Core repository for B2C billing persistence.

Repository functions never commit. Callers own transaction boundaries so
account creation, subscription updates, and future metering operations can be
composed atomically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID, uuid4

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

BillingRecord: TypeAlias = dict[str, Any]

ALLOWED_USAGE_METERS = frozenset(
    {
        "model_responses",
        "advanced_model_responses",
        "ultra_model_responses",
        "research_turns",
        "optimization_turns",
        "file_analysis_turns",
        "uploaded_bytes",
    }
)

LIVE_SUBSCRIPTION_STATUSES = frozenset(
    {"trialing", "active", "past_due", "unpaid", "paused", "incomplete"}
)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    """Provider subscription fields persisted as an internal snapshot."""

    billing_account_id: UUID
    provider: str
    provider_subscription_id: str
    plan_code: str
    status: str
    provider_price_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    canceled_at: datetime | None = None
    trial_end: datetime | None = None
    grace_until: datetime | None = None
    latest_invoice_id: str | None = None
    last_provider_event_at: datetime | None = None


def _table(name: str):
    from db.tables import get_table

    return get_table(name)


def _dialect_insert(db: Session, table):
    """Return an INSERT supporting ON CONFLICT for runtime and isolated tests."""
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        return pg_insert(table)
    if dialect_name == "sqlite":
        return sqlite_insert(table)
    raise RuntimeError(
        "Billing repository requires PostgreSQL; SQLite is supported only for isolated tests"
    )


def _record(row: RowMapping | None) -> BillingRecord | None:
    return dict(row) if row is not None else None


def _first_record(result) -> BillingRecord | None:
    return _record(result.mappings().first())


def _required_text(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalized_provider(provider: str) -> str:
    return _required_text(provider, "provider").lower()


def _normalize_quantities(
    quantities: Mapping[str, int],
    *,
    field_name: str,
    require_positive: bool,
) -> dict[str, int]:
    if not isinstance(quantities, Mapping) or not quantities:
        raise ValueError(f"{field_name} must be a non-empty mapping")

    normalized: dict[str, int] = {}
    for meter_key, quantity in quantities.items():
        if meter_key not in ALLOWED_USAGE_METERS:
            raise ValueError(f"Unknown usage meter: {meter_key}")
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError(f"{field_name}.{meter_key} must be an integer")
        minimum = 1 if require_positive else 0
        if quantity < minimum:
            comparator = "positive" if require_positive else "nonnegative"
            raise ValueError(f"{field_name}.{meter_key} must be {comparator}")
        normalized[meter_key] = quantity
    return normalized


def get_billing_account_for_user(db: Session, user_id: UUID) -> BillingRecord | None:
    billing_accounts = _table("billing_accounts")
    stmt = select(billing_accounts).where(
        and_(
            billing_accounts.c.owner_type == "user",
            billing_accounts.c.owner_id == user_id,
        )
    )
    return _first_record(db.execute(stmt))


def get_or_create_billing_account_for_user(db: Session, user_id: UUID) -> BillingRecord:
    """Get or atomically create the one B2C billing account for a user."""
    billing_accounts = _table("billing_accounts")
    account_id = uuid4()
    stmt = (
        _dialect_insert(db, billing_accounts)
        .values(id=account_id, owner_type="user", owner_id=user_id)
        .on_conflict_do_nothing(index_elements=["owner_type", "owner_id"])
        .returning(*billing_accounts.c)
    )
    created = _first_record(db.execute(stmt))
    if created is not None:
        return created

    existing = get_billing_account_for_user(db, user_id)
    if existing is None:
        raise RuntimeError("Billing account conflict occurred but the account could not be read")
    return existing


def set_stripe_customer_id(
    db: Session,
    billing_account_id: UUID,
    stripe_customer_id: str,
) -> BillingRecord | None:
    billing_accounts = _table("billing_accounts")
    customer_id = _required_text(stripe_customer_id, "stripe_customer_id")
    stmt = (
        update(billing_accounts)
        .where(billing_accounts.c.id == billing_account_id)
        .values(stripe_customer_id=customer_id, updated_at=func.now())
        .returning(*billing_accounts.c)
    )
    return _first_record(db.execute(stmt))


def get_subscription_by_provider_id(
    db: Session,
    provider: str,
    provider_subscription_id: str,
) -> BillingRecord | None:
    subscriptions = _table("subscriptions")
    stmt = select(subscriptions).where(
        and_(
            subscriptions.c.provider == _normalized_provider(provider),
            subscriptions.c.provider_subscription_id
            == _required_text(provider_subscription_id, "provider_subscription_id"),
        )
    )
    return _first_record(db.execute(stmt))


def get_live_subscription_for_account(
    db: Session,
    billing_account_id: UUID,
) -> BillingRecord | None:
    """Return the provider-lifecycle row; WP3 decides whether it grants access."""
    subscriptions = _table("subscriptions")
    stmt = (
        select(subscriptions)
        .where(
            and_(
                subscriptions.c.billing_account_id == billing_account_id,
                subscriptions.c.status.in_(sorted(LIVE_SUBSCRIPTION_STATUSES)),
            )
        )
        .order_by(
            subscriptions.c.current_period_end.desc().nullslast(),
            subscriptions.c.updated_at.desc(),
        )
        .limit(1)
    )
    return _first_record(db.execute(stmt))


def upsert_subscription_snapshot(
    db: Session,
    snapshot: SubscriptionSnapshot,
) -> BillingRecord:
    """Upsert one provider snapshot without allowing cross-account reassignment."""
    subscriptions = _table("subscriptions")
    payload = asdict(snapshot)
    payload["provider"] = _normalized_provider(snapshot.provider)
    payload["provider_subscription_id"] = _required_text(
        snapshot.provider_subscription_id, "provider_subscription_id"
    )
    payload["plan_code"] = _required_text(snapshot.plan_code, "plan_code").lower()
    payload["status"] = _required_text(snapshot.status, "status").lower()

    insert_payload = {"id": uuid4(), **payload}
    update_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"billing_account_id", "provider", "provider_subscription_id"}
    }
    update_payload["updated_at"] = func.now()

    stmt = (
        _dialect_insert(db, subscriptions)
        .values(**insert_payload)
        .on_conflict_do_update(
            index_elements=["provider", "provider_subscription_id"],
            set_=update_payload,
            where=subscriptions.c.billing_account_id == snapshot.billing_account_id,
        )
        .returning(*subscriptions.c)
    )
    persisted = _first_record(db.execute(stmt))
    if persisted is not None:
        return persisted

    existing = get_subscription_by_provider_id(
        db,
        payload["provider"],
        payload["provider_subscription_id"],
    )
    if existing is not None and existing["billing_account_id"] != snapshot.billing_account_id:
        raise ValueError("Provider subscription is already assigned to another billing account")
    raise RuntimeError("Subscription snapshot could not be persisted")


def get_active_usage_period(
    db: Session,
    billing_account_id: UUID,
    at_time: datetime,
) -> BillingRecord | None:
    usage_periods = _table("usage_periods")
    stmt = (
        select(usage_periods)
        .where(
            and_(
                usage_periods.c.billing_account_id == billing_account_id,
                usage_periods.c.status == "active",
                usage_periods.c.starts_at <= at_time,
                usage_periods.c.ends_at > at_time,
            )
        )
        .order_by(usage_periods.c.starts_at.desc())
        .limit(1)
    )
    return _first_record(db.execute(stmt))


def create_usage_period(
    db: Session,
    *,
    billing_account_id: UUID,
    plan_code: str,
    starts_at: datetime,
    ends_at: datetime,
    subscription_id: UUID | None = None,
) -> BillingRecord:
    if ends_at <= starts_at:
        raise ValueError("ends_at must be after starts_at")

    usage_periods = _table("usage_periods")
    stmt = (
        insert(usage_periods)
        .values(
            id=uuid4(),
            billing_account_id=billing_account_id,
            subscription_id=subscription_id,
            plan_code=_required_text(plan_code, "plan_code").lower(),
            starts_at=starts_at,
            ends_at=ends_at,
            status="active",
        )
        .returning(*usage_periods.c)
    )
    persisted = _first_record(db.execute(stmt))
    if persisted is None:
        raise RuntimeError("Usage period could not be created")
    return persisted


def close_usage_period(db: Session, usage_period_id: UUID) -> BillingRecord | None:
    usage_periods = _table("usage_periods")
    stmt = (
        update(usage_periods)
        .where(usage_periods.c.id == usage_period_id)
        .values(status="closed", updated_at=func.now())
        .returning(*usage_periods.c)
    )
    return _first_record(db.execute(stmt))


def get_or_create_usage_counter(
    db: Session,
    usage_period_id: UUID,
    meter_key: str,
) -> BillingRecord:
    if meter_key not in ALLOWED_USAGE_METERS:
        raise ValueError(f"Unknown usage meter: {meter_key}")

    usage_counters = _table("usage_counters")
    stmt = (
        _dialect_insert(db, usage_counters)
        .values(
            id=uuid4(),
            usage_period_id=usage_period_id,
            meter_key=meter_key,
            used_quantity=0,
            reserved_quantity=0,
        )
        .on_conflict_do_nothing(index_elements=["usage_period_id", "meter_key"])
        .returning(*usage_counters.c)
    )
    created = _first_record(db.execute(stmt))
    if created is not None:
        return created

    existing_stmt = select(usage_counters).where(
        and_(
            usage_counters.c.usage_period_id == usage_period_id,
            usage_counters.c.meter_key == meter_key,
        )
    )
    existing = _first_record(db.execute(existing_stmt))
    if existing is None:
        raise RuntimeError("Usage counter conflict occurred but the counter could not be read")
    return existing


def lock_usage_counters(
    db: Session,
    usage_period_id: UUID,
    meter_keys: Sequence[str],
) -> list[BillingRecord]:
    """Lock counters in deterministic meter order to avoid lock inversion."""
    normalized_keys = sorted(set(meter_keys))
    unknown = set(normalized_keys) - ALLOWED_USAGE_METERS
    if unknown:
        raise ValueError(f"Unknown usage meters: {', '.join(sorted(unknown))}")
    if not normalized_keys:
        return []

    usage_counters = _table("usage_counters")
    stmt = (
        select(usage_counters)
        .where(
            and_(
                usage_counters.c.usage_period_id == usage_period_id,
                usage_counters.c.meter_key.in_(normalized_keys),
            )
        )
        .order_by(usage_counters.c.meter_key)
        .with_for_update()
    )
    rows = [dict(row) for row in db.execute(stmt).mappings().all()]
    found = {row["meter_key"] for row in rows}
    missing = set(normalized_keys) - found
    if missing:
        raise LookupError(f"Usage counters must exist before locking: {', '.join(sorted(missing))}")
    return rows


def create_usage_reservation(
    db: Session,
    *,
    billing_account_id: UUID,
    usage_period_id: UUID,
    request_id: str,
    operation_type: str,
    requested_quantities: Mapping[str, int],
) -> BillingRecord:
    usage_reservations = _table("usage_reservations")
    quantities = _normalize_quantities(
        requested_quantities,
        field_name="requested_quantities",
        require_positive=True,
    )
    stmt = (
        insert(usage_reservations)
        .values(
            id=uuid4(),
            billing_account_id=billing_account_id,
            usage_period_id=usage_period_id,
            request_id=_required_text(request_id, "request_id"),
            operation_type=_required_text(operation_type, "operation_type").lower(),
            state="reserved",
            requested_quantities=quantities,
        )
        .returning(*usage_reservations.c)
    )
    persisted = _first_record(db.execute(stmt))
    if persisted is None:
        raise RuntimeError("Usage reservation could not be created")
    return persisted


def _get_usage_reservation(
    db: Session,
    billing_account_id: UUID,
    request_id: str,
    *,
    for_update: bool,
) -> BillingRecord | None:
    usage_reservations = _table("usage_reservations")
    stmt = select(usage_reservations).where(
        and_(
            usage_reservations.c.billing_account_id == billing_account_id,
            usage_reservations.c.request_id == _required_text(request_id, "request_id"),
        )
    )
    if for_update:
        stmt = stmt.with_for_update()
    return _first_record(db.execute(stmt))


def get_usage_reservation(
    db: Session,
    billing_account_id: UUID,
    request_id: str,
) -> BillingRecord | None:
    return _get_usage_reservation(
        db,
        billing_account_id,
        request_id,
        for_update=False,
    )


def settle_usage_reservation(
    db: Session,
    *,
    billing_account_id: UUID,
    request_id: str,
    settled_quantities: Mapping[str, int],
) -> BillingRecord:
    quantities = _normalize_quantities(
        settled_quantities,
        field_name="settled_quantities",
        require_positive=False,
    )
    existing = _get_usage_reservation(
        db,
        billing_account_id,
        request_id,
        for_update=True,
    )
    if existing is None:
        raise LookupError("Usage reservation was not found")

    requested = dict(existing["requested_quantities"])
    if any(key not in requested or value > requested[key] for key, value in quantities.items()):
        raise ValueError("Settled quantities cannot exceed the reservation")

    if existing["state"] == "settled":
        if dict(existing["settled_quantities"] or {}) != quantities:
            raise ValueError("Usage reservation was already settled with different quantities")
        return existing
    if existing["state"] != "reserved":
        raise ValueError(f"Cannot settle a reservation in state {existing['state']}")

    usage_reservations = _table("usage_reservations")
    stmt = (
        update(usage_reservations)
        .where(
            and_(
                usage_reservations.c.id == existing["id"],
                usage_reservations.c.state == "reserved",
            )
        )
        .values(
            state="settled",
            settled_quantities=quantities,
            settled_at=func.now(),
            release_reason=None,
        )
        .returning(*usage_reservations.c)
    )
    persisted = _first_record(db.execute(stmt))
    if persisted is None:
        raise RuntimeError("Usage reservation state changed during settlement")
    return persisted


def release_usage_reservation(
    db: Session,
    *,
    billing_account_id: UUID,
    request_id: str,
    release_reason: str,
) -> BillingRecord:
    reason = _required_text(release_reason, "release_reason")
    existing = _get_usage_reservation(
        db,
        billing_account_id,
        request_id,
        for_update=True,
    )
    if existing is None:
        raise LookupError("Usage reservation was not found")
    if existing["state"] == "released":
        return existing
    if existing["state"] != "reserved":
        raise ValueError(f"Cannot release a reservation in state {existing['state']}")

    usage_reservations = _table("usage_reservations")
    stmt = (
        update(usage_reservations)
        .where(
            and_(
                usage_reservations.c.id == existing["id"],
                usage_reservations.c.state == "reserved",
            )
        )
        .values(state="released", release_reason=reason, released_at=func.now())
        .returning(*usage_reservations.c)
    )
    persisted = _first_record(db.execute(stmt))
    if persisted is None:
        raise RuntimeError("Usage reservation state changed during release")
    return persisted


def _validate_payload_hash(payload_hash: str) -> str:
    normalized = _required_text(payload_hash, "payload_hash").lower()
    if len(normalized) != 64:
        raise ValueError("payload_hash must be a SHA-256 hex digest")
    try:
        int(normalized, 16)
    except ValueError as exc:
        raise ValueError("payload_hash must be a SHA-256 hex digest") from exc
    return normalized


def create_webhook_event_if_absent(
    db: Session,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload_hash: str,
) -> tuple[BillingRecord, bool]:
    """Create an idempotency record and report whether this call inserted it."""
    billing_webhook_events = _table("billing_webhook_events")
    provider_name = _normalized_provider(provider)
    external_id = _required_text(provider_event_id, "provider_event_id")
    digest = _validate_payload_hash(payload_hash)
    stmt = (
        _dialect_insert(db, billing_webhook_events)
        .values(
            id=uuid4(),
            provider=provider_name,
            provider_event_id=external_id,
            event_type=_required_text(event_type, "event_type"),
            payload_hash=digest,
            processing_status="received",
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_event_id"])
        .returning(*billing_webhook_events.c)
    )
    created = _first_record(db.execute(stmt))
    if created is not None:
        return created, True

    existing_stmt = select(billing_webhook_events).where(
        and_(
            billing_webhook_events.c.provider == provider_name,
            billing_webhook_events.c.provider_event_id == external_id,
        )
    )
    existing = _first_record(db.execute(existing_stmt))
    if existing is None:
        raise RuntimeError("Webhook event conflict occurred but the event could not be read")
    if existing["payload_hash"] != digest:
        raise ValueError("Webhook event ID was reused with a different payload hash")
    return existing, False


def mark_webhook_event_processed(
    db: Session,
    event_id: UUID,
    *,
    ignored: bool = False,
) -> BillingRecord | None:
    billing_webhook_events = _table("billing_webhook_events")
    stmt = (
        update(billing_webhook_events)
        .where(billing_webhook_events.c.id == event_id)
        .values(
            processing_status="ignored" if ignored else "processed",
            processed_at=func.now(),
            error_message=None,
        )
        .returning(*billing_webhook_events.c)
    )
    return _first_record(db.execute(stmt))


def mark_webhook_event_failed(
    db: Session,
    event_id: UUID,
    *,
    error_message: str,
) -> BillingRecord | None:
    billing_webhook_events = _table("billing_webhook_events")
    stmt = (
        update(billing_webhook_events)
        .where(billing_webhook_events.c.id == event_id)
        .values(
            processing_status="failed",
            processed_at=func.now(),
            error_message=_required_text(error_message, "error_message"),
        )
        .returning(*billing_webhook_events.c)
    )
    return _first_record(db.execute(stmt))
