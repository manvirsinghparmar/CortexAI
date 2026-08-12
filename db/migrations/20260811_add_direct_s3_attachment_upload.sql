-- Direct-to-S3 attachment upload lifecycle.
--
-- Upload intents exist before file bytes are available, so sha256 must remain
-- NULL until a future trusted hashing workflow populates it. The status check
-- adds the pre-upload and queued-deletion lifecycle states without removing any
-- existing states.

BEGIN;

ALTER TABLE public.uploaded_files
    ALTER COLUMN sha256 DROP NOT NULL;

ALTER TABLE public.uploaded_files
    DROP CONSTRAINT IF EXISTS uploaded_files_status_check;

ALTER TABLE public.uploaded_files
    ADD CONSTRAINT uploaded_files_status_check
    CHECK (
        status = ANY (
            ARRAY[
                'uploading'::text,
                'uploaded'::text,
                'processing'::text,
                'ready'::text,
                'failed'::text,
                'expired'::text,
                'deleting'::text,
                'deleted'::text
            ]
        )
    );

COMMIT;
