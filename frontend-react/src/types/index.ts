// Mirrors server/schemas/requests.py and server/schemas/responses.py

// ── Requests ──────────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system";

export interface ConversationHistoryItem {
  role: MessageRole;
  content: string;
}

export interface UserContextRequest {
  session_id?: string;
  conversation_history?: ConversationHistoryItem[];
  new_session?: boolean;
}

export interface ChatRoutingRequest {
  smart_mode?: boolean;
  research_mode?: boolean;
}

export type AttachmentUsageRole = "primary" | "reference";
export type AttachmentTransformMode = "auto" | "text_only" | "vision_pages" | "table_summary";

export interface AttachmentRequestItem {
  file_id: string;
  usage_role?: AttachmentUsageRole;
  transform_mode?: AttachmentTransformMode;
}

export interface ChatRequest {
  prompt: string;
  provider?: string;
  model?: string;
  context?: UserContextRequest;
  routing?: ChatRoutingRequest;
  attachments?: AttachmentRequestItem[];
  temperature?: number;
  max_tokens?: number;
}

export interface CompareTargetRequest {
  provider: string;
  model?: string;
}

export interface CompareRequest {
  prompt: string;
  targets: CompareTargetRequest[];
  routing?: ChatRoutingRequest;
  context?: UserContextRequest;
  attachments?: AttachmentRequestItem[];
  timeout_s?: number;
  temperature?: number;
  max_tokens?: number;
}

// ── Responses ─────────────────────────────────────────────────────────────────

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ApiError {
  code: string;
  message: string;
  provider: string;
  retryable: boolean;
  details: Record<string, unknown>;
}

export interface WebSourceItem {
  title: string;
  url: string;
}

export interface ChatResponse {
  request_id: string;
  session_id?: string;
  text: string;
  provider: string;
  model: string;
  latency_ms: number;
  token_usage: TokenUsage;
  estimated_cost: number;
  cost_currency: string;
  finish_reason?: string;
  error?: ApiError;
  web_source_items: WebSourceItem[];
  timestamp: string;
}

export interface CompareResponse {
  request_group_id: string;
  session_id?: string;
  responses: ChatResponse[];
  success_count: number;
  error_count: number;
  total_tokens: number;
  total_cost: number;
  timestamp: string;
}

// ── Catalog ───────────────────────────────────────────────────────────────────

export interface ModelCatalogItem {
  provider: string;
  model: string;
  tier: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  context_limit: number;
  tags: string[];
  enabled: boolean;
  supports_image_input: boolean;
  supported_attachment_mime_types: string[];
  max_attachment_bytes?: number;
  max_attachments_per_request?: number;
}

export interface ProviderCatalogItem {
  provider: string;
  label: string;
  api_key_env: string;
  default_model_env: string;
  default_model: string;
  byok_supported: boolean;
  capabilities: string[];
  ui: Record<string, unknown>;
  model_count: number;
  enabled_model_count: number;
}

export interface ModelsCatalogResponse {
  provider?: string;
  enabled_only: boolean;
  models: ModelCatalogItem[];
  total: number;
  timestamp: string;
}

export interface ProvidersCatalogResponse {
  providers: ProviderCatalogItem[];
  total: number;
  timestamp: string;
}

// ── History ───────────────────────────────────────────────────────────────────

export interface HistoryEntry {
  id: number;
  session_id?: string;
  timestamp: string;
  mode: string;
  prompt: string;
  provider: string;
  model: string;
  response: string;
  latency_ms?: number;
  tokens?: number;
  cost?: number;
  web_source_items: WebSourceItem[];
}

// ── Files ──────────────────────────────────────────────────────────────────────

export interface FileUploadResponse {
  file_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  error_code?: string;
  error_message?: string;
  ingestion_meta: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  expires_at?: string;
  deduplicated: boolean;
}

// ── Auth / WhoAmI ─────────────────────────────────────────────────────────────

export interface CognitoConfig {
  enabled: boolean;
  client_id?: string;
  domain?: string;
  region?: string;
  redirect_uri?: string;
}

export interface WhoAmIBaseline {
  provider: string;
  model: string;
  source: string;
}

export interface WhoAmIRateLimitConfig {
  requests_per_minute: number;
  daily_cap_scope: string;
  daily_token_cap?: number;
  daily_cost_cap?: number;
}

export interface WhoAmIBreakerConfig {
  failure_threshold: number;
  window_seconds: number;
  cooldown_seconds: number;
  scope: string;
}

export interface WhoAmIResponse {
  api_key_id?: string;
  user_id?: string;
  plan_tier?: string;
  storage_policy: string;
  redact_pii: boolean;
  baseline: WhoAmIBaseline;
  rate_limits: WhoAmIRateLimitConfig;
  breakers: WhoAmIBreakerConfig;
}

// ── Optimize ──────────────────────────────────────────────────────────────────

export interface OptimizeRequest {
  prompt: string;
  context?: string;
}

export interface OptimizeResponse {
  optimized_prompt: string;
  original_prompt: string;
  provider: string;
  model: string;
  latency_ms: number;
}

// ── Smart-routing state ───────────────────────────────────────────────────────

export type ChatMode = "single" | "compare";

export interface ModelKey {
  provider: string;
  model: string;
}

export interface AppState {
  mode: ChatMode;
  smartMode: boolean;
  researchMode: boolean;
  optimizeMode: boolean;
  selectedModelKey: string;
  compareModelKeys: string[];
}

// ── SSE streaming ─────────────────────────────────────────────────────────────

export interface StreamChunk {
  type: "delta" | "done" | "error" | "metadata";
  text?: string;
  error?: string;
  metadata?: Partial<ChatResponse>;
}
