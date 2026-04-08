# ADR 0001: Architecture Baseline and Deploy Boundaries

- Status: Accepted
- Date: 2026-02-28
- Last reviewed: 2026-03-19 (decision unchanged)

## Context

The codebase is organized by modules (`api`, `orchestrator`, `server`, `frontend`), but provider logic and frontend serving are still coupled through a single runtime artifact.

Before moving to larger design changes (provider registry, config-driven provider metadata, deploy split), we need a stable baseline that captures current runtime boundaries and known contracts.

## Decision

We define and freeze the current baseline as:

1. Backend runs as a modular monolith:
- `server/` hosts HTTP routes and request/response validation.
- `orchestrator/` hosts routing and model invocation orchestration.
- `api/` hosts provider-specific client adapters.

2. Frontend remains served by FastAPI static mount in the current baseline.

3. Provider support remains explicitly limited to:
- `openai`
- `gemini`
- `deepseek`
- `grok`
- `claude`

4. Contract behavior for chat/compare/byok/provider validation is locked by regression tests before refactor work.

## Consequences

- We can refactor internals safely while preserving public behavior.
- Architectural improvements (separate frontend deploy, provider plugin registry) will be measured against this baseline.
- Any change to provider-validation behavior now requires an intentional contract update plus test updates.
