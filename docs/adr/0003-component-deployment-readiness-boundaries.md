# ADR 0003: Component Deployment Readiness Boundaries

- Status: Accepted
- Date: 2026-03-01

## Context

We want the system to be deployable as separate components (`frontend`, `api`) without requiring immediate AWS rollout work.

Current risks:

- Frontend can be tightly assumed to be mounted by FastAPI runtime.
- Build outputs are not explicitly split into frontend vs API artifacts.
- CI does not yet evaluate components independently based on changed paths.

## Decision

We define deployment-readiness boundaries as:

1. API runtime must run without frontend mount.
   - `SERVE_FRONTEND=false` disables static mount in `server/app.py`.
   - `FRONTEND_DIR` can override static source path when mount is enabled.

2. Frontend must run as a standalone static component.
   - `scripts/serve_frontend.py` provides independent local/static serving.
   - Frontend runtime config can override API base/key using `window.CORTEX_RUNTIME_CONFIG` or `localStorage`.

3. Build artifacts are split by component.
   - `scripts/build_frontend_artifact.py` generates static artifact output + zip.
   - `Dockerfile.api` builds API runtime image.

4. CI must detect changed paths and run component-specific checks/builds.
   - Frontend checks/builds trigger only for frontend/shared changes.
   - Backend checks/builds trigger only for backend/db/shared changes.
   - Deploy jobs remain intentionally out of scope for now.

5. DB migration operational guidance is documented in a runbook.
   - See `docs/runbooks/db-migrations.md`.

## Consequences

- The codebase is ready for later split deployment without a full rewrite.
- Frontend-only and backend-only changes can be validated independently.
- We retain monolith convenience in local/dev while enabling future platform split.
