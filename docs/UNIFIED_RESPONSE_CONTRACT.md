# Unified Response Contract

## Purpose

All provider adapters must return one normalized object shape so route handlers, orchestration, and persistence never depend on provider-specific SDK payloads.

## Contract Model

Primary model: `models/unified_response.py`

- `TokenUsage`
  - `prompt_tokens`
  - `completion_tokens`
  - `total_tokens`
- `NormalizedError`
  - `code`
  - `message`
  - `provider`
  - `retryable`
  - `details`
- `UnifiedResponse`
  - `request_id`
  - `text`
  - `provider`
  - `model`
  - `latency_ms`
  - `token_usage`
  - `estimated_cost`
  - `finish_reason`
  - `error`
  - `metadata`
  - `raw` (optional, debug/full-save only)

## Current Provider Coverage

Adapters returning `UnifiedResponse`:

- `api/openai_client.py`
- `api/google_gemini_client.py`
- `api/deepseek_client.py`
- `api/grok_client.py`
- `api/claude_client.py`

## Non-Negotiable Rules

1. Provider clients must return `UnifiedResponse` on both success and failure paths.
2. Error paths must be represented via `UnifiedResponse.error` (normalized), not provider-native exceptions leaking upward.
3. `token_usage` must always be present (zeros allowed when unavailable).
4. `finish_reason` must be normalized into shared values (`stop`, `length`, `tool`, `content_filter`, `error`, or `null`).

## Error Normalization

Base mapping logic lives in `api/base_client.py`.

Normalized error codes:

- `timeout`
- `auth`
- `rate_limit`
- `bad_request`
- `provider_error`
- `unknown`

The `retryable` flag is derived from normalized semantics and used by fallback/retry paths.

Provider-native exception text is not exposed directly as the client-facing
`error.message`. Adapters classify failures into stable `error.details.kind`
values while preserving the public error-code set above:

- `transient_capacity` for temporary 503/high-demand/overloaded/unavailable failures; client copy is `This model is temporarily busy. Try again shortly or switch to another model.`
- `rate_limited` for retryable provider throttling
- `quota_exceeded` for billing or hard quota exhaustion
- `timeout`
- `auth`
- `bad_request`
- `provider_5xx`
- `unknown`

Routes apply a final `server/utils.py` sanitization pass before DTO or stream
output, and frontend rendering applies the same safe-copy mapping for older
persisted history entries.

## Route/Orchestrator Guardrails Tied to Contract

- Route-level `max_tokens` clamps in `server/utils.py` (current cap: `2048`).
- Empty-success normalization in `server/utils.py` converts blank `finish_reason=length` payloads into provider errors for safe retry/fallback behavior.
- Provider availability errors are sanitized in `server/utils.py` so manual Ask, Compare, and streaming cards never render raw upstream JSON. Smart routing still uses retryable provider errors for its existing fallback path, and frontend response cards render transient capacity failures with `.model-soft-error`.
- OpenAI compatibility retry (`max_tokens` -> `max_completion_tokens`) is handled in `api/openai_client.py` for models that reject legacy parameter shapes.

## Validation Tests

Primary contract and regression coverage:

- `tests/test_unified_response_contract.py`
- `tests/test_fastapi_contract_and_guardrails.py`
- `tests/test_server_utils.py`
- `tests/test_routing_regression.py`
- `tests/test_api_persistence_guardrails.py`

## Related Docs

- API behavior and route contracts: `docs/FASTAPI_README.md`
- High-level project runtime and workflows: `README.md`
- Smart routing decision flow: `docs/SMART_ROUTING_DIAGRAM.md`

---

Last updated: 2026-03-19
