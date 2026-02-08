"""
SQLAlchemy table reflection for existing PostgreSQL schema.

CRITICAL: This module does NOT create tables. Tables must already exist in PostgreSQL.
It only reflects the schema into SQLAlchemy Table objects for querying.
"""

import os
from typing import Dict
from sqlalchemy import MetaData, Table
from db.engine import get_engine

# Import logger
from utils.logger import get_logger

logger = get_logger(__name__)


# Schema name from environment (default: public)
DB_SCHEMA = os.getenv("DB_SCHEMA", "public")

# Metadata container for reflected tables
metadata = MetaData()

# Table cache for lazy loading
_tables_cache: Dict[str, Table] = {}

# All table names in the database
TABLE_NAMES = [
    "users",
    "api_keys",
    "user_preferences",
    "sessions",
    "messages",
    "context_snapshots",
    "llm_requests",
    "llm_responses",
    "usage_daily",
    "wallets",
    "ledger_entries",
    "feedback",
]


def reflect_table(table_name: str) -> Table:
    """
    Reflect a single table from the database.

    Args:
        table_name: Name of the table to reflect

    Returns:
        Table: Reflected SQLAlchemy Table object

    Raises:
        sqlalchemy.exc.NoSuchTableError: If table doesn't exist in database
    """
    try:
        logger.debug(f"Reflecting table: {table_name} from schema: {DB_SCHEMA}")
    except:
        pass

    table = Table(
        table_name,
        metadata,
        autoload_with=get_engine(),
        schema=DB_SCHEMA,
    )
    return table


def get_table(name: str) -> Table:
    """
    Get a reflected table (lazy loading with caching).

    Args:
        name: Table name

    Returns:
        Table: SQLAlchemy Table object

    Raises:
        ValueError: If table name is not recognized
        Exception: If table doesn't exist in database
    """
    if name not in TABLE_NAMES:
        raise ValueError(
            f"Unknown table name: {name}. "
            f"Available tables: {', '.join(TABLE_NAMES)}"
        )

    if name not in _tables_cache:
        try:
            _tables_cache[name] = reflect_table(name)
        except Exception as e:
            logger.error(
                f"Failed to reflect table {name}. "
                f"Ensure DATABASE_URL is correct and table exists in PostgreSQL."
            )
            raise

    return _tables_cache[name]


# Module-level __getattr__ for clean imports
# Allows: from db.tables import users, sessions
def __getattr__(name: str):
    """
    Enable direct table imports: from db.tables import users, sessions

    Args:
        name: Attribute name (table name)

    Returns:
        Table: SQLAlchemy Table object
    """
    if name in TABLE_NAMES:
        return get_table(name)
    raise AttributeError(f"module 'db.tables' has no attribute '{name}'")


# Pre-load critical tables for better error messages at startup
# (Optional - comment out if you want fully lazy loading)
try:
    _critical_tables = ["users", "sessions", "messages", "llm_requests", "llm_responses"]
    for table_name in _critical_tables:
        get_table(table_name)
    logger.info(f"Successfully reflected {len(_critical_tables)} critical tables")
except Exception as e:
    logger.warning(
        f"Could not pre-load critical tables: {e}. "
        f"Tables will be loaded on first use."
    )
