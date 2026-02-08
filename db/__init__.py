"""
Database package for CortexAI.
Provides SQLAlchemy engine, session management, table reflection, and repository functions.
"""

from db.engine import get_engine
from db.session import get_db, SessionLocal
from db.tables import (
    metadata,
    get_table,
    # Individual table getters exported via __getattr__ in tables.py
)
from db.repository import (
    # User & Auth
    get_or_create_cli_user,
    get_user_by_api_key,  # Returns (user_id, api_key_id) tuple
    update_api_key_last_used,

    # Session Management
    create_session,
    get_active_session,
    get_session_by_id,
    verify_session_belongs_to_user,
    update_session_timestamp,

    # Message Management
    save_message,
    get_session_messages,

    # Context Snapshots
    get_latest_context_snapshot,
    create_context_snapshot,

    # LLM Audit
    create_llm_request,
    create_llm_response,

    # Usage Tracking
    get_usage_daily,
    upsert_usage_daily,
    check_usage_limit,

    # User Preferences
    get_user_preferences,

    # Compare Mode
    save_compare_summary,

    # Utility
    compute_prompt_sha256,
    compute_context_hash,
)

__all__ = [
    "get_engine",
    "get_db",
    "SessionLocal",
    "metadata",
    "get_table",
    # Repository functions
    "get_or_create_cli_user",
    "get_user_by_api_key",
    "update_api_key_last_used",
    "create_session",
    "get_active_session",
    "get_session_by_id",
    "verify_session_belongs_to_user",
    "update_session_timestamp",
    "save_message",
    "get_session_messages",
    "get_latest_context_snapshot",
    "create_context_snapshot",
    "create_llm_request",
    "create_llm_response",
    "get_usage_daily",
    "upsert_usage_daily",
    "check_usage_limit",
    "get_user_preferences",
    "save_compare_summary",
    "compute_prompt_sha256",
    "compute_context_hash",
]
