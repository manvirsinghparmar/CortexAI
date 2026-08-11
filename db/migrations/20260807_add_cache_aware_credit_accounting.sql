BEGIN;

ALTER TABLE public.credit_transactions
    ADD COLUMN IF NOT EXISTS normal_input_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cached_input_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_write_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reasoning_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS normal_input_credits bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cached_input_credits bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_write_credits bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS uncached_equivalent_credits bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_savings_credits bigint NOT NULL DEFAULT 0;

-- Historical rows predate cache-aware accounting and remain unchanged totals.
UPDATE public.credit_transactions
SET normal_input_tokens = input_tokens,
    cached_input_tokens = 0,
    cache_write_tokens = 0,
    reasoning_tokens = 0,
    normal_input_credits = input_credits,
    cached_input_credits = 0,
    cache_write_credits = 0,
    uncached_equivalent_credits = total_credits,
    cache_savings_credits = 0;

ALTER TABLE public.credit_transactions
    DROP CONSTRAINT IF EXISTS credit_transactions_normal_input_tokens_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_cached_input_tokens_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_cache_write_tokens_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_reasoning_tokens_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_normal_input_credits_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_cached_input_credits_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_cache_write_credits_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_uncached_equivalent_nonnegative,
    DROP CONSTRAINT IF EXISTS credit_transactions_cache_savings_nonnegative;

ALTER TABLE public.credit_transactions
    ADD CONSTRAINT credit_transactions_normal_input_tokens_nonnegative
        CHECK (normal_input_tokens >= 0),
    ADD CONSTRAINT credit_transactions_cached_input_tokens_nonnegative
        CHECK (cached_input_tokens >= 0),
    ADD CONSTRAINT credit_transactions_cache_write_tokens_nonnegative
        CHECK (cache_write_tokens >= 0),
    ADD CONSTRAINT credit_transactions_reasoning_tokens_nonnegative
        CHECK (reasoning_tokens >= 0),
    ADD CONSTRAINT credit_transactions_normal_input_credits_nonnegative
        CHECK (normal_input_credits >= 0),
    ADD CONSTRAINT credit_transactions_cached_input_credits_nonnegative
        CHECK (cached_input_credits >= 0),
    ADD CONSTRAINT credit_transactions_cache_write_credits_nonnegative
        CHECK (cache_write_credits >= 0),
    ADD CONSTRAINT credit_transactions_uncached_equivalent_nonnegative
        CHECK (uncached_equivalent_credits >= 0),
    ADD CONSTRAINT credit_transactions_cache_savings_nonnegative
        CHECK (cache_savings_credits >= 0);

ALTER TABLE public.cortex_analysis_runs
    ADD COLUMN IF NOT EXISTS analysis_policy_version text NOT NULL DEFAULT 'cortex-analysis-v1',
    ADD COLUMN IF NOT EXISTS cached_input_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_write_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reasoning_tokens bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pricing_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS pricing_version text;

ALTER TABLE public.cortex_analysis_runs
    DROP CONSTRAINT IF EXISTS cortex_analysis_runs_cached_input_tokens_nonnegative,
    DROP CONSTRAINT IF EXISTS cortex_analysis_runs_cache_write_tokens_nonnegative,
    DROP CONSTRAINT IF EXISTS cortex_analysis_runs_reasoning_tokens_nonnegative;

ALTER TABLE public.cortex_analysis_runs
    ADD CONSTRAINT cortex_analysis_runs_cached_input_tokens_nonnegative
        CHECK (cached_input_tokens >= 0),
    ADD CONSTRAINT cortex_analysis_runs_cache_write_tokens_nonnegative
        CHECK (cache_write_tokens >= 0),
    ADD CONSTRAINT cortex_analysis_runs_reasoning_tokens_nonnegative
        CHECK (reasoning_tokens >= 0);

CREATE INDEX IF NOT EXISTS idx_cortex_analysis_runs_reuse
ON public.cortex_analysis_runs (
    user_id,
    request_group_id,
    source_fingerprint,
    model,
    analysis_policy_version,
    created_at DESC
);

CREATE TABLE IF NOT EXISTS public.prompt_optimization_cache (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    cache_key text NOT NULL,
    optimizer_provider text NOT NULL,
    optimizer_model text NOT NULL,
    prompt_version text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    CONSTRAINT prompt_optimization_cache_pkey PRIMARY KEY (id),
    CONSTRAINT prompt_optimization_cache_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT uq_prompt_optimization_cache_user_key UNIQUE (user_id, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_prompt_optimization_cache_expiry
ON public.prompt_optimization_cache (expires_at);

CREATE TABLE IF NOT EXISTS public.research_reuse_cache (
    session_id text NOT NULL,
    state jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    CONSTRAINT research_reuse_cache_pkey PRIMARY KEY (session_id)
);

CREATE INDEX IF NOT EXISTS idx_research_reuse_cache_expiry
ON public.research_reuse_cache (expires_at);

CREATE TABLE IF NOT EXISTS public.cache_reuse_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    request_id varchar(255) NOT NULL,
    operation_type varchar(64) NOT NULL,
    reused boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT cache_reuse_events_pkey PRIMARY KEY (id),
    CONSTRAINT cache_reuse_events_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT cache_reuse_events_operation_type_check
        CHECK (operation_type IN ('research', 'prompt_optimization', 'cortex_analysis')),
    CONSTRAINT uq_cache_reuse_events_user_operation_request
        UNIQUE (user_id, operation_type, request_id)
);

CREATE INDEX IF NOT EXISTS idx_cache_reuse_events_user_created
ON public.cache_reuse_events (user_id, created_at DESC);

ALTER TABLE public.context_snapshots
    ADD COLUMN IF NOT EXISTS source_message_range text,
    ADD COLUMN IF NOT EXISTS source_hash text,
    ADD COLUMN IF NOT EXISTS summary_policy_version text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_context_snapshots_reusable_summary
ON public.context_snapshots (
    session_id,
    source_message_range,
    source_hash,
    summary_policy_version
)
WHERE source_hash IS NOT NULL;

COMMIT;
