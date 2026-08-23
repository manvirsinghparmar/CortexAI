BEGIN;

ALTER TABLE public.llm_requests
    ADD COLUMN IF NOT EXISTS requested_model TEXT;

UPDATE public.llm_requests
SET requested_model = model
WHERE requested_model IS NULL;

ALTER TABLE public.llm_responses
    ADD COLUMN IF NOT EXISTS served_model TEXT,
    ADD COLUMN IF NOT EXISTS pricing_model TEXT,
    ADD COLUMN IF NOT EXISTS model_lifecycle_status TEXT,
    ADD COLUMN IF NOT EXISTS alias_redirected BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS replacement_model TEXT,
    ADD COLUMN IF NOT EXISTS model_migration_reason TEXT,
    ADD COLUMN IF NOT EXISTS reasoning_mode TEXT,
    ADD COLUMN IF NOT EXISTS cached_input_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS pricing_rule_applied TEXT,
    ADD COLUMN IF NOT EXISTS pricing_version TEXT,
    ADD COLUMN IF NOT EXISTS pricing_unknown BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS pricing_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE public.llm_responses AS response
SET served_model = request.model,
    pricing_model = request.model,
    model_lifecycle_status = 'UNKNOWN',
    pricing_unknown = true
FROM public.llm_requests AS request
WHERE response.llm_request_id = request.id
  AND (
      response.served_model IS NULL
      OR response.pricing_model IS NULL
      OR response.model_lifecycle_status IS NULL
  );

UPDATE public.llm_responses
SET pricing_unknown = true
WHERE model_lifecycle_status = 'UNKNOWN'
  AND pricing_rule_applied IS NULL
  AND pricing_version IS NULL
  AND pricing_snapshot = '{}'::jsonb;

COMMENT ON COLUMN public.llm_requests.requested_model IS
    'Model identity selected by the caller before lifecycle migration or provider alias resolution.';
COMMENT ON COLUMN public.llm_responses.served_model IS
    'Provider-reported model identity that generated the response.';
COMMENT ON COLUMN public.llm_responses.pricing_model IS
    'Canonical model identity whose effective pricing rule was applied.';
COMMENT ON COLUMN public.llm_responses.pricing_snapshot IS
    'Immutable rule ID, rates, source URL, verification date, and request-specific pricing flags.';

COMMIT;
