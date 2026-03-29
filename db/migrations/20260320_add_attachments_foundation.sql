BEGIN;

CREATE TABLE IF NOT EXISTS public.uploaded_files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    api_key_id uuid NULL REFERENCES public.api_keys(id) ON DELETE SET NULL,
    original_filename text NOT NULL,
    mime_type text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    sha256 text NOT NULL,
    storage_bucket text NOT NULL,
    storage_key text NOT NULL,
    status text NOT NULL DEFAULT 'uploaded',
    error_code text NULL,
    error_message text NULL,
    ingestion_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    expires_at timestamptz NULL,
    deleted_at timestamptz NULL,
    CONSTRAINT uploaded_files_status_check CHECK (
        status = ANY (
            ARRAY[
                'uploaded'::text,
                'processing'::text,
                'ready'::text,
                'failed'::text,
                'expired'::text,
                'deleted'::text
            ]
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_status_created_at
    ON public.uploaded_files (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_sha_size_active
    ON public.uploaded_files (user_id, sha256, size_bytes)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_uploaded_files_user_storage_key
    ON public.uploaded_files (user_id, storage_bucket, storage_key);

CREATE TABLE IF NOT EXISTS public.request_attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    llm_request_id uuid NOT NULL REFERENCES public.llm_requests(id) ON DELETE CASCADE,
    file_id uuid NOT NULL REFERENCES public.uploaded_files(id) ON DELETE CASCADE,
    order_index integer NOT NULL CHECK (order_index >= 0),
    usage_role text NOT NULL DEFAULT 'primary',
    transform_mode text NOT NULL DEFAULT 'auto',
    resolved_artifact_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT request_attachments_usage_role_check CHECK (
        usage_role = ANY (ARRAY['primary'::text, 'reference'::text])
    ),
    CONSTRAINT request_attachments_transform_mode_check CHECK (
        transform_mode = ANY (
            ARRAY[
                'auto'::text,
                'text_only'::text,
                'vision_pages'::text,
                'table_summary'::text
            ]
        )
    ),
    CONSTRAINT uq_request_attachments_request_order UNIQUE (llm_request_id, order_index)
);

CREATE INDEX IF NOT EXISTS idx_request_attachments_request_order
    ON public.request_attachments (llm_request_id, order_index);

CREATE INDEX IF NOT EXISTS idx_request_attachments_file_id
    ON public.request_attachments (file_id);

CREATE TABLE IF NOT EXISTS public.file_deletion_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id uuid NOT NULL REFERENCES public.uploaded_files(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error text NULL,
    available_at timestamptz NOT NULL DEFAULT NOW(),
    locked_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT file_deletion_queue_status_check CHECK (
        status = ANY (
            ARRAY[
                'pending'::text,
                'in_progress'::text,
                'retry'::text,
                'succeeded'::text,
                'failed'::text
            ]
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_file_deletion_queue_status_available_at
    ON public.file_deletion_queue (status, available_at);

CREATE INDEX IF NOT EXISTS idx_file_deletion_queue_file_id
    ON public.file_deletion_queue (file_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_file_deletion_queue_active_file
    ON public.file_deletion_queue (file_id)
    WHERE status = ANY (ARRAY['pending'::text, 'in_progress'::text, 'retry'::text]);

COMMIT;
