-- Additive audit contract for provider-aware generation budgets and stop status.

ALTER TABLE public.llm_requests
    ADD COLUMN IF NOT EXISTS generation_profile TEXT,
    ADD COLUMN IF NOT EXISTS requested_max_output_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS effective_max_output_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS requested_reasoning_mode TEXT,
    ADD COLUMN IF NOT EXISTS effective_reasoning_mode TEXT,
    ADD COLUMN IF NOT EXISTS requested_reasoning_effort TEXT,
    ADD COLUMN IF NOT EXISTS effective_reasoning_effort TEXT,
    ADD COLUMN IF NOT EXISTS generation_policy_version TEXT;

ALTER TABLE public.llm_requests
    DROP CONSTRAINT IF EXISTS llm_requests_requested_max_output_tokens_check;
ALTER TABLE public.llm_requests
    ADD CONSTRAINT llm_requests_requested_max_output_tokens_check
    CHECK (requested_max_output_tokens IS NULL OR requested_max_output_tokens > 0);

ALTER TABLE public.llm_requests
    DROP CONSTRAINT IF EXISTS llm_requests_effective_max_output_tokens_check;
ALTER TABLE public.llm_requests
    ADD CONSTRAINT llm_requests_effective_max_output_tokens_check
    CHECK (effective_max_output_tokens IS NULL OR effective_max_output_tokens > 0);

ALTER TABLE public.llm_responses
    ADD COLUMN IF NOT EXISTS completion_status TEXT,
    ADD COLUMN IF NOT EXISTS stop_cause TEXT;

UPDATE public.llm_responses
SET completion_status = CASE
        WHEN error_type IS NOT NULL THEN 'failed'
        WHEN finish_reason = 'length' THEN 'incomplete'
        ELSE 'complete'
    END,
    stop_cause = CASE
        WHEN error_type IS NOT NULL THEN 'error'
        WHEN finish_reason = 'length' THEN 'token_limit'
        WHEN finish_reason = 'content_filter' THEN 'content_filter'
        WHEN finish_reason IN ('stop', 'tool') THEN 'natural'
        ELSE 'unknown'
    END
WHERE completion_status IS NULL OR stop_cause IS NULL;

ALTER TABLE public.llm_responses
    ALTER COLUMN completion_status SET DEFAULT 'complete',
    ALTER COLUMN completion_status SET NOT NULL,
    ALTER COLUMN stop_cause SET DEFAULT 'unknown',
    ALTER COLUMN stop_cause SET NOT NULL;

ALTER TABLE public.llm_responses
    DROP CONSTRAINT IF EXISTS llm_responses_completion_status_check;
ALTER TABLE public.llm_responses
    ADD CONSTRAINT llm_responses_completion_status_check
    CHECK (completion_status IN ('complete', 'incomplete', 'failed'));

ALTER TABLE public.llm_responses
    DROP CONSTRAINT IF EXISTS llm_responses_stop_cause_check;
ALTER TABLE public.llm_responses
    ADD CONSTRAINT llm_responses_stop_cause_check
    CHECK (stop_cause IN (
        'natural', 'token_limit', 'context_limit', 'content_filter', 'error', 'unknown'
    ));
