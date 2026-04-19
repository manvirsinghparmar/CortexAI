# ADR 0002: Provider Validation and Safety Rails

- Status: Accepted
- Date: 2026-02-28
- Last reviewed: 2026-03-19 (decision unchanged)

## Context

Provider handling currently spans multiple layers:

- `server/schemas/requests.py` (request validation)
- `server/routes/chat.py` (provider normalization and execution planning)
- `server/byok_service.py` (BYOK provider allowlist and runtime key resolution)
- `orchestrator/core.py` (runtime invocation guardrails)

Without explicit safety rails, refactors can introduce accidental contract drift.

## Decision

We freeze the current provider-validation contract with regression tests:

1. Request schemas enforce:
- `model` requires `provider` for chat.
- compare targets must use known providers.
- BYOK payload and baseline constraints remain strict.

2. Chat route helper behavior remains stable:
- provider normalization is case-insensitive and drops invalid values.
- routing constraints parser ignores invalid env values.
- explicit manual model selection defaults to provider-specific default model.

3. BYOK service remains strict:
- unknown providers raise `ValueError`.
- runtime provider filters validate requested providers.
- BYOK key resolution skips unsupported rows and gracefully handles missing `MASTER_KEY`.

4. Orchestrator guardrails remain stable:
- unknown `model_type` in `_get_client` raises `ValueError`.
- non-smart routing without explicit provider returns normalized `bad_request` error.

## Consequences

- Provider-related behavior is now contract-tested and safe to refactor.
- Future provider onboarding changes must be deliberate and include contract updates.
- This ADR is a temporary guardrail for the baseline; it can be superseded once provider configuration becomes fully dynamic.
