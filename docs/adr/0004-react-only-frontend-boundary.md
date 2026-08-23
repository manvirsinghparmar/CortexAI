# ADR 0004: React-Only Frontend Boundary

- Status: Accepted
- Date: 2026-07-25

## Context

The repository previously carried two product UIs: a vanilla HTML/CSS/JavaScript application in `frontend/` and the React/Vite application in `frontend-react/`. Maintaining two runtime choices duplicated browser tests, CI jobs, deployment tooling, documentation, and static-serving configuration after React became the supported product UI.

## Decision

1. `frontend-react/` is the only product frontend.
2. FastAPI may still serve compiled frontend assets for monolith deployments:
   - `SERVE_FRONTEND=false` keeps the API runtime API-only.
   - `FRONTEND_DIR` overrides the compiled asset directory.
   - `frontend-react/dist` is the default when `FRONTEND_DIR` is unset.
3. `GET /runtime-config.js` remains an API-owned React runtime contract.
4. `frontend-react/runtime-config.example.js` is the template for static hosts that must provide the runtime config themselves.
5. Vite build output, `Dockerfile.frontend`, and `scripts/build_frontend_artifact.py` are the supported React artifacts.
6. React unit/build checks and Playwright React suites replace the removed vanilla-frontend checks.
7. The live Playwright bootstrap builds React and serves `frontend-react/dist` through FastAPI before running full-stack scenarios.

## Consequences

- The `frontend/` directory, the dual-UI `REACT_FRONTEND` switch, the standalone vanilla static server, and vanilla-only CI jobs are removed.
- Local development continues through `python run_app.py`, which runs FastAPI in API-only mode alongside Vite.
- Production can use the standalone React/nginx image or explicitly mount the React build into FastAPI.
- Backend uses of the term `legacy` for routing, persisted compatibility data, or API behavior are unaffected.
