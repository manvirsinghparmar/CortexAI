BEGIN;

-- Itemized, immutable reconciliation detail for the single public AI-credit
-- balance. Existing allowance rows are retained for audit/history but new
-- runtime writes use only usage_counters.meter_key = 'ai_credits'.
CREATE TABLE IF NOT EXISTS public.credit_transactions (
    id uuid PRIMARY KEY,
    billing_account_id uuid NOT NULL REFERENCES public.billing_accounts(id),
    usage_period_id uuid NOT NULL REFERENCES public.usage_periods(id) ON DELETE CASCADE,
    reservation_id uuid NULL REFERENCES public.usage_reservations(id),
    request_id varchar(255) NOT NULL,
    operation_type varchar(64) NOT NULL,
    item_index integer NOT NULL DEFAULT 0,
    item_type varchar(32) NOT NULL,
    provider varchar(64) NULL,
    model varchar(255) NULL,
    input_tokens bigint NOT NULL DEFAULT 0,
    output_tokens bigint NOT NULL DEFAULT 0,
    input_credits bigint NOT NULL DEFAULT 0,
    output_credits bigint NOT NULL DEFAULT 0,
    fixed_credits bigint NOT NULL DEFAULT 0,
    total_credits bigint NOT NULL,
    provider_cost_usd numeric(18, 8) NOT NULL DEFAULT 0,
    usage_estimated boolean NOT NULL DEFAULT FALSE,
    pricing_version varchar(64) NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_credit_transactions_nonnegative CHECK (
        item_index >= 0
        AND input_tokens >= 0
        AND output_tokens >= 0
        AND input_credits >= 0
        AND output_credits >= 0
        AND fixed_credits >= 0
        AND total_credits >= 0
        AND provider_cost_usd >= 0
    ),
    CONSTRAINT ck_credit_transactions_item_type CHECK (
        item_type IN ('model', 'research', 'adjustment')
    ),
    CONSTRAINT uq_credit_transactions_reservation_item
        UNIQUE (reservation_id, item_index)
);

CREATE INDEX IF NOT EXISTS ix_credit_transactions_account_created
    ON public.credit_transactions (billing_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_credit_transactions_period_created
    ON public.credit_transactions (usage_period_id, created_at DESC);

COMMIT;
