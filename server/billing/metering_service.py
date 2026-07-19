"""Atomic reservation lifecycle for subscription usage allowances.

All functions participate in the caller-owned SQLAlchemy transaction. They do
not commit or roll back, allowing route-level units of work to compose plan
resolution and metering safely before provider execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from db import billing_repository as repository
from server.billing.errors import (
    BillingConfigurationError,
    UsageAllowanceExceededError,
    UsageReservationConflictError,
    UsageReservationNotFoundError,
    UsageReservationStateError,
)
from server.billing.subscription_service import EffectiveSubscription
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RESERVATION_TTL = timedelta(minutes=30)
_EXPIRY_REASON = "stale_reservation_expired"


@dataclass(frozen=True)
class UsageReservation:
    id: UUID
    billing_account_id: UUID
    usage_period_id: UUID
    request_id: str
    operation_type: str
    state: str
    requested_quantities: Mapping[str, int]
    settled_quantities: Mapping[str, int] | None
    release_reason: str | None
    created_at: datetime
    settled_at: datetime | None
    released_at: datetime | None


def _required_text(value: str, field_name: str, *, max_length: int = 255) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    return normalized


def _normalize_quantities(
    quantities: Mapping[str, int],
    *,
    field_name: str,
    allow_empty: bool,
) -> dict[str, int]:
    if not isinstance(quantities, Mapping):
        raise ValueError(f"{field_name} must be a mapping")

    normalized: dict[str, int] = {}
    for raw_meter, quantity in quantities.items():
        meter = str(raw_meter or "").strip()
        if meter not in repository.ALLOWED_USAGE_METERS:
            raise ValueError(f"Unknown usage meter: {meter}")
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError(f"{field_name}.{meter} must be an integer")
        if quantity < 0:
            raise ValueError(f"{field_name}.{meter} must be nonnegative")
        if quantity > 0:
            normalized[meter] = quantity

    if not normalized and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one positive quantity")
    return normalized


def _record_quantities(record: Mapping[str, Any], field_name: str) -> dict[str, int]:
    raw = record.get(field_name)
    if raw is None and field_name == "settled_quantities":
        return {}
    if not isinstance(raw, Mapping):
        raise BillingConfigurationError(f"Reservation {field_name} is invalid")
    try:
        return _normalize_quantities(
            cast(Mapping[str, int], raw),
            field_name=field_name,
            allow_empty=field_name == "settled_quantities",
        )
    except ValueError as exc:
        raise BillingConfigurationError(f"Reservation {field_name} is invalid") from exc


def _to_reservation(record: Mapping[str, Any]) -> UsageReservation:
    requested = _record_quantities(record, "requested_quantities")
    settled = (
        _record_quantities(record, "settled_quantities")
        if record.get("settled_quantities") is not None
        else None
    )
    return UsageReservation(
        id=cast(UUID, record["id"]),
        billing_account_id=cast(UUID, record["billing_account_id"]),
        usage_period_id=cast(UUID, record["usage_period_id"]),
        request_id=str(record["request_id"]),
        operation_type=str(record["operation_type"]),
        state=str(record["state"]),
        requested_quantities=requested,
        settled_quantities=settled,
        release_reason=(
            str(record["release_reason"]) if record.get("release_reason") is not None else None
        ),
        created_at=cast(datetime, record["created_at"]),
        settled_at=cast(datetime | None, record.get("settled_at")),
        released_at=cast(datetime | None, record.get("released_at")),
    )


def _matching_reservation(
    record: Mapping[str, Any],
    *,
    operation_type: str,
    requested_quantities: Mapping[str, int],
) -> UsageReservation:
    persisted_operation = str(record.get("operation_type") or "").strip().lower()
    persisted_quantities = _record_quantities(record, "requested_quantities")
    if persisted_operation != operation_type or persisted_quantities != requested_quantities:
        raise UsageReservationConflictError(
            "The request ID is already associated with different usage quantities."
        )
    return _to_reservation(record)


def _allowance_limit(effective: EffectiveSubscription, meter: str) -> int:
    try:
        value = getattr(effective.plan.allowances, meter)
    except AttributeError as exc:
        raise BillingConfigurationError(
            f"The effective plan does not define the {meter} allowance"
        ) from exc
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BillingConfigurationError(f"The effective plan has an invalid {meter} allowance")
    return value


def _lock_and_validate_counters(
    db: Session,
    *,
    usage_period_id: UUID,
    quantities: Mapping[str, int],
    enforce_limits: bool,
    effective: EffectiveSubscription | None = None,
    create_missing: bool = False,
) -> list[dict[str, Any]]:
    try:
        if create_missing:
            for meter in sorted(quantities):
                repository.get_or_create_usage_counter(db, usage_period_id, meter)
        counters = repository.lock_usage_counters(
            db,
            usage_period_id,
            sorted(quantities),
        )
    except Exception as exc:
        raise BillingConfigurationError("Usage counters could not be locked") from exc

    by_meter = {str(counter["meter_key"]): counter for counter in counters}
    for meter, requested in quantities.items():
        counter = by_meter.get(meter)
        if counter is None:
            raise BillingConfigurationError(f"The {meter} usage counter is unavailable")
        used = int(counter.get("used_quantity") or 0)
        reserved = int(counter.get("reserved_quantity") or 0)
        if used < 0 or reserved < 0:
            raise BillingConfigurationError(f"The {meter} usage counter is invalid")
        if enforce_limits:
            if effective is None:
                raise BillingConfigurationError("The effective subscription is unavailable")
            limit = _allowance_limit(effective, meter)
            if requested > limit - used - reserved:
                raise UsageAllowanceExceededError(
                    meter=meter,
                    requested=requested,
                    used=used,
                    reserved=reserved,
                    limit=limit,
                    plan_code=effective.plan.code,
                    reset_at=effective.current_period_end,
                )
    return counters


def reserve_usage(
    db_session: Session,
    *,
    effective_subscription: EffectiveSubscription,
    request_id: str,
    operation_type: str,
    requested_quantities: Mapping[str, int],
) -> UsageReservation:
    """Atomically claim plan allowance capacity for one idempotent request."""
    normalized_request_id = _required_text(request_id, "request_id")
    normalized_operation = _required_text(
        operation_type,
        "operation_type",
        max_length=64,
    ).lower()
    quantities = _normalize_quantities(
        requested_quantities,
        field_name="requested_quantities",
        allow_empty=False,
    )
    effective = effective_subscription

    existing = repository.get_usage_reservation(
        db_session,
        effective.billing_account_id,
        normalized_request_id,
    )
    if existing is not None:
        return _matching_reservation(
            existing,
            operation_type=normalized_operation,
            requested_quantities=quantities,
        )

    account = repository.lock_billing_account(db_session, effective.billing_account_id)
    if account is None:
        raise BillingConfigurationError("The effective billing account no longer exists")

    # The account lock closes the no-row idempotency race. Counter locks remain
    # the authoritative protection against concurrent allowance overuse.
    existing = repository.get_usage_reservation(
        db_session,
        effective.billing_account_id,
        normalized_request_id,
    )
    if existing is not None:
        return _matching_reservation(
            existing,
            operation_type=normalized_operation,
            requested_quantities=quantities,
        )

    _lock_and_validate_counters(
        db_session,
        usage_period_id=effective.usage_period_id,
        effective=effective,
        quantities=quantities,
        enforce_limits=True,
        create_missing=True,
    )
    try:
        repository.reserve_usage_quantities(
            db_session,
            effective.usage_period_id,
            quantities,
        )
        record = repository.create_usage_reservation(
            db_session,
            billing_account_id=effective.billing_account_id,
            usage_period_id=effective.usage_period_id,
            request_id=normalized_request_id,
            operation_type=normalized_operation,
            requested_quantities=quantities,
        )
    except UsageAllowanceExceededError:
        raise
    except Exception as exc:
        raise BillingConfigurationError("Usage could not be reserved atomically") from exc
    return _to_reservation(record)


def _locked_reservation(db_session: Session, reservation_id: UUID) -> dict[str, Any]:
    record = repository.get_usage_reservation_by_id(
        db_session,
        reservation_id,
        for_update=True,
    )
    if record is None:
        raise UsageReservationNotFoundError("Usage reservation was not found")
    return record


def _validate_reserved_counters(
    counters: list[dict[str, Any]],
    requested_quantities: Mapping[str, int],
) -> None:
    by_meter = {str(counter["meter_key"]): counter for counter in counters}
    for meter, requested in requested_quantities.items():
        counter = by_meter.get(meter)
        reserved = int(counter.get("reserved_quantity") or 0) if counter else -1
        if reserved < requested:
            raise BillingConfigurationError(
                f"The {meter} counter no longer contains the reserved quantity"
            )


def settle_usage(
    db_session: Session,
    *,
    reservation_id: UUID,
    successful_quantities: Mapping[str, int],
    settlement_metadata: Mapping[str, Any] | None = None,
) -> UsageReservation:
    """Finalize successful units and release every unused reserved unit.

    The WP2 schema has no settlement-metadata column, so arbitrary metadata
    values are neither persisted nor logged. Only key names enter diagnostics.
    """
    successful = _normalize_quantities(
        successful_quantities,
        field_name="successful_quantities",
        allow_empty=True,
    )
    record = _locked_reservation(db_session, reservation_id)
    requested = _record_quantities(record, "requested_quantities")
    if any(
        meter not in requested or value > requested[meter] for meter, value in successful.items()
    ):
        raise ValueError("Successful quantities cannot exceed the reservation")

    state = str(record.get("state") or "")
    if state == "settled":
        if _record_quantities(record, "settled_quantities") != successful:
            raise UsageReservationConflictError(
                "The reservation was already settled with different quantities."
            )
        return _to_reservation(record)
    if state != "reserved":
        raise UsageReservationStateError(f"Cannot settle a reservation in state {state}")

    counters = _lock_and_validate_counters(
        db_session,
        usage_period_id=cast(UUID, record["usage_period_id"]),
        quantities=requested,
        enforce_limits=False,
    )
    _validate_reserved_counters(counters, requested)
    try:
        repository.settle_usage_quantities(
            db_session,
            cast(UUID, record["usage_period_id"]),
            requested_quantities=requested,
            successful_quantities=successful,
        )
        persisted = repository.settle_usage_reservation(
            db_session,
            billing_account_id=cast(UUID, record["billing_account_id"]),
            request_id=str(record["request_id"]),
            settled_quantities=successful,
        )
    except Exception as exc:
        raise BillingConfigurationError("Usage could not be settled atomically") from exc

    metadata_keys = sorted(str(key) for key in (settlement_metadata or {}))
    logger.info(
        "Subscription usage settled",
        extra={
            "extra_fields": {
                "reservation_id": str(reservation_id),
                "requested_quantities": requested,
                "successful_quantities": successful,
                "settlement_metadata_keys": metadata_keys,
            }
        },
    )
    return _to_reservation(persisted)


def release_usage(
    db_session: Session,
    *,
    reservation_id: UUID,
    reason: str,
) -> UsageReservation:
    """Release every still-reserved unit without incrementing finalized usage."""
    normalized_reason = _required_text(reason, "reason")
    record = _locked_reservation(db_session, reservation_id)
    state = str(record.get("state") or "")
    if state == "released":
        return _to_reservation(record)
    if state != "reserved":
        raise UsageReservationStateError(f"Cannot release a reservation in state {state}")

    requested = _record_quantities(record, "requested_quantities")
    counters = _lock_and_validate_counters(
        db_session,
        usage_period_id=cast(UUID, record["usage_period_id"]),
        quantities=requested,
        enforce_limits=False,
    )
    _validate_reserved_counters(counters, requested)
    try:
        repository.release_usage_quantities(
            db_session,
            cast(UUID, record["usage_period_id"]),
            requested,
        )
        persisted = repository.release_usage_reservation(
            db_session,
            billing_account_id=cast(UUID, record["billing_account_id"]),
            request_id=str(record["request_id"]),
            release_reason=normalized_reason,
        )
    except Exception as exc:
        raise BillingConfigurationError("Usage could not be released atomically") from exc
    return _to_reservation(persisted)


def expire_stale_reservations(
    db_session: Session,
    *,
    older_than: datetime | None = None,
) -> int:
    """Release clearly stale reservations, defaulting to a 30-minute cutoff."""
    threshold = older_than or (datetime.now(UTC) - DEFAULT_RESERVATION_TTL)
    if threshold.tzinfo is None:
        raise ValueError("older_than must be timezone-aware")

    try:
        stale = repository.lock_stale_usage_reservations(
            db_session,
            older_than=threshold.astimezone(UTC),
        )
        expired = 0
        for record in stale:
            requested = _record_quantities(record, "requested_quantities")
            counters = _lock_and_validate_counters(
                db_session,
                usage_period_id=cast(UUID, record["usage_period_id"]),
                quantities=requested,
                enforce_limits=False,
            )
            _validate_reserved_counters(counters, requested)
            repository.release_usage_quantities(
                db_session,
                cast(UUID, record["usage_period_id"]),
                requested,
            )
            repository.expire_usage_reservation(
                db_session,
                reservation_id=cast(UUID, record["id"]),
                release_reason=_EXPIRY_REASON,
            )
            expired += 1
        return expired
    except (ValueError, UsageReservationStateError):
        raise
    except Exception as exc:
        raise BillingConfigurationError("Stale usage reservations could not be expired") from exc
