# Logging System Documentation

## Overview

The OpenAI Project now uses an enterprise-ready structured JSON logging system that provides:

- **Structured JSON logs** for easy integration with log aggregation systems (ELK, Grafana Loki, Datadog)
- **Multiple log files** with automatic rotation to prevent disk space issues
- **Clean console** - user chat interface remains uncluttered
- **Environment-based configuration** - easily adjust logging behavior
- **Production-ready** - follows enterprise logging best practices

## Log Files

All logs are stored in the `logs/` directory:

| File | Content | Level | Purpose |
|------|---------|-------|---------|
| `app.log` | Application logs (JSON) | INFO+ | Main application events, API calls, completions |
| `error.log` | Error logs only (JSON) | ERROR+ | All errors for troubleshooting |
| `debug.log` | Debug logs (JSON) | DEBUG+ | Everything (only created if LOG_LEVEL=DEBUG) |

### Log Rotation

- **Max file size**: 10MB per file
- **Backup files**: 5 previous versions kept
- **Automatic**: Old logs rotate automatically (e.g., `app.log.1`, `app.log.2`)

## Configuration

Configure logging via environment variables in `.env`:

```bash
# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Whether to output ERROR logs to console (stderr)
# false = clean console (recommended for chat interface)
# true = errors also visible in console
LOG_TO_CONSOLE=false
```

### Log Levels

| Level | When to Use | What You'll See |
|-------|-------------|-----------------|
| **DEBUG** | Development/troubleshooting | Everything: user queries, token counts, internal operations |
| **INFO** | Production (recommended) | Application events: initialization, completions, session stats |
| **WARNING** | Production (quiet) | Potential issues: missing API keys, deprecated features |
| **ERROR** | Production (minimal) | Only errors: API failures, exceptions |
| **CRITICAL** | Production (alerts only) | Critical failures requiring immediate attention |

## Log Format

### JSON Structure (in files)

```json
{
  "timestamp": "2026-01-03T10:30:45.123456Z",
  "level": "INFO",
  "logger": "api.openai_client",
  "message": "Completion successful",
  "module": "openai_client",
  "function": "get_completion",
  "line": 72,
  "prompt_tokens": 45,
  "completion_tokens": 120,
  "total_tokens": 165,
  "cost": 0.00285
}
```

### Human-Readable Format (console, if enabled)

```
[2026-01-03 10:30:45] [ERROR] [api.openai_client] Error getting completion: API timeout
```

## What Gets Logged

### Application Lifecycle
- ✅ Application startup with model type
- ✅ Client initialization (OpenAI, Gemini, DeepSeek, Grok)
- ✅ Session statistics on exit
- ✅ User interruptions (Ctrl+C)

### API Operations
- ✅ Completion requests (with token counts and costs)
- ✅ Model listing operations
- ✅ API errors with error types
- ✅ Missing API keys

### User Actions
- ✅ Stats command usage (DEBUG level)
- ✅ User query lengths (DEBUG level)

### What's NOT Logged
- ❌ User messages (privacy)
- ❌ AI responses (privacy)
- ❌ API keys (security)

## Integration with Centralized Logging Systems

The JSON format makes integration with enterprise logging systems straightforward:

### Grafana Loki (Recommended)

1. **Install Promtail** (log shipper):
   ```bash
   # Download and install Promtail
   wget https://github.com/grafana/loki/releases/download/v2.9.0/promtail-linux-amd64.zip
   ```

2. **Configure Promtail** (`promtail-config.yml`):
   ```yaml
   server:
     http_listen_port: 9080
     grpc_listen_port: 0

   positions:
     filename: /tmp/positions.yaml

   clients:
     - url: http://localhost:3100/loki/api/v1/push

   scrape_configs:
     - job_name: openai-project
       static_configs:
         - targets:
             - localhost
           labels:
             job: openai-project
             __path__: /path/to/OpenAIProject/logs/*.log
       pipeline_stages:
         - json:
             expressions:
               level: level
               logger: logger
               timestamp: timestamp
         - labels:
             level:
             logger:
   ```

3. **Run**:
   ```bash
   ./promtail -config.file=promtail-config.yml
   ```

### ELK Stack

1. **Install Filebeat**:
   ```bash
   # Install Filebeat for log shipping
   curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.10.0-linux-x86_64.tar.gz
   ```

2. **Configure Filebeat** (`filebeat.yml`):
   ```yaml
   filebeat.inputs:
     - type: log
       enabled: true
       paths:
         - /path/to/OpenAIProject/logs/*.log
       json.keys_under_root: true
       json.add_error_key: true

   output.elasticsearch:
     hosts: ["localhost:9200"]
   ```

### Datadog

1. **Install Datadog Agent**
2. **Configure log collection** in `datadog.yaml`:
   ```yaml
   logs_enabled: true
   logs_config:
     logs_dd_url: https://http-intake.logs.datadoghq.com:443
   ```

3. **Add log source** (`/etc/datadog-agent/conf.d/openai_project.yaml`):
   ```yaml
   logs:
     - type: file
       path: /path/to/OpenAIProject/logs/*.log
       service: openai-project
       source: python
       sourcecategory: application
   ```

## Development Tips

### Debugging Issues

1. **Enable DEBUG logging**:
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **View logs in real-time**:
   ```bash
   # Watch all logs
   tail -f logs/app.log | python -m json.tool

   # Watch errors only
   tail -f logs/error.log | python -m json.tool
   ```

3. **Search logs**:
   ```bash
   # Find all errors
   grep '"level": "ERROR"' logs/app.log | python -m json.tool

   # Find specific function calls
   grep '"function": "get_completion"' logs/app.log | python -m json.tool
   ```

### Testing Logging

```python
from utils.logger import get_logger

logger = get_logger(__name__)

# Test different levels
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")

# Add extra context
logger.info(
    "User action",
    extra={"extra_fields": {
        "user_id": "123",
        "action": "query",
        "tokens": 150
    }}
)
```

## Console Behavior

### Default (LOG_TO_CONSOLE=false)
- ✅ Console is **clean** - only user chat interface
- ✅ All logs go to files
- ✅ Perfect for interactive chat sessions

### With Console Logging (LOG_TO_CONSOLE=true)
- ⚠️ ERROR logs appear in console (stderr)
- ⚠️ May clutter chat interface
- ✅ Useful for monitoring errors in real-time

## Best Practices

1. **Production**: Use `LOG_LEVEL=INFO` and `LOG_TO_CONSOLE=false`
2. **Development**: Use `LOG_LEVEL=DEBUG` to see everything
3. **Troubleshooting**: Check `error.log` first for problems
4. **Monitoring**: Integrate with Grafana Loki or Datadog for dashboards
5. **Privacy**: Never log sensitive user data or API keys

## Migration from Print Statements

All `print()` statements for internal operations have been replaced with logging:

| Old | New |
|-----|-----|
| `print(f"Error: {e}")` | `logger.error(f"Error: {e}")` |
| `print("Initialized client")` | `logger.info("Initialized client")` |
| `print(f"Debug: {value}")` | `logger.debug(f"Debug: {value}")` |

**User-facing print statements** (chat interface) remain unchanged.

## Troubleshooting

### Logs not appearing?
1. Check `LOG_LEVEL` in `.env`
2. Verify `logs/` directory exists and is writable
3. Look for errors in console during startup

### Logs taking up too much space?
- Logs rotate automatically at 10MB
- Only 5 backup files are kept
- Reduce log level to WARNING or ERROR

### Want to see logs in console?
- Set `LOG_TO_CONSOLE=true` in `.env`
- Only ERROR logs will appear in stderr

## Future Enhancements

Potential improvements:
- [ ] Add request IDs for distributed tracing
- [ ] Integrate OpenTelemetry for full observability
- [ ] Add log sampling for high-volume scenarios
- [ ] Create custom log analyzers/dashboards
- [ ] Add log shipping daemon (systemd service)
