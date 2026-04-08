# Architecture Decision Records (ADR)

This folder captures architecture decisions that we want to keep stable over time.

Operational behavior and endpoint contracts can evolve; when details differ, treat ADRs as design intent and use `README.md` + `docs/FASTAPI_README.md` for current runtime truth.

## Purpose

- Make design tradeoffs explicit.
- Preserve historical context for refactors.
- Define contracts that regression tests must protect.

## Index

- [0001 - Architecture Baseline and Deploy Boundaries](./0001-architecture-baseline-and-deploy-boundaries.md)
- [0002 - Provider Validation and Safety Rails](./0002-provider-validation-and-safety-rails.md)
- [0003 - Component Deployment Readiness Boundaries](./0003-component-deployment-readiness-boundaries.md)

## ADR Format

Each ADR includes:

- `Status`: proposed, accepted, deprecated, superseded
- `Date`
- `Context`
- `Decision`
- `Consequences`

---

Last reviewed: 2026-03-19
