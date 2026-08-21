# CortexAI Work rollout and operations

## Production gate

Keep `CORTEX_WORK_ENABLED=false` until every item below has an evidence link or
captured command output. Repository implementation is not proof of live AWS or
Anthropic configuration; unresolved items are enumerated in
`docs/work/00-infrastructure-readiness.md`.

1. Back up RDS/PostgreSQL and confirm PITR.
2. Apply the additive migration with the same guarded production migration role
   used by the subscription rollout:

   ```powershell
   $env:MIGRATION_DATABASE_URL = 'postgresql+psycopg://...'
   psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260820_add_cortex_work_mode.sql
   ```

3. Verify the schema:

   ```sql
   SELECT to_regclass('public.work_sessions'),
          to_regclass('public.work_runs'),
          to_regclass('public.work_events'),
          to_regclass('public.tool_connections'),
          to_regclass('public.work_approvals');
   SELECT pg_get_constraintdef(oid)
   FROM pg_constraint
   WHERE conname IN ('ck_sessions_mode', 'ck_work_runs_status');
   ```

4. Create the Anthropic Managed Agent and environment. Record resource names,
   owners, region/data policy, and IDs. Inject `ANTHROPIC_API_KEY`, never print it.
5. Configure the environment variables listed below and deploy with Work still
   disabled.
6. Confirm outbound DNS/TCP 443 to Anthropic and every approved MCP/OAuth host.
7. Confirm the API workload role's exact S3/KMS and Secrets Manager permissions.
8. Configure cache-disabled `/v1/work/*` and `/v1/tools/*` API behaviors at the
   edge. Forward cookies/auth, query strings, `X-Request-ID`, and `Last-Event-ID`.
   Disable response buffering/transformation and set origin/ALB timeouts above
   the 15-second SSE heartbeat.
9. Keep WAF enabled; inspect logs before creating any exact path/method exception.
10. Run existing Ask, Compare, Research, Optimize, Analysis, uploads, billing,
    history, and auth smoke tests before enabling Work for an internal Pro user.

## Configuration inventory

Required for production Work:

- `CORTEX_WORK_ENABLED`
- `CORTEX_WORK_AGENT_PROVIDER=anthropic_managed_agents`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MANAGED_AGENT_ID`
- `ANTHROPIC_MANAGED_ENVIRONMENT_ID`
- `ANTHROPIC_MANAGED_BILLING_MODEL`
- `CORTEX_WORK_DEFAULT_CREDIT_BUDGET`
- `CORTEX_WORK_SYNC_INTERVAL_SECONDS`
- `CORTEX_WORK_SSE_HEARTBEAT_SECONDS`
- `CORTEX_WORK_APPROVAL_TIMEOUT_SECONDS`
- `CORTEX_WORK_MCP_ENABLED`
- `CORTEX_WORK_ACTION_TOOLS_ENABLED`
- `CORTEX_WORK_ARTIFACT_IMPORT_ENABLED`
- `CORTEX_WORK_WEB_ENABLED`
- `CORTEX_WORK_CONNECTOR_SECRET_PREFIX`

The existing `DATABASE_URL`, billing/Stripe settings, attachment/S3 settings,
Cognito/session settings, `MASTER_KEY`, proxy settings, and logging settings
remain authoritative.

For each verified connector key (`GITHUB`, `GOOGLE_DRIVE`, `GMAIL`, `SLACK`,
`JIRA`, `NOTION`, `MICROSOFT_365`) configure:

- `CORTEX_WORK_CONNECTOR_<KEY>_MCP_URL`
- `CORTEX_WORK_CONNECTOR_<KEY>_OAUTH_AUTHORIZATION_URL`
- `CORTEX_WORK_CONNECTOR_<KEY>_OAUTH_TOKEN_URL`
- `CORTEX_WORK_CONNECTOR_<KEY>_OAUTH_CLIENT_ID`
- `CORTEX_WORK_CONNECTOR_<KEY>_OAUTH_CLIENT_SECRET`
- `CORTEX_WORK_CONNECTOR_<KEY>_OAUTH_REDIRECT_URI`
- `CORTEX_WORK_CONNECTOR_<KEY>_OAUTH_SCOPE`
- `CORTEX_WORK_CONNECTOR_<KEY>_PROVIDER_VAULT_ID`

Register every exact HTTPS callback URL at the OAuth provider. The callback must
resolve to `/v1/tools/<connector_key>/oauth/callback`. Authenticated custom MCP
requires a reviewed Secrets Manager ARN plus a Managed Agent provider vault ID.

## Rollout sequence

1. Deploy DB migration.
2. Deploy API/React with Work disabled; verify `/runtime-config.js` reports
   `workEnabled:false` and Work is absent from navigation.
3. Enable `CORTEX_WORK_ENABLED` with MCP/action/artifact/web flags still false.
   Run a Plus and Pro file-only task. Free must receive `work_not_in_plan`.
4. Enable artifact import; validate PDF/text/spreadsheet deliverables, private
   download ownership, invalid MIME/oversize rejection, and S3 cleanup.
5. Enable web for internal Pro; verify budget settlement includes web requests.
6. Enable MCP and one read-only verified connector. Verify SSRF rejection,
   OAuth state replay rejection, connection ownership, tool discovery, audit,
   and disconnect/reconnect.
7. Enable action tools. Verify inline approve, deny, replay 409, sensitive-action
   approval, exact remembered WRITE grant, and a second queued approval.
8. Expand to Plus. Monitor provider errors, active-run age, reserved credits,
   approval latency, WAF blocks, SSE reconnect rate, and DB pool/lock pressure.

## Smoke test

Use a signed internal account. Never use the fake provider in production.

1. Open `/work`; confirm the exact empty headline `What should I work on?`.
2. Upload a small owned file, set a 25k budget, and start a run.
3. Record session/run IDs and confirm `run_created`, planning/progress, and SSE
   heartbeats. Disconnect the browser for at least one edge timeout, reconnect,
   and verify no duplicate events.
4. Restart one API instance during a run and verify provider-session recovery.
5. Trigger a read tool (no approval) and a WRITE tool (approval required).
6. Deny once; verify no side effect. Retry, approve, and verify a replay is 409.
7. Complete the task, open/download an artifact, and verify a second user gets
   404 for the same run/file/approval IDs.
8. Compare reservation, ledger, run `actual_credits`, cumulative provider usage,
   runtime/web cost, and released remainder.
9. Start a follow-up in the same Work session and verify earlier usage is not
   billed again.
10. Cancel an active run and verify remote interruption, durable cancelled state,
    actual-use settlement, and released reservation.

## Monitoring and alerts

Dashboard and alert by hashed account plus request/run/session correlation IDs:

- active/terminal runs, oldest run, provider session failures, reconciliation
  errors/lease contention, duplicate event rate, and SSE reconnects;
- pending/expired approval count and decision latency;
- connector discovery/OAuth/SSRF failures and tool calls by risk class;
- reserved/settled/released/unbilled credits and provider cost drift;
- artifact imports, validation failures, S3/KMS errors, and orphan cleanup;
- DB pool saturation, lock waits, event growth, API 5xx/504, and WAF blocks.

Never log instructions, file contents, tool payloads, OAuth tokens, provider
credentials, or secret values.

## Troubleshooting

- `work_disabled` (404): master flag is false or the deployment did not reload.
- `work_provider_not_configured` (503): provider IDs, billing model, or API key
  is missing; validate secret injection without printing values.
- `work_not_in_plan` (403): effective plan is Free or billing snapshots have not
  updated; inspect `/v1/entitlements`.
- `insufficient_credits` (402): choose a lower budget or wait for/reset credits.
- `active_work_run_limit` (409): complete/cancel an existing run.
- SSE stops around a fixed interval: compare heartbeat with CloudFront origin,
  ALB idle, nginx/read, and client timeouts; ensure no buffering/caching.
- `mcp_connection_failed` (502): verify public HTTPS:443 DNS, Streamable HTTP
  initialize/tools-list support, OAuth/vault configuration, and egress policy.
- approval remains pending: inspect provider session ID, tool-call provider ID,
  other queued approvals, and normalized confirmation error logs.
- completed with no deliverable: inspect artifact flag, provider output listing,
  MIME/size checks, S3/KMS rights, and `work.artifact.import.failed` logs.
- reservation remains open: reopen the run to reconcile, inspect provider usage,
  and then use the existing stale reservation maintenance path only after the
  provider state is understood.

## Rollback

1. Set `CORTEX_WORK_ACTION_TOOLS_ENABLED=false`, then
   `CORTEX_WORK_MCP_ENABLED=false`, then `CORTEX_WORK_ENABLED=false`.
2. Drain short HTTP control requests; do not wait for browser SSE connections.
3. Reconcile/cancel active provider sessions and settle/release reservations.
4. Deploy the previous application/React version.
5. Retain all additive Work tables and artifacts for audit and later recovery.
   Do not drop columns/tables during an incident rollback.
6. Re-run Ask/Compare/billing/upload smoke tests and preserve incident evidence.

Primary operational references:

- Anthropic Managed Agents: https://platform.claude.com/docs/en/managed-agents/quickstart
- MCP Streamable HTTP: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- CloudFront origin timeouts: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html
- ALB idle timeout: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-load-balancer-attributes.html
