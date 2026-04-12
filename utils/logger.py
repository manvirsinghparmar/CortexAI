"""
Centralized structured logging configuration for the CortexAI project.

Key properties:
- JSON log events suitable for CloudWatch/ELK/Loki/Datadog ingestion
- Request correlation with context-aware request_id injection
- Rotating file logs plus optional stdout/stderr streaming
- Environment-driven levels and destination controls
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.config
import logging.handlers
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_REQUEST_ID_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _coerce_level(raw: str | None, fallback: str) -> str:
    value = str(raw or "").strip().upper()
    return value if value in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else fallback


def _coerce_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_positive_int(raw: str | None, default: int) -> int:
    try:
        value = int(str(raw or "").strip())
    except Exception:
        return default
    return value if value > 0 else default


def _resolve_log_dir() -> Path:
    configured = str(os.getenv("LOG_DIR") or "").strip()
    if not configured:
        return _REPO_ROOT / "logs"
    log_dir = Path(configured)
    if not log_dir.is_absolute():
        log_dir = (_REPO_ROOT / log_dir).resolve()
    return log_dir


def normalize_request_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if _REQUEST_ID_PATTERN.fullmatch(text):
        return text
    return None


def set_request_id(value: str | None) -> contextvars.Token[str | None]:
    """
    Set request_id in async-safe context storage.

    Returns a token that should be passed to reset_request_id().
    """
    normalized = normalize_request_id(value)
    return _REQUEST_ID_CONTEXT.set(normalized)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    """Reset request_id context using the token from set_request_id()."""
    try:
        _REQUEST_ID_CONTEXT.reset(token)
    except Exception:
        # Defensive: logging context reset should never break request handling.
        pass


def get_request_id() -> str | None:
    """Return request_id from context storage when present."""
    return _REQUEST_ID_CONTEXT.get()


class RequestContextFilter(logging.Filter):
    """Inject request_id from context into log record extra_fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        extra_fields = getattr(record, "extra_fields", None)
        if not isinstance(extra_fields, dict):
            extra_fields = {}
            setattr(record, "extra_fields", extra_fields)

        request_id = get_request_id()
        if request_id and "request_id" not in extra_fields:
            extra_fields["request_id"] = request_id
        return True


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            log_data.update(extra_fields)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_data["stack"] = self.formatStack(record.stack_info)

        return json.dumps(log_data, default=str, ensure_ascii=False)


class LoggerConfig:
    """Centralized logger configuration and lifecycle."""

    LOG_LEVEL = _coerce_level(os.getenv("LOG_LEVEL"), "INFO")
    LOG_CONSOLE_LEVEL = _coerce_level(os.getenv("LOG_CONSOLE_LEVEL"), "INFO")
    LOG_TO_CONSOLE = _coerce_bool(os.getenv("LOG_TO_CONSOLE"), False)
    LOG_DESTINATION = str(os.getenv("LOG_DESTINATION") or "").strip().lower()
    LOG_DIR = _resolve_log_dir()
    MAX_BYTES = _coerce_positive_int(os.getenv("LOG_FILE_MAX_BYTES"), 10 * 1024 * 1024)
    BACKUP_COUNT = _coerce_positive_int(os.getenv("LOG_FILE_BACKUP_COUNT"), 5)
    NOISY_LIBRARIES_LEVEL = _coerce_level(
        os.getenv("LOG_NOISY_LIBRARIES_LEVEL"),
        "WARNING",
    )

    _initialized = False

    @classmethod
    def _destination_mode(cls) -> str:
        if cls.LOG_DESTINATION in {"file", "stdout", "both"}:
            return cls.LOG_DESTINATION
        # Backward-compatible fallback:
        # old LOG_TO_CONSOLE=true should mean file+stdout output.
        return "both" if cls.LOG_TO_CONSOLE else "file"

    @classmethod
    def setup_logging(cls) -> None:
        """Set up process-wide logging via dictConfig."""
        if cls._initialized:
            return

        destination = cls._destination_mode()
        if destination in {"file", "both"}:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

        handlers: dict[str, dict[str, Any]] = {}
        root_handlers: list[str] = []

        if destination in {"file", "both"}:
            handlers["app_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": str(cls.LOG_DIR / "app.log"),
                "maxBytes": cls.MAX_BYTES,
                "backupCount": cls.BACKUP_COUNT,
                "encoding": "utf-8",
                "filters": ["request_context"],
            }
            handlers["error_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": str(cls.LOG_DIR / "error.log"),
                "maxBytes": cls.MAX_BYTES,
                "backupCount": cls.BACKUP_COUNT,
                "encoding": "utf-8",
                "filters": ["request_context"],
            }
            root_handlers.extend(["app_file", "error_file"])

            if cls.LOG_LEVEL == "DEBUG":
                handlers["debug_file"] = {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "json",
                    "filename": str(cls.LOG_DIR / "debug.log"),
                    "maxBytes": cls.MAX_BYTES,
                    "backupCount": cls.BACKUP_COUNT,
                    "encoding": "utf-8",
                    "filters": ["request_context"],
                }
                root_handlers.append("debug_file")

        if destination in {"stdout", "both"}:
            handlers["console"] = {
                "class": "logging.StreamHandler",
                "level": cls.LOG_CONSOLE_LEVEL,
                "formatter": "json",
                "stream": "ext://sys.stdout",
                "filters": ["request_context"],
            }
            root_handlers.append("console")

        config: dict[str, Any] = {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_context": {
                    "()": RequestContextFilter,
                }
            },
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                }
            },
            "handlers": handlers,
            "root": {
                "level": cls.LOG_LEVEL,
                "handlers": root_handlers,
            },
            "loggers": {
                # Keep external HTTP/network libraries quieter unless explicitly raised.
                "httpx": {"level": cls.NOISY_LIBRARIES_LEVEL, "propagate": True},
                "urllib3": {"level": cls.NOISY_LIBRARIES_LEVEL, "propagate": True},
                "botocore": {"level": cls.NOISY_LIBRARIES_LEVEL, "propagate": True},
                "boto3": {"level": cls.NOISY_LIBRARIES_LEVEL, "propagate": True},
            },
        }

        logging.config.dictConfig(config)
        cls._initialized = True

        init_logger = logging.getLogger(__name__)
        init_logger.info(
            "Logging system initialized",
            extra={
                "extra_fields": {
                    "event": "logging.initialized",
                    "log_level": cls.LOG_LEVEL,
                    "console_level": cls.LOG_CONSOLE_LEVEL,
                    "destination": destination,
                    "log_dir": str(cls.LOG_DIR),
                    "max_bytes": cls.MAX_BYTES,
                    "backup_count": cls.BACKUP_COUNT,
                    "noisy_libraries_level": cls.NOISY_LIBRARIES_LEVEL,
                }
            },
        )

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        if not cls._initialized:
            cls.setup_logging()
        return logging.getLogger(name)


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor for configured loggers."""
    return LoggerConfig.get_logger(name)


# Initialize logging on module import.
LoggerConfig.setup_logging()
