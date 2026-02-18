"""
Database package for CortexAI.
Provides SQLAlchemy engine, session management, table reflection, and repository functions.
"""

from db.engine import get_engine
from db.repository import (
    check_usage_limit,
    compute_context_hash,
    compute_api_key_hash,
    create_api_key,
    create_routing_attempts,
    create_routing_decision,
    # Utility
    compute_prompt_sha256,
    create_context_snapshot,
    # LLM Audit
    create_llm_request,
    create_llm_response,
    generate_api_key,
    # Session Management
    create_session,
    get_active_session,
    # Context Snapshots
    get_latest_context_snapshot,
    # User & Auth
    get_or_create_cli_user,
    get_or_create_service_user,
    get_session_by_id,
    get_session_messages,
    # Usage Tracking
    get_usage_daily,
    get_user_by_api_key,  # Returns (user_id, api_key_id) tuple
    # User Preferences
    get_user_preferences,
    # Compare Mode
    save_compare_summary,
    # Message Management
    save_message,
    update_api_key_last_used,
    update_session_timestamp,
    upsert_usage_daily,
    verify_session_belongs_to_user,
)
from db.session import SessionLocal, get_db
from db.tables import (
    get_table,
    # Individual table getters exported via __getattr__ in tables.py
    metadata,
)

__all__ = [
    "SessionLocal",
    "check_usage_limit",
    "compute_api_key_hash",
    "compute_context_hash",
    "compute_prompt_sha256",
    "create_api_key",
    "create_context_snapshot",
    "create_llm_request",
    "create_llm_response",
    "generate_api_key",
    "create_routing_attempts",
    "create_routing_decision",
    "create_session",
    "get_active_session",
    "get_db",
    "get_engine",
    "get_latest_context_snapshot",
    "get_or_create_cli_user",
    "get_or_create_service_user",
    "get_session_by_id",
    "get_session_messages",
    "get_table",
    "get_usage_daily",
    "get_user_by_api_key",
    "get_user_preferences",
    "metadata",
    "save_compare_summary",
    "save_message",
    "update_api_key_last_used",
    "update_session_timestamp",
    "upsert_usage_daily",
    "verify_session_belongs_to_user",
]
