BEGIN;

-- Grouping key for compare/multi-step runs:
-- multiple llm_requests rows can share one request_group_id.
ALTER TABLE public.llm_requests
ADD COLUMN IF NOT EXISTS request_group_id uuid;

-- Fast lookup by group id
CREATE INDEX IF NOT EXISTS idx_llm_requests_request_group_id
ON public.llm_requests (request_group_id)
WHERE request_group_id IS NOT NULL;

-- Common user-scoped lookup pattern
CREATE INDEX IF NOT EXISTS idx_llm_requests_user_request_group_id
ON public.llm_requests (user_id, request_group_id)
WHERE request_group_id IS NOT NULL;

COMMIT;
