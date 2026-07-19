// Mirrors server/schemas/requests.py and server/schemas/responses.py.

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

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export type ResponseRunStatus =
  | "queued"
  | "optimizing"
  | "requesting"
  | "streaming"
  | "finalizing"
  | "complete"
  | "failed";

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
  latency_ms: number | null;
  token_usage: TokenUsage | null;
  estimated_cost: number;
  cost_currency: string;
  finish_reason?: string;
  error?: ApiError;
  web_source_items: WebSourceItem[];
  timestamp: string;
  ui_status?: ResponseRunStatus;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
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

export type ModelBillingClass = "standard" | "advanced" | "ultra";

export interface ModelCatalogItem {
  provider: string;
  model: string;
  tier: string;
  billing_class: ModelBillingClass;
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

export interface HistoryEntry {
  id: number;
  session_id?: string;
  session_title?: string;
  request_group_id?: string;
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

export type HistoryThreadMode = ChatMode | "mixed";

export interface HistoryThread {
  key: string;
  sessionId?: string;
  entries: HistoryEntry[];
  title: string;
  latestTimestamp: string;
  latestTimestampMs: number;
  mode: HistoryThreadMode;
  preferredMode: ChatMode;
  providerLabel: string;
  modelLabel: string;
  totalCost: number;
  totalTokens: number;
  turnCount: number;
  searchText: string;
}

export type FileUploadStatus = "ready" | "processing" | "failed" | string;

export interface FileUploadResponse {
  file_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  status: FileUploadStatus;
  error_code?: string;
  error_message?: string;
  ingestion_meta: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  expires_at?: string;
  deduplicated: boolean;
}

export interface CognitoConfig {
  enabled: boolean;
  client_id?: string;
  clientId?: string;
  domain?: string;
  region?: string;
  redirect_uri?: string;
  redirectUri?: string;
  logout_url?: string;
  logoutUrl?: string;
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

export interface UsageSummaryPeriod {
  from: string;
  to: string;
  label: string;
}

export interface UsageSummaryModel {
  provider: "openai" | "anthropic" | "deepseek" | "google" | "meta" | "mistral" | string;
  modelId: string;
  displayName: string;
  replies: number;
  viaSmart: number;
}

export interface UsageSummarySessionModes {
  askOnly: number;
  compareOnly: number;
  mixed: number;
}

export interface UsageActivityDay {
  date: string;
  tokens: number;
}

export interface UsageSummary {
  period: UsageSummaryPeriod;
  totalTokens: number;
  totalRequests: number;
  totalSessions: number;
  avgLatencyMs: number;
  p95LatencyMs: number;
  minLatencyMs: number;
  avgCostPerRequest: number;
  totalSpend: number;
  tokensDeltaPct: number;
  smartRoutedTotal: number;
  models: UsageSummaryModel[];
  sessionModes: UsageSummarySessionModes;
  switchedMidSession: number;
  activityDaily: UsageActivityDay[];
}

export interface OptimizeRequest {
  prompt: string;
  context_hint?: string;
  context?: UserContextRequest;
}

export interface OptimizeResponse {
  original_prompt: string;
  optimized_prompt: string;
  was_optimized: boolean;
  server_optimization_enabled: boolean;
  optimization_status: string;
  fallback_reason?: string;
}

export type ChatMode = "single" | "compare";
export type TurnStatus = "idle" | "optimizing" | "streaming" | "complete" | "error" | "cancelled";

export type PromptOptimizationUiStatus = "pending" | "optimized" | "kept_original" | "cancelled";

export interface PromptOptimizationState {
  status: PromptOptimizationUiStatus;
  originalPrompt: string;
  displayPrompt: string;
  note?: string;
  optimizationStatus?: string;
  fallbackReason?: string;
}

export interface ModelKey {
  provider: string;
  model: string;
}

export interface ChatTurn {
  id: string;
  mode: ChatMode;
  prompt: string;
  submittedPrompt: string;
  researchEnabled?: boolean;
  optimizeEnabled?: boolean;
  attachments: FileUploadResponse[];
  responses: ChatResponse[];
  status: TurnStatus;
  createdAt: string;
  requestGroupId?: string;
  compareSummary?: CompareResponse;
  optimization?: PromptOptimizationState;
}

export interface AppState {
  mode: ChatMode;
  smartMode: boolean;
  researchMode: boolean;
  compareResearchMode: boolean;
  optimizeMode: boolean;
  selectedModelKey: string;
  compareModelKeys: string[];
}

export interface StreamChunk {
  type: "delta" | "done" | "error" | "metadata" | "start";
  text?: string;
  error?: string;
  metadata?: Partial<ChatResponse>;
  provider?: string;
  model?: string;
  session_id?: string;
}

export interface CompareStreamChunk {
  type: "start" | "response_start" | "delta" | "response_done" | "done" | "error";
  index?: number;
  text?: string;
  error?: string;
  provider?: string;
  model?: string;
  response?: ChatResponse;
  compare?: CompareResponse;
  session_id?: string;
}
