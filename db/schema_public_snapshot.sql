-- Auto-generated from live database schema (public)
-- Generated for local bootstrap/testing
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    CREATE TYPE public.prompt_category AS ENUM ('coding', 'financial', 'educational', 'math', 'legal', 'data_technical', 'general', 'unknown');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


CREATE TABLE public.users (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	email TEXT, 
	display_name TEXT, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	auth_provider TEXT, 
	auth_subject TEXT, 
	auth_issuer TEXT, 
	CONSTRAINT users_pkey PRIMARY KEY (id), 
	CONSTRAINT users_email_key UNIQUE NULLS DISTINCT (email)
);


CREATE TABLE public.api_keys (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	key_hash TEXT NOT NULL, 
	label TEXT, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	last_used_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT api_keys_pkey PRIMARY KEY (id), 
	CONSTRAINT api_keys_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE, 
	CONSTRAINT api_keys_key_hash_key UNIQUE NULLS DISTINCT (key_hash)
);


CREATE TABLE public.sessions (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	title TEXT, 
	mode TEXT DEFAULT 'ask'::text NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT sessions_pkey PRIMARY KEY (id), 
	CONSTRAINT sessions_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE, 
	CONSTRAINT sessions_mode_check CHECK (mode = ANY (ARRAY['ask'::text, 'compare'::text, 'eval'::text, 'research'::text]))
);


CREATE TABLE public.usage_daily (
	user_id UUID NOT NULL, 
	usage_date DATE NOT NULL, 
	total_requests INTEGER DEFAULT 0 NOT NULL, 
	total_tokens INTEGER DEFAULT 0 NOT NULL, 
	total_cost NUMERIC(12, 6) DEFAULT 0 NOT NULL, 
	CONSTRAINT usage_daily_pkey PRIMARY KEY (user_id, usage_date), 
	CONSTRAINT usage_daily_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE
);


CREATE TABLE public.user_preferences (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	default_mode TEXT, 
	default_provider TEXT, 
	default_model TEXT, 
	cost_bias TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT user_preferences_pkey PRIMARY KEY (id), 
	CONSTRAINT user_preferences_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE, 
	CONSTRAINT user_preferences_user_id_key UNIQUE NULLS DISTINCT (user_id)
);


CREATE TABLE public.wallets (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	currency TEXT DEFAULT 'CAD'::text NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT wallets_pkey PRIMARY KEY (id), 
	CONSTRAINT wallets_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE, 
	CONSTRAINT wallets_user_id_key UNIQUE NULLS DISTINCT (user_id)
);


CREATE TABLE public.ledger_entries (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	wallet_id UUID NOT NULL, 
	ledger_type TEXT NOT NULL, 
	amount NUMERIC(12, 6) NOT NULL, 
	reference TEXT, 
	note TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT ledger_entries_pkey PRIMARY KEY (id), 
	CONSTRAINT ledger_entries_wallet_id_fkey FOREIGN KEY(wallet_id) REFERENCES public.wallets (id) ON DELETE CASCADE
);


CREATE TABLE public.llm_requests (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	session_id UUID, 
	request_id TEXT NOT NULL, 
	route_mode TEXT DEFAULT 'ask'::text NOT NULL, 
	provider TEXT NOT NULL, 
	model TEXT NOT NULL, 
	requested_model TEXT,
	prompt_sha256 TEXT, 
	prompt_stored BOOLEAN DEFAULT false NOT NULL, 
	prompt_text TEXT, 
	input_tokens_est INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	api_key_id UUID, 
	request_group_id UUID, 
	response_revision_root_id UUID,
	response_revision INTEGER DEFAULT 1 NOT NULL,
	generation_profile TEXT,
	requested_max_output_tokens INTEGER,
	effective_max_output_tokens INTEGER,
	requested_reasoning_mode TEXT,
	effective_reasoning_mode TEXT,
	requested_reasoning_effort TEXT,
	effective_reasoning_effort TEXT,
	generation_policy_version TEXT,
	CONSTRAINT llm_requests_pkey PRIMARY KEY (id), 
	CONSTRAINT llm_requests_api_key_id_fkey FOREIGN KEY(api_key_id) REFERENCES public.api_keys (id) ON DELETE SET NULL, 
	CONSTRAINT llm_requests_response_revision_root_id_fkey FOREIGN KEY(response_revision_root_id) REFERENCES public.llm_requests (id) ON DELETE CASCADE,
	CONSTRAINT llm_requests_session_id_fkey FOREIGN KEY(session_id) REFERENCES public.sessions (id) ON DELETE SET NULL, 
	CONSTRAINT llm_requests_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE, 
	CONSTRAINT llm_requests_request_id_key UNIQUE NULLS DISTINCT (request_id), 
	CONSTRAINT llm_requests_route_mode_check CHECK (route_mode = ANY (ARRAY['ask'::text, 'compare'::text, 'eval'::text, 'research'::text])),
	CONSTRAINT llm_requests_response_revision_check CHECK (response_revision >= 1),
	CONSTRAINT llm_requests_requested_max_output_tokens_check CHECK (requested_max_output_tokens IS NULL OR requested_max_output_tokens > 0),
	CONSTRAINT llm_requests_effective_max_output_tokens_check CHECK (effective_max_output_tokens IS NULL OR effective_max_output_tokens > 0)
);


CREATE TABLE public.messages (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	session_id UUID NOT NULL, 
	role TEXT NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	is_edited BOOLEAN DEFAULT false NOT NULL, 
	edited_at TIMESTAMP WITH TIME ZONE, 
	replaced_by_message_id UUID, 
	CONSTRAINT messages_pkey PRIMARY KEY (id), 
	CONSTRAINT messages_replaced_by_message_id_fkey FOREIGN KEY(replaced_by_message_id) REFERENCES public.messages (id) ON DELETE SET NULL, 
	CONSTRAINT messages_session_id_fkey FOREIGN KEY(session_id) REFERENCES public.sessions (id) ON DELETE CASCADE
);


CREATE TABLE public.context_snapshots (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	base_message_id UUID, 
	context_hash TEXT NOT NULL, 
	context_text TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT context_snapshots_pkey PRIMARY KEY (id), 
	CONSTRAINT context_snapshots_base_message_id_fkey FOREIGN KEY(base_message_id) REFERENCES public.messages (id) ON DELETE SET NULL, 
	CONSTRAINT context_snapshots_session_id_fkey FOREIGN KEY(session_id) REFERENCES public.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT context_snapshots_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE
);


CREATE TABLE public.feedback (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	user_id UUID NOT NULL, 
	session_id UUID, 
	llm_request_id UUID, 
	rating INTEGER, 
	comment TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT feedback_pkey PRIMARY KEY (id), 
	CONSTRAINT feedback_llm_request_id_fkey FOREIGN KEY(llm_request_id) REFERENCES public.llm_requests (id) ON DELETE SET NULL, 
	CONSTRAINT feedback_session_id_fkey FOREIGN KEY(session_id) REFERENCES public.sessions (id) ON DELETE SET NULL, 
	CONSTRAINT feedback_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE
);


CREATE TABLE public.llm_responses (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	llm_request_id UUID NOT NULL, 
	text TEXT, 
	finish_reason TEXT, 
	latency_ms INTEGER, 
	prompt_tokens INTEGER, 
	completion_tokens INTEGER, 
	total_tokens INTEGER, 
	estimated_cost NUMERIC(12, 6), 
	served_model TEXT,
	pricing_model TEXT,
	model_lifecycle_status TEXT,
	alias_redirected BOOLEAN DEFAULT false NOT NULL,
	replacement_model TEXT,
	model_migration_reason TEXT,
	reasoning_mode TEXT,
	cached_input_tokens INTEGER DEFAULT 0 NOT NULL,
	cache_write_tokens INTEGER DEFAULT 0 NOT NULL,
	reasoning_tokens INTEGER DEFAULT 0 NOT NULL,
	pricing_rule_applied TEXT,
	pricing_version TEXT,
	pricing_unknown BOOLEAN DEFAULT false NOT NULL,
	pricing_snapshot JSONB DEFAULT '{}'::jsonb NOT NULL,
	completion_status TEXT DEFAULT 'complete'::text NOT NULL,
	stop_cause TEXT DEFAULT 'unknown'::text NOT NULL,
	error_type TEXT, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT llm_responses_pkey PRIMARY KEY (id), 
	CONSTRAINT llm_responses_llm_request_id_fkey FOREIGN KEY(llm_request_id) REFERENCES public.llm_requests (id) ON DELETE CASCADE, 
	CONSTRAINT llm_responses_llm_request_id_key UNIQUE NULLS DISTINCT (llm_request_id),
	CONSTRAINT llm_responses_completion_status_check CHECK (completion_status = ANY (ARRAY['complete'::text, 'incomplete'::text, 'failed'::text])),
	CONSTRAINT llm_responses_stop_cause_check CHECK (stop_cause = ANY (ARRAY['natural'::text, 'token_limit'::text, 'context_limit'::text, 'content_filter'::text, 'error'::text, 'unknown'::text]))
);


CREATE TABLE public.cortex_analysis_runs (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	session_id UUID NOT NULL,
	request_group_id UUID NOT NULL,
	model TEXT NOT NULL,
	source_fingerprint TEXT NOT NULL,
	source_snapshot JSONB DEFAULT '[]'::jsonb NOT NULL,
	recommended_answer TEXT NOT NULL,
	agreements JSONB DEFAULT '[]'::jsonb NOT NULL,
	disagreements JSONB DEFAULT '[]'::jsonb NOT NULL,
	disagreement_note TEXT,
	unique_insights JSONB DEFAULT '[]'::jsonb NOT NULL,
	confidence_level TEXT NOT NULL,
	confidence_reason TEXT NOT NULL,
	verify_items JSONB DEFAULT '[]'::jsonb NOT NULL,
	high_stakes_domain TEXT,
	combined_response_count INTEGER NOT NULL,
	failed_response_count INTEGER DEFAULT 0 NOT NULL,
	prompt_tokens INTEGER DEFAULT 0 NOT NULL,
	completion_tokens INTEGER DEFAULT 0 NOT NULL,
	total_tokens INTEGER DEFAULT 0 NOT NULL,
	estimated_cost NUMERIC(12, 6) DEFAULT 0 NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT cortex_analysis_runs_pkey PRIMARY KEY (id),
	CONSTRAINT cortex_analysis_runs_user_id_fkey FOREIGN KEY(user_id) REFERENCES public.users (id) ON DELETE CASCADE,
	CONSTRAINT cortex_analysis_runs_session_id_fkey FOREIGN KEY(session_id) REFERENCES public.sessions (id) ON DELETE CASCADE,
	CONSTRAINT cortex_analysis_runs_confidence_level_check CHECK (confidence_level = ANY (ARRAY['limited'::text, 'moderate'::text, 'high'::text])),
	CONSTRAINT cortex_analysis_runs_high_stakes_domain_check CHECK (high_stakes_domain IS NULL OR high_stakes_domain = ANY (ARRAY['financial'::text, 'medical'::text, 'legal'::text, 'safety'::text])),
	CONSTRAINT cortex_analysis_runs_combined_response_count_check CHECK (combined_response_count BETWEEN 2 AND 3),
	CONSTRAINT cortex_analysis_runs_failed_response_count_check CHECK (failed_response_count >= 0)
);


CREATE TABLE public.routing_decisions (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	llm_request_id UUID NOT NULL, 
	prompt_category prompt_category DEFAULT 'unknown'::prompt_category NOT NULL, 
	research_mode TEXT DEFAULT 'off'::text NOT NULL, 
	routing_mode TEXT DEFAULT 'smart'::text NOT NULL, 
	initial_tier TEXT, 
	final_tier TEXT, 
	attempt_count INTEGER DEFAULT 1 NOT NULL, 
	fallback_used BOOLEAN DEFAULT false NOT NULL, 
	decision_reasons TEXT[] DEFAULT ARRAY[]::text[] NOT NULL, 
	features JSONB DEFAULT '{}'::jsonb NOT NULL, 
	trace JSONB DEFAULT '{}'::jsonb NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT routing_decisions_pkey PRIMARY KEY (id), 
	CONSTRAINT routing_decisions_llm_request_id_fkey FOREIGN KEY(llm_request_id) REFERENCES public.llm_requests (id) ON DELETE CASCADE, 
	CONSTRAINT routing_decisions_llm_request_id_key UNIQUE NULLS DISTINCT (llm_request_id), 
	CONSTRAINT routing_decisions_attempt_count_check CHECK (attempt_count >= 1), 
	CONSTRAINT routing_decisions_research_mode_check CHECK (research_mode = ANY (ARRAY['off'::text, 'auto'::text, 'on'::text])), 
	CONSTRAINT routing_decisions_routing_mode_check CHECK (routing_mode = ANY (ARRAY['smart'::text, 'cheap'::text, 'strong'::text, 'explicit'::text, 'legacy'::text]))
);


CREATE TABLE public.routing_attempts (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	routing_decision_id UUID NOT NULL, 
	attempt_number INTEGER NOT NULL, 
	tier TEXT, 
	provider TEXT, 
	model TEXT, 
	validation TEXT, 
	latency_ms INTEGER, 
	error_type TEXT, 
	error_message TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT routing_attempts_pkey PRIMARY KEY (id), 
	CONSTRAINT routing_attempts_routing_decision_id_fkey FOREIGN KEY(routing_decision_id) REFERENCES public.routing_decisions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_routing_attempts_decision_attempt_number UNIQUE NULLS DISTINCT (routing_decision_id, attempt_number), 
	CONSTRAINT routing_attempts_attempt_number_check CHECK (attempt_number >= 1)
);

CREATE INDEX idx_api_keys_user_id ON public.api_keys USING btree (user_id);
CREATE INDEX idx_context_snapshots_user_session_time ON public.context_snapshots USING btree (user_id, session_id, created_at DESC);
CREATE UNIQUE INDEX uq_context_snapshots_session_hash ON public.context_snapshots USING btree (session_id, context_hash);
CREATE INDEX idx_feedback_request ON public.feedback USING btree (llm_request_id);
CREATE INDEX idx_feedback_user_time ON public.feedback USING btree (user_id, created_at DESC);
CREATE INDEX idx_ledger_reference ON public.ledger_entries USING btree (reference);
CREATE INDEX idx_ledger_wallet_time ON public.ledger_entries USING btree (wallet_id, created_at DESC);
CREATE INDEX idx_llm_requests_api_key_time ON public.llm_requests USING btree (api_key_id, created_at DESC);
CREATE INDEX idx_llm_requests_provider_model_time ON public.llm_requests USING btree (provider, model, created_at DESC);
CREATE INDEX idx_llm_requests_request_group_id ON public.llm_requests USING btree (request_group_id) WHERE (request_group_id IS NOT NULL);
CREATE INDEX idx_llm_requests_response_revision_root ON public.llm_requests USING btree (response_revision_root_id, response_revision DESC) WHERE (response_revision_root_id IS NOT NULL);
CREATE UNIQUE INDEX uq_llm_requests_logical_response_revision ON public.llm_requests USING btree (COALESCE(response_revision_root_id, id), response_revision);
CREATE INDEX idx_llm_requests_session_time ON public.llm_requests USING btree (session_id, created_at DESC);
CREATE INDEX idx_llm_requests_user_request_group_id ON public.llm_requests USING btree (user_id, request_group_id) WHERE (request_group_id IS NOT NULL);
CREATE INDEX idx_llm_requests_user_time ON public.llm_requests USING btree (user_id, created_at DESC);
CREATE INDEX idx_llm_responses_request_id ON public.llm_responses USING btree (llm_request_id);
CREATE INDEX idx_cortex_analysis_runs_user_group_time ON public.cortex_analysis_runs USING btree (user_id, request_group_id, created_at DESC);
CREATE INDEX idx_cortex_analysis_runs_user_session_time ON public.cortex_analysis_runs USING btree (user_id, session_id, created_at DESC);
CREATE INDEX idx_messages_session_id ON public.messages USING btree (session_id);
CREATE INDEX idx_messages_session_time ON public.messages USING btree (session_id, created_at);
CREATE INDEX idx_routing_attempts_decision_id ON public.routing_attempts USING btree (routing_decision_id);
CREATE INDEX idx_routing_attempts_provider_model_time ON public.routing_attempts USING btree (provider, model, created_at);
CREATE INDEX idx_routing_attempts_validation_time ON public.routing_attempts USING btree (validation, created_at);
CREATE INDEX idx_routing_decisions_category_time ON public.routing_decisions USING btree (prompt_category, created_at);
CREATE INDEX idx_routing_decisions_llm_request_id ON public.routing_decisions USING btree (llm_request_id);
CREATE INDEX idx_routing_decisions_mode_time ON public.routing_decisions USING btree (routing_mode, research_mode, created_at);
CREATE INDEX idx_sessions_user_id ON public.sessions USING btree (user_id);
CREATE INDEX idx_sessions_user_updated ON public.sessions USING btree (user_id, updated_at DESC);
CREATE UNIQUE INDEX uq_users_auth_subject ON public.users USING btree (auth_provider, auth_issuer, auth_subject) WHERE (auth_subject IS NOT NULL);

COMMIT;
