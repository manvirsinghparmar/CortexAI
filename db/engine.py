"""
SQLAlchemy engine configuration for PostgreSQL.
Supports local and AWS RDS/Aurora via DATABASE_URL environment variable.
"""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import StaticPool

# Import logger
from utils.logger import get_logger

logger = get_logger(__name__)


def get_database_url() -> str:
    """
    Retrieve DATABASE_URL from environment.

    Returns:
        str: Database URL (already URL-encoded by user)

    Raises:
        ValueError: If DATABASE_URL not set

    Example URLs:
        Local: postgresql+psycopg://cortex:password@localhost:5432/cortexai
        AWS:   postgresql+psycopg://cortex:password@rds-endpoint:5432/cortexai?sslmode=require
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "DATABASE_URL environment variable not set. "
            "Set it in .env file. Example: "
            "DATABASE_URL=postgresql+psycopg://cortex:password@localhost:5432/cortexai"
        )
    return db_url


def create_db_engine() -> Engine:
    """
    Create SQLAlchemy engine with AWS-safe pooling configuration.

    Configuration via environment variables:
    - DATABASE_URL: Full database URL (required)
    - DB_POOL_SIZE: Connection pool size (default: 5)
    - DB_MAX_OVERFLOW: Max overflow connections (default: 10)
    - DB_POOL_TIMEOUT: Pool checkout timeout in seconds (default: 30)

    Returns:
        Engine: Configured SQLAlchemy engine
    """
    database_url = get_database_url()

    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    parsed_url = make_url(database_url)
    dialect = parsed_url.get_backend_name().lower()
    is_sqlite = dialect == "sqlite"
    sqlite_in_memory = is_sqlite and (
        (parsed_url.database or "") in {"", ":memory:"}
        or "mode=memory" in str(database_url).lower()
    )

    # Log engine creation
    logger.info(
        "Creating database engine",
        extra={
            "extra_fields": {
                "dialect": dialect,
                "pool_size": pool_size,
                "max_overflow": max_overflow,
                "pool_timeout": pool_timeout,
                "ssl_enabled": "sslmode=require" in database_url,
            }
        },
    )

    # SQLite does not accept QueuePool-only options such as max_overflow/pool_timeout.
    if is_sqlite:
        sqlite_kwargs: dict[str, object] = {
            "pool_pre_ping": True,
            "echo": False,
        }
        if sqlite_in_memory:
            # Share one in-memory DB connection across the app/test process.
            sqlite_kwargs["poolclass"] = StaticPool
            sqlite_kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_engine(database_url, **sqlite_kwargs)
    else:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,  # AWS-safe: validate connections before use
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            echo=False,  # Set to True for SQL debugging
        )

    return engine


# Lazy engine singleton
_ENGINE: Engine | None = None


def get_engine() -> Engine:
    """
    Get or create the database engine (lazy initialization).

    Returns:
        Engine: SQLAlchemy engine singleton

    Note:
        Engine is created on first call, not at module import time.
        This prevents crashes if DATABASE_URL is not set during imports.
    """
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_db_engine()
    return _ENGINE
