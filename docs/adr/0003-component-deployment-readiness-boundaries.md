# ADR 0003: Component Deployment Readiness Boundaries

- Status: Superseded by ADR 0004
- Date: 2026-03-01
- Last reviewed: 2026-05-09 (decision extended for React/Vite frontend)

## Context

We want the system to be deployable as separate components (`frontend`, `api`) without requiring immediate AWS rollout work.

Current risks:

- Frontend can be tightly assumed to be mounted by FastAPI runtime.
- Build outputs are not explicitly split into frontend vs API artifacts.
- CI does not yet evaluate components independently based on changed paths.
- React/Vite static output requires an npm build before FastAPI or nginx can serve it.
- Split React deployments need explicit routing for API/session endpoints because the current React client uses same-origin relative API paths.

## Decision

We define deployment-readiness boundaries as:

1. API runtime must run without frontend mount.
   - `SERVE_FRONTEND=false` disables static mount in `server/app.py`.
   - `FRONTEND_DIR` can override static source path when mount is enabled.
   - The current React-only default and selector behavior are defined by ADR 0004.

2. Frontend must run as a standalone static component.
   - Vite preview supports local static-build checks, while nginx/CDN hosting supports deployment.
   - Frontend runtime config can override API base and local dev bootstrap flags using `window.CORTEX_RUNTIME_CONFIG` or `localStorage`.
   - The React frontend is built with `npm ci --prefix frontend-react` and `npm run --prefix frontend-react build`.
   - React hot-reload development uses `npm run --prefix frontend-react dev`, with Vite proxying `/v1`, `/auth`, and `/runtime-config.js` to the local API.

3. Build artifacts are split by component.
   - `scripts/build_frontend_artifact.py` generates static artifact output + zip.
   - `Dockerfile.api` builds API runtime image.
   - `Dockerfile.frontend` builds the React frontend and serves static assets with nginx.
   - `Dockerfile.api` does not include React assets by default; deployments that want API-served React must copy `frontend-react/dist` into the API runtime image and set `FRONTEND_DIR`.

4. CI must detect changed paths and run component-specific checks/builds.
   - React checks/builds trigger only for React/shared changes.
   - Backend checks/builds trigger only for backend/db/shared changes.
   - Deploy jobs remain intentionally out of scope for now.

5. DB migration operational guidance is documented in a runbook.
   - See `docs/runbooks/db-migrations.md`.

## Consequences

- The codebase is ready for later split deployment without a full rewrite.
- Frontend-only and backend-only changes can be validated independently.
- We retain monolith convenience in local/dev while enabling future platform split.
- Production split deployments must put React static hosting and FastAPI behind routing that sends `/v1/*`, `/auth`, and `/runtime-config.js` to the API service, or must extend `nginx.conf` equivalently.
- React dependencies stay in npm manifests, not Python `requirements.txt`.
