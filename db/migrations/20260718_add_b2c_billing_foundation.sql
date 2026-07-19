BEGIN;

-- Stable billing owner abstraction. owner_id is intentionally polymorphic and
-- therefore is validated by application services rather than a foreign key.
CREATE TABLE IF NOT EXISTS public.billing_accounts (
    id uuid PRIMARY KEY,
    owner_type varchar(32) NOT NULL,
    owner_id uuid NOT NULL,
    stripe_customer_id varchar(255) NULL,
    currency varchar(3) NOT NULL DEFAULT 'USD',
    country varchar(2) NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_billing_accounts_owner_type
        CHECK (owner_type IN ('user', 'organization')),
    CONSTRAINT uq_billing_accounts_owner
        UNIQUE (owner_type, owner_id),
    CONSTRAINT uq_billing_accounts_stripe_customer
        UNIQUE (stripe_customer_id)
);

CREATE TABLE IF NOT EXISTS public.subscriptions (
    id uuid PRIMARY KEY,
    billing_account_id uuid NOT NULL REFERENCES public.billing_accounts(id),
    provider varchar(32) NOT NULL DEFAULT 'stripe',
    provider_subscription_id varchar(255) NULL,
    provider_price_id varchar(255) NULL,
    plan_code varchar(64) NOT NULL,
    status varchar(64) NOT NULL,
    current_period_start timestamptz NULL,
    current_period_end timestamptz NULL,
    cancel_at_period_end boolean NOT NULL DEFAULT FALSE,
    canceled_at timestamptz NULL,
    trial_end timestamptz NULL,
    grace_until timestamptz NULL,
    latest_invoice_id varchar(255) NULL,
    last_provider_event_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_subscriptions_provider_id
        UNIQUE (provider, provider_subscription_id)
);

CREATE INDEX IF NOT EXISTS ix_subscriptions_account_status
    ON public.subscriptions (billing_account_id, status);

CREATE INDEX IF NOT EXISTS ix_subscriptions_period_end
    ON public.subscriptions (current_period_end);

-- These statuses represent one still-open provider lifecycle object. They do
-- not imply paid entitlement; WP3 resolves effective access conservatively.
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_one_live_per_account
    ON public.subscriptions (billing_account_id)
    WHERE status IN ('trialing', 'active', 'past_due', 'unpaid', 'paused', 'incomplete');

CREATE TABLE IF NOT EXISTS public.usage_periods (
    id uuid PRIMARY KEY,
    billing_account_id uuid NOT NULL REFERENCES public.billing_accounts(id),
    subscription_id uuid NULL REFERENCES public.subscriptions(id),
    plan_code varchar(64) NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_usage_period_dates
        CHECK (ends_at > starts_at),
    CONSTRAINT uq_usage_period_account_start
        UNIQUE (billing_account_id, starts_at)
);

CREATE INDEX IF NOT EXISTS ix_usage_periods_account_active
    ON public.usage_periods (billing_account_id, status, ends_at);

CREATE TABLE IF NOT EXISTS public.usage_counters (
    id uuid PRIMARY KEY,
    usage_period_id uuid NOT NULL REFERENCES public.usage_periods(id) ON DELETE CASCADE,
    meter_key varchar(64) NOT NULL,
    used_quantity bigint NOT NULL DEFAULT 0,
    reserved_quantity bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_usage_counter_nonnegative
        CHECK (used_quantity >= 0 AND reserved_quantity >= 0),
    CONSTRAINT uq_usage_counter_period_meter
        UNIQUE (usage_period_id, meter_key)
);

CREATE TABLE IF NOT EXISTS public.usage_reservations (
    id uuid PRIMARY KEY,
    billing_account_id uuid NOT NULL REFERENCES public.billing_accounts(id),
    usage_period_id uuid NOT NULL REFERENCES public.usage_periods(id),
    request_id varchar(255) NOT NULL,
    operation_type varchar(64) NOT NULL,
    state varchar(32) NOT NULL,
    requested_quantities jsonb NOT NULL,
    settled_quantities jsonb NULL,
    release_reason varchar(255) NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    settled_at timestamptz NULL,
    released_at timestamptz NULL,
    CONSTRAINT uq_usage_reservations_request
        UNIQUE (billing_account_id, request_id),
    CONSTRAINT ck_usage_reservation_state
        CHECK (state IN ('reserved', 'settled', 'released', 'expired'))
);

CREATE INDEX IF NOT EXISTS ix_usage_reservations_state_created
    ON public.usage_reservations (state, created_at);

CREATE TABLE IF NOT EXISTS public.billing_webhook_events (
    id uuid PRIMARY KEY,
    provider varchar(32) NOT NULL DEFAULT 'stripe',
    provider_event_id varchar(255) NOT NULL,
    event_type varchar(255) NOT NULL,
    payload_hash varchar(64) NOT NULL,
    processing_status varchar(32) NOT NULL,
    received_at timestamptz NOT NULL DEFAULT NOW(),
    processed_at timestamptz NULL,
    error_message text NULL,
    CONSTRAINT uq_billing_webhook_provider_event
        UNIQUE (provider, provider_event_id),
    CONSTRAINT ck_billing_webhook_status
        CHECK (processing_status IN ('received', 'processed', 'ignored', 'failed'))
);

COMMIT;
