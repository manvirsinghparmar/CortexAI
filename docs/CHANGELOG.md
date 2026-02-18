# Changelog

All notable changes to OpenAIProject will be documented in this file.

## [Unreleased]

### Added
- API persistence guardrail tests:
  - `tests/test_api_persistence_guardrails.py`
  - compare request group migration sanity checks
- Dev key tooling:
  - `tools/register_dev_key.py` (zero-argument IDE-friendly key registration)
  - improved `tools/create_api_key.py` import-path behavior
- DB migrations:
  - `db/migrations/20260218_llm_requests_api_key_owner_guard.sql`
  - `db/migrations/20260218_add_request_group_id_to_llm_requests.sql`

### Changed
- FastAPI `/v1/chat` persistence flow now enforces key-owner attribution:
  - mapped key owner is authoritative for persisted `user_id`
  - safer unmapped-key defaults (`AUTO_REGISTER_UNMAPPED_API_KEYS=false`)
  - service-user fallback identity separated from CLI identity
- FastAPI `/v1/compare` now persists DB rows:
  - one `llm_requests`/`llm_responses` row per target response
  - shared `request_group_id` for grouped compare runs
- Canonical compare `request_group_id` now flows consistently across:
  - API response
  - orchestrator logs
  - `llm_requests.request_group_id`
- `create_llm_request(...)` supports optional `request_group_id` (schema-aware insert)
- Header redaction added for auth logs (`X-API-Key`, `Authorization`)

### Fixed
- OpenAI newer model compatibility:
  - auto-retry with `max_completion_tokens` when model rejects `max_tokens`
- Compare DTO mapping compatibility:
  - supports both `created_at` and `timestamp` MultiUnifiedResponse variants
- Prevented API key ownership mismatch corruption in persistence paths (app + DB trigger defense in depth)

## [2.0.0] - 2026-01-03

### Added
- **Grok (X.AI) Support**: Complete integration with grok-4-latest and other models
- **Cost Tracking System**: Real-time cost calculation with pricing data
  - Created `utils/cost_calculator.py` (separate from token tracking)
  - Created `config/pricing.py` with current pricing for all providers
  - Per-request and cumulative cost display
  - Session statistics with cost breakdown
- **Enhanced Documentation**: Comprehensive README and context files

### Changed
- Updated `TokenTracker` to optionally store model type/name
- Modified `main.py` to support cost tracking alongside token tracking
- Updated `.env` and `.env.example` with Grok configuration

### Technical Details
- Architecture: Token tracking and cost calculation are separate modules
- Pricing: Centralized in `config/pricing.py` (per million tokens)
- All clients use OpenAI SDK with custom base URLs

## [1.0.0] - 2025-12-XX

### Added
- Initial release with OpenAI, Gemini, and DeepSeek support
- Token tracking functionality
- Interactive CLI with loading animations
- Environment-based configuration

---

**Note**: For detailed architecture, see `.claude-context.md` and `PROJECT_MAP.md`
