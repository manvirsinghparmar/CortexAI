BEGIN;

-- Defense-in-depth invariant:
-- If llm_requests.api_key_id is set, llm_requests.user_id must equal api_keys.user_id.
CREATE OR REPLACE FUNCTION public.enforce_llm_request_api_key_owner_match()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    key_owner uuid;
BEGIN
    IF NEW.api_key_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT ak.user_id
    INTO key_owner
    FROM public.api_keys AS ak
    WHERE ak.id = NEW.api_key_id;

    IF key_owner IS NULL THEN
        RAISE EXCEPTION 'api_key_id % does not exist', NEW.api_key_id
            USING ERRCODE = '23503';
    END IF;

    IF NEW.user_id IS DISTINCT FROM key_owner THEN
        RAISE EXCEPTION
            'llm_requests.user_id (%) must match api_keys.user_id (%) for api_key_id (%)',
            NEW.user_id,
            key_owner,
            NEW.api_key_id
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_llm_requests_enforce_api_key_owner ON public.llm_requests;

CREATE TRIGGER trg_llm_requests_enforce_api_key_owner
BEFORE INSERT OR UPDATE OF user_id, api_key_id
ON public.llm_requests
FOR EACH ROW
EXECUTE FUNCTION public.enforce_llm_request_api_key_owner_match();

COMMIT;
