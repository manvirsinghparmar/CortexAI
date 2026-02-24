BEGIN;

-- Per-API-key runtime settings (baseline model, optional key-scoped RPM override).
CREATE TABLE IF NOT EXISTS public.api_key_settings (
    api_key_id uuid PRIMARY KEY REFERENCES public.api_keys(id) ON DELETE CASCADE,
    baseline_provider text NULL,
    baseline_model text NULL,
    requests_per_minute integer NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW()
);

-- Encrypted BYOK credentials at rest (never store raw secret plaintext).
CREATE TABLE IF NOT EXISTS public.byok_provider_keys (
    api_key_id uuid NOT NULL REFERENCES public.api_keys(id) ON DELETE CASCADE,
    provider text NOT NULL,
    encrypted_key text NOT NULL,
    key_fingerprint text NOT NULL,
    key_last4 text NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    PRIMARY KEY (api_key_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_byok_provider_keys_api_key_id
    ON public.byok_provider_keys (api_key_id);

-- Savings telemetry keyed per llm request.
CREATE TABLE IF NOT EXISTS public.llm_savings (
    llm_request_id uuid PRIMARY KEY REFERENCES public.llm_requests(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    api_key_id uuid NULL REFERENCES public.api_keys(id),
    usage_date date NOT NULL DEFAULT CURRENT_DATE,
    provider text NOT NULL,
    model text NOT NULL,
    actual_cost numeric(18, 8) NOT NULL DEFAULT 0,
    baseline_provider text NOT NULL,
    baseline_model text NOT NULL,
    baseline_cost numeric(18, 8) NOT NULL DEFAULT 0,
    savings_amount numeric(18, 8) NOT NULL DEFAULT 0,
    savings_pct numeric(10, 6) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_savings_usage_date
    ON public.llm_savings (usage_date);

CREATE INDEX IF NOT EXISTS idx_llm_savings_user_usage_date
    ON public.llm_savings (user_id, usage_date);

CREATE INDEX IF NOT EXISTS idx_llm_savings_api_key_usage_date
    ON public.llm_savings (api_key_id, usage_date);

COMMIT;
