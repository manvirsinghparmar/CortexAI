"""Authenticated Stripe Checkout and Customer Portal session routes."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, Request

from server import persistence as persistence_service
from server.billing.errors import (
    BillingConfigurationError,
    BillingIdentityError,
    BillingNotConfiguredError,
    BillingPlanSelectionError,
    BillingProviderError,
    StripeCustomerRequiredError,
    billing_configuration_http_exception,
    billing_database_required_http_exception,
    billing_identity_http_exception,
    billing_not_configured_http_exception,
    billing_plan_selection_http_exception,
    billing_provider_http_exception,
    stripe_customer_required_http_exception,
)
from server.billing.session_service import (
    create_checkout_redirect,
    create_portal_redirect,
)
from server.billing.stripe_gateway import (
    StripeBillingConfig,
    StripeGateway,
    require_stripe_billing_config,
)
from server.dependencies import AuthResult, get_auth
from server.routes.session_auth import SessionScopedAuthGuard
from server.schemas.requests import CheckoutSessionRequest, PortalSessionRequest
from server.schemas.responses import CheckoutSessionResponseDTO, PortalSessionResponseDTO
from utils.logger import get_logger

router = APIRouter(prefix="/v1/billing", tags=["Billing"])
logger = get_logger(__name__)

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_resolve_identity = persistence_service.resolve_identity
_db_uow = persistence_service.db_uow
_SESSION_AUTH_GUARD = SessionScopedAuthGuard(
    route_label="Billing",
    rejection_event="billing.auth.session_required",
    logger=logger,
)


def _gateway_factory(config: StripeBillingConfig) -> StripeGateway:
    return StripeGateway(config)


def _raise_billing_http_error(error: Exception, *, request_id: str) -> None:
    if isinstance(error, BillingNotConfiguredError):
        raise billing_not_configured_http_exception() from error
    if isinstance(error, BillingPlanSelectionError):
        raise billing_plan_selection_http_exception(error) from error
    if isinstance(error, StripeCustomerRequiredError):
        raise stripe_customer_required_http_exception() from error
    if isinstance(error, BillingProviderError):
        logger.warning(
            "Stripe hosted billing session creation failed",
            extra={"extra_fields": {"request_id": request_id}},
        )
        raise billing_provider_http_exception() from error
    if isinstance(error, BillingIdentityError):
        raise billing_identity_http_exception() from error
    logger.exception(
        "Billing session configuration failed",
        extra={"extra_fields": {"request_id": request_id}},
    )
    raise billing_configuration_http_exception() from error


def _authenticated_user_id(auth: AuthResult, *, request_id: str) -> UUID:
    with _db_uow() as db_session:
        identity = _resolve_identity(
            auth=auth,
            request_id=request_id,
            db_session=db_session,
        )
        return identity.user_id


@router.post(
    "/checkout-session",
    response_model=CheckoutSessionResponseDTO,
)
async def checkout_session(
    payload: CheckoutSessionRequest,
    request: Request,
    auth: AuthResult = Depends(get_auth),
):
    request_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=request_id)

    try:
        config = require_stripe_billing_config()
        if not API_DB_ENABLED:
            raise billing_database_required_http_exception()
        redirect = await create_checkout_redirect(
            uow_factory=_db_uow,
            gateway=_gateway_factory(config),
            config=config,
            user_id=_authenticated_user_id(auth, request_id=request_id),
            plan_code=payload.plan_code,
            billing_period=payload.billing_period,
        )
    except (
        BillingConfigurationError,
        BillingIdentityError,
        BillingNotConfiguredError,
        BillingPlanSelectionError,
        BillingProviderError,
        StripeCustomerRequiredError,
    ) as exc:
        _raise_billing_http_error(exc, request_id=request_id)
        raise AssertionError("unreachable") from exc

    return CheckoutSessionResponseDTO(
        checkout_url=redirect.url,
        destination=redirect.destination,
    )


@router.post(
    "/portal-session",
    response_model=PortalSessionResponseDTO,
)
async def portal_session(
    request: Request,
    payload: PortalSessionRequest | None = Body(default=None),
    auth: AuthResult = Depends(get_auth),
):
    del payload
    request_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=request_id)

    try:
        config = require_stripe_billing_config()
        if not API_DB_ENABLED:
            raise billing_database_required_http_exception()
        redirect = await create_portal_redirect(
            uow_factory=_db_uow,
            gateway=_gateway_factory(config),
            user_id=_authenticated_user_id(auth, request_id=request_id),
        )
    except (
        BillingConfigurationError,
        BillingIdentityError,
        BillingNotConfiguredError,
        BillingPlanSelectionError,
        BillingProviderError,
        StripeCustomerRequiredError,
    ) as exc:
        _raise_billing_http_error(exc, request_id=request_id)
        raise AssertionError("unreachable") from exc

    return PortalSessionResponseDTO(portal_url=redirect.url)
