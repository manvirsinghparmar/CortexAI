BEGIN;

-- Keep regenerated Compare responses attached to their original logical slot.
-- The original response has a NULL root and version 1. Every regeneration points
-- at that original row and increments the version without overwriting history.
ALTER TABLE public.llm_requests
ADD COLUMN IF NOT EXISTS response_revision_root_id uuid;

ALTER TABLE public.llm_requests
ADD COLUMN IF NOT EXISTS response_revision integer NOT NULL DEFAULT 1;

ALTER TABLE public.llm_requests
DROP CONSTRAINT IF EXISTS llm_requests_response_revision_root_id_fkey;

ALTER TABLE public.llm_requests
ADD CONSTRAINT llm_requests_response_revision_root_id_fkey
FOREIGN KEY (response_revision_root_id)
REFERENCES public.llm_requests (id)
ON DELETE CASCADE;

ALTER TABLE public.llm_requests
DROP CONSTRAINT IF EXISTS llm_requests_response_revision_check;

ALTER TABLE public.llm_requests
ADD CONSTRAINT llm_requests_response_revision_check
CHECK (response_revision >= 1);

CREATE INDEX IF NOT EXISTS idx_llm_requests_response_revision_root
ON public.llm_requests (response_revision_root_id, response_revision DESC)
WHERE response_revision_root_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_requests_logical_response_revision
ON public.llm_requests (
    (COALESCE(response_revision_root_id, id)),
    response_revision
);

CREATE TABLE IF NOT EXISTS public.cortex_analysis_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    session_id uuid NOT NULL,
    request_group_id uuid NOT NULL,
    model text NOT NULL,
    source_fingerprint text NOT NULL,
    source_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL,
    recommended_answer text NOT NULL,
    agreements jsonb DEFAULT '[]'::jsonb NOT NULL,
    disagreements jsonb DEFAULT '[]'::jsonb NOT NULL,
    unique_insights jsonb DEFAULT '[]'::jsonb NOT NULL,
    confidence_level text NOT NULL,
    confidence_reason text NOT NULL,
    verify_items jsonb DEFAULT '[]'::jsonb NOT NULL,
    high_stakes_domain text,
    combined_response_count integer NOT NULL,
    failed_response_count integer DEFAULT 0 NOT NULL,
    prompt_tokens integer DEFAULT 0 NOT NULL,
    completion_tokens integer DEFAULT 0 NOT NULL,
    total_tokens integer DEFAULT 0 NOT NULL,
    estimated_cost numeric(12, 6) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT cortex_analysis_runs_pkey PRIMARY KEY (id),
    CONSTRAINT cortex_analysis_runs_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES public.users (id) ON DELETE CASCADE,
    CONSTRAINT cortex_analysis_runs_session_id_fkey
        FOREIGN KEY (session_id) REFERENCES public.sessions (id) ON DELETE CASCADE,
    CONSTRAINT cortex_analysis_runs_confidence_level_check
        CHECK (confidence_level = ANY (ARRAY['limited'::text, 'moderate'::text, 'high'::text])),
    CONSTRAINT cortex_analysis_runs_high_stakes_domain_check
        CHECK (
            high_stakes_domain IS NULL
            OR high_stakes_domain = ANY (
                ARRAY['financial'::text, 'medical'::text, 'legal'::text, 'safety'::text]
            )
        ),
    CONSTRAINT cortex_analysis_runs_combined_response_count_check
        CHECK (combined_response_count BETWEEN 2 AND 3),
    CONSTRAINT cortex_analysis_runs_failed_response_count_check
        CHECK (failed_response_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cortex_analysis_runs_user_group_time
ON public.cortex_analysis_runs (user_id, request_group_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cortex_analysis_runs_user_session_time
ON public.cortex_analysis_runs (user_id, session_id, created_at DESC);

COMMIT;
