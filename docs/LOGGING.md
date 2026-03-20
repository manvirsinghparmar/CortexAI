# Logging Documentation

## Overview

The project uses structured JSON logging via `utils/logger.py` with rotating file handlers.

Key characteristics:

- JSON logs for machine parsing and aggregation
- Separate app/error log streams
- Optional debug log stream
- Optional stderr error output (`LOG_TO_CONSOLE=true`)
- Request correlation support through `X-Request-ID` middleware + route/persistence context

## Log Files

All logs are written under `logs/`:

- `app.log` (INFO and above)
- `error.log` (ERROR and above)
- `debug.log` (DEBUG and above, created when `LOG_LEVEL=DEBUG`)

Rotation policy:

- Max file size: `10 MB`
- Backups kept: `5`

## Configuration

Environment variables:

```ini
LOG_LEVEL=INFO
LOG_TO_CONSOLE=false
```

`LOG_LEVEL` options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

`LOG_TO_CONSOLE=true` mirrors ERROR logs to stderr (useful in container logs / CI); default `false` keeps terminal output cleaner.

## Log Shape

Base fields emitted by formatter:

- `timestamp`
- `level`
- `logger`
- `message`
- `module`
- `function`
- `line`

Additional context is attached through `extra={"extra_fields": {...}}`.

## Security and Privacy

- Sensitive request headers are redacted before auth logging:
  - `X-API-Key`
  - `Authorization`
- Route/persistence flows can include `request_id` for tracing.
- Prompt/response storage behavior is controlled separately by privacy/storage settings (`STORAGE_POLICY`, `REDACT_PII`), not by logger formatter rules alone.

## Operational Notes

- Middleware sets/propagates `X-Request-ID`; use it to correlate route logs, provider calls, and persistence records.
- Start with `error.log` for incident triage, then pivot to `app.log` for full sequence.
- In local troubleshooting, `LOG_LEVEL=DEBUG` plus `LOG_TO_CONSOLE=true` provides fastest feedback.

## Related Files

- `utils/logger.py`
- `server/middleware.py`
- `server/dependencies.py`
- `server/utils.py` (header redaction)
- `server/persistence.py`

---

Last updated: 2026-03-19
