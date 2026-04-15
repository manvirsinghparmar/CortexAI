# AWS EC2 Linux Logging Runbook

## Purpose

This runbook describes where to find CortexAI logs on AWS EC2 Linux hosts and how to trace incidents end-to-end.

It is optimized for:

- file upload failures (`POST /v1/files/upload`)
- Tavily/web-search connectivity issues
- CloudFront/WAF vs origin diagnosis

## Time And Correlation Basics

- CloudFront access logs are in UTC.
- CortexAI structured logs use UTC timestamps (`timestamp` field).
- Always carry one of these IDs through triage:
  - `request_id` (API response header `X-Request-ID`)
  - CloudFront `x-edge-request-id`
  - CloudFront forwarded request header `X-Amz-Cf-Id` (if forwarded)

## Logging Configuration To Use In EC2

Recommended environment values:

```ini
LOG_LEVEL=INFO
LOG_DESTINATION=both
LOG_CONSOLE_LEVEL=INFO
LOG_DIR=logs
LOG_NOISY_LIBRARIES_LEVEL=WARNING
```

Tavily diagnostics (recommended):

```ini
TAVILY_NETWORK_DIAGNOSTICS_HOST=api.tavily.com
TAVILY_NETWORK_DIAGNOSTICS_PORT=443
TAVILY_NETWORK_DIAGNOSTICS_INTERVAL_SECONDS=300
TAVILY_NETWORK_DIAGNOSTICS_TIMEOUT_SECONDS=2
```

## Where Logs Are Stored

### 1) CortexAI file logs

With `LOG_DESTINATION=file|both`, logs are written under repo-root `logs/`:

- `logs/app.log` (INFO+)
- `logs/error.log` (ERROR+)
- `logs/debug.log` (DEBUG+, only when `LOG_LEVEL=DEBUG`)

Example path on EC2:

- `/home/ubuntu/OpenAIProject/logs/app.log`

### 2) Systemd/journald logs (stdout/stderr)

With `LOG_DESTINATION=stdout|both`, JSON logs are visible in journal.

Common commands:

```bash
sudo systemctl status cortexai
sudo journalctl -u cortexai -n 200 --no-pager
sudo journalctl -u cortexai -f
```

Time-window example (UTC):

```bash
sudo journalctl -u cortexai \
  --since "2026-04-14 01:00:00 UTC" \
  --until "2026-04-14 01:10:00 UTC" \
  --no-pager
```

### 3) Docker logs (if containerized)

```bash
docker ps
docker logs <container_name_or_id> --since 30m
docker logs -f <container_name_or_id>
```

### 4) Nginx / reverse proxy logs (if used)

Common locations:

- `/var/log/nginx/access.log`
- `/var/log/nginx/error.log`

## CloudFront/WAF vs Origin: Fast Decision Tree

1. Check CloudFront log line.
2. Search CortexAI for `upload.route.received` (or `http.request.start`) around same UTC timestamp.
3. Interpret result:
   - If not found: blocked before origin (CloudFront behavior, WAF rule, edge policy).
   - If found: request reached app; continue with application event chain.

If CloudFront ID forwarding is enabled, correlate directly with:

- request header: `X-Amz-Cf-Id`
- app field: `edge_headers.x_amz_cf_id` in `upload.route.received`

## Upload Incident Workflow (`POST /v1/files/upload`)

### Step 1: confirm route arrival

Search for:

- `event=upload.route.received`

Key fields:

- `auth_mode`
- `has_x_api_key_header`
- `has_authorization_header`
- `content_length_header`
- `edge_headers` (CloudFront/proxy context)

### Step 2: check payload parsing

Search for:

- `event=upload.route.payload.read`

Key fields:

- `payload_size_bytes`
- `content_length_matches_payload`

### Step 3: find rejection/success point

Possible terminal route events:

- `upload.route.success`
- `upload.route.rejected`
- `upload.route.rejected.empty_body`
- `upload.route.exception`

Service-level validation events:

- `upload.feature.disabled`
- `upload.db.disabled`
- `upload.validation.invalid_mime`
- `upload.validation.unsupported_mime`
- `upload.validation.empty_payload`
- `upload.validation.file_too_large`
- `upload.auth.resolved`

Auth-related failures:

- `auth.failed`
- `auth.config.missing`

## Tavily/Web Search Incident Workflow

### Core Tavily events

- `research.dispatch`
- `research.search.start|success|failure|empty`
- `research.qna.start|success|failure`
- `research.context.ready|failure`

### Network diagnostics event

- `research.network.diagnostics`

Key fields:

- `status` (`ok` or `degraded`)
- `diagnostic_host`
- `diagnostic_port`
- `dns_ok`, `dns_latency_ms`, `dns_error_type`
- `tcp_ok`, `tcp_latency_ms`, `tcp_error_type`, `tcp_error_errno`
- proxy flags: `http_proxy_present`, `https_proxy_present`, `no_proxy_present`

### Tavily failure classification

On `research.search.failure` and `research.qna.failure`, use:

- `error_kind`
- `error_type`
- `error_message`
- `error_chain_types`
- `network_diag_status`

Common `error_kind` values:

- `dns_resolution_failed`
- `timeout`
- `connection_refused`
- `proxy_error`
- `tls_error`
- `auth_forbidden`
- `rate_limited`
- `provider_server_error`

## Handy Linux Commands (JSON Logs)

### Filter app.log by event

```bash
grep '"event":"upload.route.rejected"' logs/app.log | tail -n 50
```

### Filter by request id

```bash
grep '"request_id":"<request-id>"' logs/app.log
```

### jq filtering

```bash
jq -c 'select(.event=="research.search.failure")' logs/app.log | tail -n 50
```

```bash
jq -c 'select(.event=="research.network.diagnostics" and .status=="degraded")' logs/app.log
```

### Combined upload chain view

```bash
jq -c 'select(.request_id=="<request-id>") | {timestamp,event,status_code,error_code,error_kind,payload_size_bytes,content_length_header}' logs/app.log
```

## CloudWatch Logs Insights Query Examples

If journald/stdout is shipped to CloudWatch, adapt field names to your log group parser.

Upload failures:

```sql
fields @timestamp, event, request_id, status_code, error_code, path, auth_mode
| filter event like /upload\.route\.(rejected|exception)/ or event like /upload\.validation\./
| sort @timestamp desc
| limit 200
```

Tavily network failures:

```sql
fields @timestamp, event, error_kind, error_type, network_diag_status, dns_ok, tcp_ok, tcp_error_errno
| filter event in ["research.search.failure","research.qna.failure","research.network.diagnostics"]
| sort @timestamp desc
| limit 200
```

## Practical Root-Cause Patterns

### Pattern: CloudFront 403 with no origin logs

Symptoms:

- CloudFront shows `sc-status=403`
- no `upload.route.received` in app logs

Likely layer:

- WAF rule, CloudFront behavior/policy, edge-level block.

### Pattern: `auth.failed` then `upload.route.rejected`

Symptoms:

- request reached origin but auth header missing/invalid.

Likely layer:

- forwarded header policy (missing `X-API-Key` / `Authorization`) or client auth bug.

### Pattern: Tavily failures with `dns_resolution_failed`

Symptoms:

- `research.search.failure` with `error_kind=dns_resolution_failed`
- `research.network.diagnostics` has `dns_ok=false`

Likely layer:

- EC2 DNS resolver/VPC DNS/security egress restrictions.

### Pattern: Tavily failures with `timeout` and diagnostics `tcp_ok=false`

Likely layer:

- SG/NACL/route egress restrictions, proxy misconfiguration, or external network path.

## What To Capture In Incident Tickets

- UTC timestamp window.
- `request_id` and/or `x-edge-request-id`.
- `event` sequence for that request.
- relevant fields:
  - upload: `status_code`, `error_code`, `auth_mode`, `content_length_matches_payload`, `edge_headers.x_amz_cf_id`
  - Tavily: `error_kind`, `dns_ok`, `tcp_ok`, `tcp_error_errno`, proxy flags
- whether request reached origin (`upload.route.received` present or absent).

---

Last updated: 2026-04-13
