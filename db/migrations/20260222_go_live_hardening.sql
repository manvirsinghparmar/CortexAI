BEGIN;

-- Mark savings rows with response outcome to keep failed responses auditable
-- and avoid ambiguous savings interpretation in reporting.
ALTER TABLE public.llm_savings
    ADD COLUMN IF NOT EXISTS response_status text NOT NULL DEFAULT 'success';

ALTER TABLE public.llm_savings
    ADD COLUMN IF NOT EXISTS error_code text NULL;

CREATE INDEX IF NOT EXISTS idx_llm_savings_response_status
    ON public.llm_savings (response_status);

-- Reporting paths rely on date-range scans by user/api key.
CREATE INDEX IF NOT EXISTS idx_llm_requests_user_created_at
    ON public.llm_requests (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_llm_requests_api_key_created_at
    ON public.llm_requests (api_key_id, created_at);

CREATE INDEX IF NOT EXISTS idx_llm_savings_user_created_at
    ON public.llm_savings (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_llm_savings_api_key_created_at
    ON public.llm_savings (api_key_id, created_at);

COMMIT;
