"""SQLite database helper for chat history persistence."""

import sqlite3
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

# Store the DB file alongside the project root
_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cortexai_history.db")


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with row_factory."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the chat_history table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                mode        TEXT NOT NULL,
                prompt      TEXT NOT NULL,
                provider    TEXT NOT NULL,
                model       TEXT NOT NULL,
                response    TEXT NOT NULL,
                latency_ms  INTEGER,
                tokens      INTEGER,
                cost        REAL
            )
        """)
        conn.commit()
    logger.info("Database initialised at %s", _DB_PATH)


def save_chat(
    *,
    prompt: str,
    provider: str,
    model: str,
    response: str,
    latency_ms: Optional[int] = None,
    tokens: Optional[int] = None,
    cost: Optional[float] = None,
    mode: str = "chat",
) -> int:
    """Insert one history record and return the new row id."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO chat_history
               (timestamp, mode, prompt, provider, model, response, latency_ms, tokens, cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, mode, prompt, provider, model, response, latency_ms, tokens, cost),
        )
        conn.commit()
        return cur.lastrowid


def get_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent history entries, newest first."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_history_entry(entry_id: int) -> bool:
    """Delete a single history entry. Returns True if a row was removed."""
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM chat_history WHERE id = ?", (entry_id,))
        conn.commit()
    return cur.rowcount > 0


def clear_all_history() -> int:
    """Delete all history entries. Returns count of deleted rows."""
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM chat_history")
        conn.commit()
    return cur.rowcount
