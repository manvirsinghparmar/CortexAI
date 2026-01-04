"""
Centralized logging configuration for the OpenAI Project.

This module provides structured JSON logging with:
- Rotating file handlers to prevent log file bloat
- Separate files for different log levels
- Console output only for errors (optional)
- Environment-based configuration
- Enterprise-ready JSON format for easy integration with ELK/Loki/Datadog
"""

import logging
import logging.handlers
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs logs in JSON format for easy parsing by log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class LoggerConfig:
    """
    Centralized logger configuration and management.
    """

    # Default configuration
    LOG_DIR = Path("logs")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "false").lower() == "true"
    MAX_BYTES = 10 * 1024 * 1024  # 10MB per file
    BACKUP_COUNT = 5  # Keep 5 backup files

    _initialized = False

    @classmethod
    def setup_logging(cls) -> None:
        """
        Set up the logging configuration for the entire application.
        This should be called once at application startup.
        """
        if cls._initialized:
            return

        # Create logs directory if it doesn't exist
        cls.LOG_DIR.mkdir(exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, cls.LOG_LEVEL))

        # Remove any existing handlers
        root_logger.handlers.clear()

        # JSON formatter for file handlers
        json_formatter = JsonFormatter()

        # Console formatter (human-readable, only for errors)
        console_formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 1. Main application log (INFO and above) - JSON format
        app_handler = logging.handlers.RotatingFileHandler(
            cls.LOG_DIR / "app.log",
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT,
            encoding='utf-8'
        )
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(json_formatter)
        root_logger.addHandler(app_handler)

        # 2. Error log (ERROR and above) - JSON format
        error_handler = logging.handlers.RotatingFileHandler(
            cls.LOG_DIR / "error.log",
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(json_formatter)
        root_logger.addHandler(error_handler)

        # 3. Debug log (everything) - JSON format (only if DEBUG level)
        if cls.LOG_LEVEL == "DEBUG":
            debug_handler = logging.handlers.RotatingFileHandler(
                cls.LOG_DIR / "debug.log",
                maxBytes=cls.MAX_BYTES,
                backupCount=cls.BACKUP_COUNT,
                encoding='utf-8'
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(json_formatter)
            root_logger.addHandler(debug_handler)

        # 4. Console handler (optional, only for errors)
        if cls.LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        cls._initialized = True

        # Log initialization
        init_logger = logging.getLogger(__name__)
        init_logger.info(
            "Logging system initialized",
            extra={"extra_fields": {
                "log_level": cls.LOG_LEVEL,
                "log_dir": str(cls.LOG_DIR),
                "console_logging": cls.LOG_TO_CONSOLE
            }}
        )

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance with the specified name.

        Args:
            name: The name of the logger (typically __name__)

        Returns:
            Configured logger instance
        """
        if not cls._initialized:
            cls.setup_logging()

        return logging.getLogger(name)


# Convenience function for getting loggers
def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger (typically __name__)

    Returns:
        Configured logger instance

    Example:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.error("An error occurred", extra={"extra_fields": {"user_id": "123"}})
    """
    return LoggerConfig.get_logger(name)


# Initialize logging on module import
LoggerConfig.setup_logging()
