BEGIN;

-- Persisted activity lets every API instance distinguish a crashed request
-- from a long-running request that is still actively using its reservation.
ALTER TABLE public.usage_reservations
    ADD COLUMN IF NOT EXISTS last_activity_at timestamptz;

UPDATE public.usage_reservations
SET last_activity_at = created_at
WHERE last_activity_at IS NULL;

ALTER TABLE public.usage_reservations
    ALTER COLUMN last_activity_at SET DEFAULT NOW();

ALTER TABLE public.usage_reservations
    ALTER COLUMN last_activity_at SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_usage_reservations_state_activity
    ON public.usage_reservations (state, last_activity_at);

COMMIT;
