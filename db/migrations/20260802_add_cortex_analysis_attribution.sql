BEGIN;

-- Preserve the optional explanation that follows attributed disagreement
-- positions in the redesigned Cortex Analysis result document.
ALTER TABLE public.cortex_analysis_runs
ADD COLUMN IF NOT EXISTS disagreement_note text;

COMMIT;
