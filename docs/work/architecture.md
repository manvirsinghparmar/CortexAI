# CortexAI Work architecture

## Boundary and ownership

Work is an additive execution mode beside Ask and Compare. The React route,
Zustand store, API module, FastAPI routes, application services, repository, and
provider adapter are all Work-owned. Existing authentication, subscription,
unified AI credits, sessions, uploads, private object storage, and logging are
shared platform services. Work never starts Claude Code, Cowork, a shell, or a
local agent subprocess.

The authoritative state is split deliberately:

- PostgreSQL owns Cortex session/run status, ordered public events, approvals,
  tool-call audit, user ownership, file references, connection snapshots,
  provider IDs, billing reservations, and reconciliation leases.
- Anthropic Managed Agents owns the remote execution environment and continues
  running if the browser or API process disconnects.
- Private S3 owns user inputs and imported deliverables; a provider file ID or
  URL is never a public download authority.
- The browser is a resumable observer/controller. It owns no durable run state.

## Start-to-deliver flow

1. React uploads inputs through the existing Cortex file pipeline and receives
   owned `uploaded_files` IDs.
2. `POST /v1/work/sessions` creates a common `sessions(mode=work)` row plus a
   specialized `work_sessions` row.
3. `POST /v1/work/sessions/{id}/runs` validates auth, ownership, entitlement,
   active-run/connection/file limits, web rollout, and the requested credit
   ceiling. `Idempotency-Key` is the idempotency key.
4. A short DB transaction reserves the maximum credits, creates the run and
   initial event, attaches files, and snapshots selected connections. It closes
   before any external I/O.
5. The provider adapter uploads input bytes server-side, creates or reuses the
   remote session, mounts all prior session resources after provider-session
   recovery, applies the provider budget, mounts MCP/vaults, and sends the user
   instruction.
6. `GET /stream` first replays `work_events` after `Last-Event-ID`, then claims a
   short PostgreSQL reconciliation lease, fetches provider events/usage, and
   appends normalized idempotent events. SSE comments keep the edge connection
   alive but do not alter the durable event sequence.
7. Tool-use events create high-signal audit rows. READ is confirmed silently.
   Unknown and sensitive actions become a persisted inline approval. WRITE can
   use an exact saved tool+connection grant for this Work session; destructive,
   external communication, financial, and deployment actions always ask.
8. Completion settles the run's cumulative usage delta, including normal/cache
   token pricing, Managed Agent active time, and web searches. Unused reserved
   credits are released by the existing billing service.
9. When artifact rollout is enabled, output files are listed, validated,
   downloaded server-side, stored through Cortex object storage, and registered
   as owned `uploaded_files` plus `work_run_files(role=artifact)` rows.
10. Open/download links call an authenticated Cortex route that checks both run
    and file ownership and returns `private, no-store` bytes.

A follow-up creates a new Work run under the same Work session and uses the
same provider session when available. Billing uses the prior cumulative usage
snapshot as the baseline so earlier tokens/runtime are not charged twice.

## Provider-neutral events

Public event payloads are stable Cortex contracts: `run_created`, `planning`,
`plan_created`, `progress`, `tool_started`, `tool_completed`,
`approval_required`, `approval_resolved`, `file_created`, `run_completed`,
`run_failed`, and `budget_exhausted`. They contain display copy and bounded,
redacted summaries. Provider thinking, raw tool output, credentials, cookies,
tokens, and authorization headers are excluded.

Every event has a per-run sequence allocated from a locked run row. Provider
event IDs are unique per run. Replay after sequence N is therefore ordered and
duplicate provider delivery is a no-op.

## Approval protocol

- The server classifies, persists, and decides approvals; provider policy is
  configured `always_ask` so it cannot bypass Cortex.
- Approval lookup joins approval -> run -> Work session -> user.
- A pending row is changed with a compare-and-set update. A replay gets 409.
- Pending approvals older than `CORTEX_WORK_APPROVAL_TIMEOUT_SECONDS` expire on
  the next reconciliation and are denied at the provider. A failed provider
  denial reopens the approval so a later reconciliation can retry safely.
- The provider receives allow/deny before the DB run resumes. If more pending
  approvals exist, the run remains `waiting_for_approval` and React shows one
  card at a time.
- Remembering is accepted only for `WRITE` with a concrete connection. The
  grant is exact `{connection_id, tool_name}` and scoped to this Work session.
  Sensitive action classes ignore remembered WRITE grants.
- Approval payload fields are redacted before persistence and rendering.

## Recovery and failure behavior

| Failure | User-visible behavior | Recovery source |
|---|---|---|
| Browser/SSE disconnect | Status pauses locally; reconnect catches up | ordered PostgreSQL events |
| API restart/deploy | Browser reconnects; run keeps executing remotely | provider session ID + DB lease |
| Provider session missing | normalized recoverable error; a later run creates a replacement and remounts inputs | Cortex files + Work session |
| Duplicate start | original run is returned; conflicting reuse is 409 | request ID constraint |
| Tool approval wait | inline card; no side effect before confirmation | approval/tool-call rows |
| Budget reached | remote session interrupted; status becomes Budget reached | run ceiling + usage snapshot |
| Artifact import error | completed outcome remains; deliverable is withheld | provider output + idempotent import |
| Feature rollback | Work navigation disappears and routes reject new control operations | server feature flag |

No DB transaction is held while waiting on Anthropic, MCP, OAuth, S3, or SSE.
No single API process is the run owner. A user who returns later triggers
reconciliation and can recover the remote outcome even when no browser remained
connected during execution.

V1 does not run an always-on Cortex reconciliation worker: provider execution
continues remotely, but Cortex event import, approval expiry, artifact import,
and final credit settlement occur when an authenticated run/event/stream request
triggers reconciliation. Remembered WRITE grants are stored and enforced, but a
dedicated settings UI/API for reviewing and revoking them is not yet included.

## Security and retention

All identifiers are opaque but never treated as authorization. Remote MCP URLs
must use public HTTPS on port 443, may not contain credentials, and are resolved
server-side to reject local/private/reserved addresses. OAuth state is hashed,
short-lived, single-use, and user-bound. OAuth tokens are stored in AWS Secrets
Manager references; provider vault IDs are opaque configuration, not secrets.

Work rows are retained with the account's billing/audit history. Work artifacts
reuse the existing file deletion/TTL queue. OAuth states and expired leases are
safe maintenance targets. Before high-volume production, the owner must set an
archive/retention policy for `work_events` and tool-call summaries that preserves
records needed for billing, approval audit, and incident investigation.

## Canonical implementation map

- React: `frontend-react/src/pages/WorkPage.tsx`, `components/work/`,
  `api/work.ts`, `store/workStore.ts`
- HTTP contracts: `server/routes/work.py`, `server/routes/tools.py`,
  `server/schemas/work.py`
- Application/runtime: `server/work/`
- Provider boundary: `server/work/provider.py`,
  `server/work/anthropic_provider.py`
- Persistence: `db/work_repository.py`, `db/tables.py`,
  `db/migrations/20260820_add_cortex_work_mode.sql`
- Plans: `config/subscription_plans.yaml`
- Operations: `docs/runbooks/cortex-work.md`,
  `docs/work/00-infrastructure-readiness.md`

The adapter follows the current Managed Agents beta contract and the MCP client
uses Streamable HTTP protocol `2025-06-18`. Re-verify both primary specifications
before a provider SDK or connector-protocol upgrade:

- https://platform.claude.com/docs/en/managed-agents/quickstart
- https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
