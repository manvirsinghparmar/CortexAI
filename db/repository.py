"""
Repository layer for CortexAI database operations.
All CRUD functions using SQLAlchemy Core with reflected tables.

Design principles:
- Functions do NOT commit - caller commits for transaction control
- Returns None or raises exceptions on errors
- Uses SQLAlchemy Core (insert/select/update) not ORM
"""

import hashlib
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert  # For UPSERT
from sqlalchemy.orm import Session

# Import logger
from utils.logger import get_logger

logger = get_logger(__name__)

# Import UnifiedResponse for type hints
try:
    from models.unified_response import UnifiedResponse
except ImportError:
    UnifiedResponse = Any  # Fallback if import fails


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def compute_prompt_sha256(prompt: str) -> str:
    """
    Compute SHA-256 hash of prompt for deduplication/indexing.

    Args:
        prompt: The user's prompt text

    Returns:
        str: Hexadecimal SHA-256 hash
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def compute_context_hash(context: str) -> str:
    """
    Compute SHA-256 hash of context for deduplication.

    Args:
        context: The context text

    Returns:
        str: Hexadecimal SHA-256 hash
    """
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


def compute_api_key_hash(api_key: str) -> str:
    """
    Compute SHA-256 hash of API key for secure comparison.

    NOTE: Check server/dependencies.py for existing hash function.
    If auth already uses a different hashing method (bcrypt, argon2, etc.),
    import and use that function instead.

    Args:
        api_key: Plaintext API key (from X-API-Key header)

    Returns:
        str: Hexadecimal SHA-256 hash
    """
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


# ============================================================================
# USER & API KEY MANAGEMENT
# ============================================================================


def get_or_create_cli_user(
    db: Session, email: str = "cli@cortexai.local", display_name: str = "CLI User"
) -> UUID:
    """
    Get or create a default CLI user for local testing.

    This is a temporary solution for CLI usage. When authentication is ready,
    use get_user_by_api_key() or JWT-based user resolution instead.

    Args:
        db: Database session
        email: User email (default: cli@cortexai.local)
        display_name: Display name (default: CLI User)

    Returns:
        UUID: user_id

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    users = get_table("users")

    # Check if CLI user exists
    stmt = select(users.c.id).where(users.c.email == email)
    user_id = db.execute(stmt).scalar_one_or_none()

    if user_id:
        return user_id

    # Create CLI user
    stmt = (
        insert(users)
        .values(
            email=email,
            display_name=display_name,
            is_active=True,
            auth_provider="cli",
            auth_subject="local-cli",
            auth_issuer="cortexai",
        )
        .returning(users.c.id)
    )

    user_id = db.execute(stmt).scalar_one()

    logger.info(f"Created CLI user: {email} (id: {user_id})")

    return user_id


def get_user_by_api_key(db: Session, api_key: str) -> tuple[UUID, UUID] | None:
    """
    Look up user_id AND api_key_id from API key via api_keys table.

    CRITICAL: Returns BOTH user_id and api_key_id for proper attribution.
    - user_id: Used for sessions, usage enforcement, ownership
    - api_key_id: Stored in llm_requests for audit trail (which key was used)

    IMPORTANT: Check server/dependencies.py for existing API key verification.
    If it already has a hash function, use that instead of compute_api_key_hash().

    Args:
        db: Database session
        api_key: Plaintext API key from X-API-Key header

    Returns:
        tuple[UUID, UUID]: (user_id, api_key_id) if found, None otherwise
    """
    from db.tables import get_table

    api_keys = get_table("api_keys")

    # Hash the API key (adjust if using different hash method)
    key_hash = compute_api_key_hash(api_key)

    # Look up BOTH user_id and api_key_id
    stmt = select(api_keys.c.user_id, api_keys.c.id).where(
        and_(api_keys.c.key_hash == key_hash, api_keys.c.is_active)
    )
    result = db.execute(stmt).first()

    if result:
        user_id, api_key_id = result
        logger.debug(f"API key matched to user_id: {user_id}, api_key_id: {api_key_id}")
        return (user_id, api_key_id)
    else:
        logger.warning(f"API key not found or inactive: {key_hash[:8]}...")
        return None


def update_api_key_last_used(db: Session, api_key: str) -> None:
    """
    Update api_keys.last_used_at timestamp.

    Args:
        db: Database session
        api_key: Plaintext API key

    Note:
        Does NOT commit. Fails silently if key not found.
    """
    from db.tables import get_table

    api_keys = get_table("api_keys")

    key_hash = compute_api_key_hash(api_key)

    stmt = update(api_keys).where(api_keys.c.key_hash == key_hash).values(last_used_at=func.now())

    db.execute(stmt)


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================


def create_session(db: Session, user_id: UUID, mode: str = "ask", title: str | None = None) -> UUID:
    """
    Create a new chat session.

    Args:
        db: Database session
        user_id: User ID
        mode: Session mode ('ask', 'compare', 'eval', 'research')
        title: Optional session title

    Returns:
        UUID: session_id

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    sessions = get_table("sessions")

    stmt = (
        insert(sessions)
        .values(
            user_id=user_id,
            title=title,
            mode=mode,
        )
        .returning(sessions.c.id)
    )

    session_id = db.execute(stmt).scalar_one()

    logger.info(f"Created session: {session_id} for user: {user_id}, mode: {mode}")

    return session_id


def get_active_session(db: Session, user_id: UUID, mode: str = "ask") -> UUID | None:
    """
    Get user's most recent active session for given mode.

    Args:
        db: Database session
        user_id: User ID
        mode: Session mode (default: 'ask')

    Returns:
        UUID: session_id if found, None otherwise
    """
    from db.tables import get_table

    sessions = get_table("sessions")

    stmt = (
        select(sessions.c.id)
        .where(and_(sessions.c.user_id == user_id, sessions.c.mode == mode))
        .order_by(desc(sessions.c.updated_at))
        .limit(1)
    )

    return db.execute(stmt).scalar_one_or_none()


def get_session_by_id(db: Session, session_id: UUID) -> dict[str, Any] | None:
    """
    Get session metadata by ID.

    Args:
        db: Database session
        session_id: Session ID

    Returns:
        dict: Session data or None if not found
    """
    from db.tables import get_table

    sessions = get_table("sessions")

    stmt = select(sessions).where(sessions.c.id == session_id)
    result = db.execute(stmt).first()

    if result:
        return dict(result._mapping)
    return None


def verify_session_belongs_to_user(db: Session, session_id: UUID, user_id: UUID) -> bool:
    """
    Verify that a session belongs to a user.

    Args:
        db: Database session
        session_id: Session ID
        user_id: User ID

    Returns:
        bool: True if session belongs to user, False otherwise
    """
    from db.tables import get_table

    sessions = get_table("sessions")

    stmt = select(sessions.c.id).where(
        and_(sessions.c.id == session_id, sessions.c.user_id == user_id)
    )

    result = db.execute(stmt).scalar_one_or_none()
    return result is not None


def update_session_timestamp(db: Session, session_id: UUID) -> None:
    """
    Update sessions.updated_at to current timestamp.

    Args:
        db: Database session
        session_id: Session ID

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    sessions = get_table("sessions")

    stmt = update(sessions).where(sessions.c.id == session_id).values(updated_at=func.now())

    db.execute(stmt)


# ============================================================================
# MESSAGE MANAGEMENT
# ============================================================================


def save_message(db: Session, session_id: UUID, role: str, content: str) -> UUID:
    """
    Insert a message into the messages table.

    Args:
        db: Database session
        session_id: Session ID
        role: Message role ('user' or 'assistant')
        content: Message content

    Returns:
        UUID: message_id

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    messages = get_table("messages")

    stmt = (
        insert(messages)
        .values(session_id=session_id, role=role, content=content)
        .returning(messages.c.id)
    )

    message_id = db.execute(stmt).scalar_one()

    logger.debug(f"Saved {role} message to session {session_id}: {message_id}")

    return message_id


def get_session_messages(
    db: Session, session_id: UUID, limit: int = 10, offset: int = 0
) -> list[dict[str, Any]]:
    """
    Get messages for a session (for building context).

    Args:
        db: Database session
        session_id: Session ID
        limit: Maximum number of messages to return (default: 10)
        offset: Number of messages to skip (default: 0)

    Returns:
        list: List of message dicts, ordered by created_at ASC

    Note:
        Returns messages in chronological order (oldest first) for context building.
    """
    from db.tables import get_table

    messages = get_table("messages")

    stmt = (
        select(messages)
        .where(messages.c.session_id == session_id)
        .order_by(desc(messages.c.created_at))
        .limit(limit)
        .offset(offset)
    )

    results = db.execute(stmt).fetchall()

    # Reverse to get chronological order (oldest first)
    messages_list = [dict(row._mapping) for row in reversed(results)]

    return messages_list


# ============================================================================
# CONTEXT SNAPSHOTS
# ============================================================================


def get_latest_context_snapshot(db: Session, session_id: UUID) -> dict[str, Any] | None:
    """
    Get the most recent context snapshot for a session.

    Args:
        db: Database session
        session_id: Session ID

    Returns:
        dict: Snapshot data or None if no snapshot exists
    """
    from db.tables import get_table

    context_snapshots = get_table("context_snapshots")

    stmt = (
        select(context_snapshots)
        .where(context_snapshots.c.session_id == session_id)
        .order_by(desc(context_snapshots.c.created_at))
        .limit(1)
    )

    result = db.execute(stmt).first()

    if result:
        return dict(result._mapping)
    return None


def create_context_snapshot(
    db: Session,
    user_id: UUID,
    session_id: UUID,
    context_text: str,
    base_message_id: UUID | None = None,
) -> UUID:
    """
    Create a new context snapshot (with hash-based deduplication).

    Args:
        db: Database session
        user_id: User ID
        session_id: Session ID
        context_text: The full context text
        base_message_id: Optional ID of the message this context is based on

    Returns:
        UUID: snapshot_id

    Note:
        Does NOT commit. Caller must commit.
        Uses ON CONFLICT DO NOTHING for hash-based deduplication.
    """
    from db.tables import get_table

    context_snapshots = get_table("context_snapshots")

    context_hash = compute_context_hash(context_text)

    # Use PostgreSQL UPSERT to handle duplicate hash
    stmt = (
        pg_insert(context_snapshots)
        .values(
            user_id=user_id,
            session_id=session_id,
            base_message_id=base_message_id,
            context_hash=context_hash,
            context_text=context_text,
        )
        .on_conflict_do_nothing(index_elements=["session_id", "context_hash"])
        .returning(context_snapshots.c.id)
    )

    result = db.execute(stmt).scalar_one_or_none()

    if result:
        logger.debug(f"Created context snapshot: {result}")
        return result
    else:
        # Snapshot with same hash already exists, fetch it
        stmt = select(context_snapshots.c.id).where(
            and_(
                context_snapshots.c.session_id == session_id,
                context_snapshots.c.context_hash == context_hash,
            )
        )
        existing_id = db.execute(stmt).scalar_one()
        logger.debug(f"Context snapshot already exists: {existing_id}")
        return existing_id


# ============================================================================
# LLM AUDIT LOGGING
# ============================================================================


def create_llm_request(
    db: Session,
    user_id: UUID,
    request_id: str,
    route_mode: str,
    provider: str,
    model: str,
    prompt: str,
    session_id: UUID | None = None,
    api_key_id: UUID | None = None,
    input_tokens_est: int | None = None,
    store_prompt: bool = False,
) -> UUID:
    """
    Insert a row into llm_requests table.

    Args:
        db: Database session
        user_id: User ID
        request_id: Unique request ID (from UnifiedResponse)
        route_mode: Route mode ('ask', 'compare', 'eval', 'research')
        provider: LLM provider name (e.g., 'openai')
        model: Model name (e.g., 'gpt-4')
        prompt: User's prompt text
        session_id: Optional session ID
        api_key_id: Optional API key ID (if request via API)
        input_tokens_est: Optional estimated input tokens
        store_prompt: Whether to store raw prompt text (default: False for privacy)

    Returns:
        UUID: The llm_requests.id of the inserted row

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    llm_requests = get_table("llm_requests")

    prompt_sha256 = compute_prompt_sha256(prompt)

    stmt = (
        insert(llm_requests)
        .values(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            route_mode=route_mode,
            provider=provider,
            model=model,
            prompt_sha256=prompt_sha256,
            prompt_stored=store_prompt,
            prompt_text=prompt if store_prompt else None,
            input_tokens_est=input_tokens_est,
            api_key_id=api_key_id,
        )
        .returning(llm_requests.c.id)
    )

    llm_request_id = db.execute(stmt).scalar_one()

    logger.debug(
        f"Created llm_request: {llm_request_id} "
        f"(request_id: {request_id}, provider: {provider}, model: {model})"
    )

    return llm_request_id


def create_llm_response(db: Session, llm_request_id: UUID, response: UnifiedResponse) -> None:
    """
    Insert a row into llm_responses table from UnifiedResponse.

    Args:
        db: Database session
        llm_request_id: Foreign key to llm_requests.id
        response: UnifiedResponse object from orchestrator

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    llm_responses = get_table("llm_responses")

    # Extract error info if present
    error_type = None
    error_message = None
    if hasattr(response, "error") and response.error:
        error_type = response.error.code
        error_message = response.error.message

    stmt = insert(llm_responses).values(
        llm_request_id=llm_request_id,
        text=response.text,
        finish_reason=response.finish_reason,
        latency_ms=response.latency_ms,
        prompt_tokens=response.token_usage.prompt_tokens,
        completion_tokens=response.token_usage.completion_tokens,
        total_tokens=response.token_usage.total_tokens,
        estimated_cost=response.estimated_cost,
        error_type=error_type,
        error_message=error_message,
    )

    db.execute(stmt)

    logger.debug(f"Created llm_response for request: {llm_request_id}")


# ============================================================================
# USAGE TRACKING & ENFORCEMENT
# ============================================================================


def get_usage_daily(
    db: Session, user_id: UUID, usage_date: date | None = None
) -> dict[str, Any] | None:
    """
    Get usage_daily row for user and date.

    Args:
        db: Database session
        user_id: User ID
        usage_date: Date to query (default: today)

    Returns:
        dict: Usage data or None if no usage today
    """
    from db.tables import get_table

    usage_daily = get_table("usage_daily")

    if usage_date is None:
        usage_date = date.today()

    stmt = select(usage_daily).where(
        and_(usage_daily.c.user_id == user_id, usage_daily.c.usage_date == usage_date)
    )

    result = db.execute(stmt).first()

    if result:
        return dict(result._mapping)
    return None


def upsert_usage_daily(
    db: Session,
    user_id: UUID,
    total_tokens: int,
    estimated_cost: float,
    usage_date: date | None = None,
) -> None:
    """
    Upsert (INSERT or UPDATE) usage_daily for user and date.

    Uses PostgreSQL ON CONFLICT to handle both insert and update in one query.

    Args:
        db: Database session
        user_id: User ID
        total_tokens: Tokens to add
        estimated_cost: Cost to add
        usage_date: Date to update (default: today)

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    usage_daily = get_table("usage_daily")

    if usage_date is None:
        usage_date = date.today()

    # PostgreSQL UPSERT
    stmt = (
        pg_insert(usage_daily)
        .values(
            user_id=user_id,
            usage_date=usage_date,
            total_requests=1,
            total_tokens=total_tokens,
            total_cost=estimated_cost,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "usage_date"],
            set_=dict(
                total_requests=usage_daily.c.total_requests + 1,
                total_tokens=usage_daily.c.total_tokens + total_tokens,
                total_cost=usage_daily.c.total_cost + estimated_cost,
            ),
        )
    )

    db.execute(stmt)

    logger.debug(
        f"Updated usage_daily for user {user_id}: "
        f"+{total_tokens} tokens, +${estimated_cost:.6f}"
    )


def check_usage_limit(
    db: Session, user_id: UUID, token_cap: int | None = None, cost_cap: float | None = None
) -> dict[str, Any]:
    """
    Check if user has exceeded usage limits for today.

    Args:
        db: Database session
        user_id: User ID
        token_cap: Max tokens per day (None = no limit)
        cost_cap: Max cost per day in dollars (None = no limit)

    Returns:
        dict: {
            "allowed": bool,
            "current_tokens": int,
            "current_cost": float,
            "reason": str (if denied)
        }
    """
    usage = get_usage_daily(db, user_id)

    if usage is None:
        # No usage today - allowed
        return {"allowed": True, "current_tokens": 0, "current_cost": 0.0}

    current_tokens = usage["total_tokens"]
    current_cost = float(usage["total_cost"])

    # Check token cap
    if token_cap is not None and current_tokens >= token_cap:
        return {
            "allowed": False,
            "current_tokens": current_tokens,
            "current_cost": current_cost,
            "reason": f"Daily token limit exceeded ({current_tokens}/{token_cap})",
        }

    # Check cost cap
    if cost_cap is not None and current_cost >= cost_cap:
        return {
            "allowed": False,
            "current_tokens": current_tokens,
            "current_cost": current_cost,
            "reason": f"Daily cost limit exceeded (${current_cost:.2f}/${cost_cap:.2f})",
        }

    # Allowed
    return {"allowed": True, "current_tokens": current_tokens, "current_cost": current_cost}


# ============================================================================
# USER PREFERENCES
# ============================================================================


def get_user_preferences(db: Session, user_id: UUID) -> dict[str, Any] | None:
    """
    Get user preferences.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        dict: Preferences or None if not set
    """
    from db.tables import get_table

    user_preferences = get_table("user_preferences")

    stmt = select(user_preferences).where(user_preferences.c.user_id == user_id)

    result = db.execute(stmt).first()

    if result:
        return dict(result._mapping)
    return None


# ============================================================================
# COMPARE MODE
# ============================================================================


def save_compare_summary(
    db: Session, session_id: UUID, responses: list[UnifiedResponse], selected_model_index: int = 0
) -> UUID:
    """
    Build and save a compare summary message from multiple model responses.

    CRITICAL COMPARE MODE PERSISTENCE:
    - N llm_requests + llm_responses (one per model) - already persisted separately
    - ONE assistant message in messages table (this function)
    - Summary includes selected answer for conversation continuity
    - Compact results for all models with request IDs for traceability

    Args:
        db: Database session
        session_id: Session ID
        responses: List of UnifiedResponse objects from different models
        selected_model_index: Index of response to use as "selected answer" (default: 0)

    Returns:
        UUID: message_id of the assistant summary

    Note:
        Does NOT commit. Caller must commit.

    Summary Format:
        **Selected Answer:** (from Model A)
        [Answer text]

        **Comparison Results:**
        1. Model A: [cost, tokens, latency, request_id]
           [preview/full text]
        2. Model B: [cost, tokens, latency, request_id]
           [preview/full text]
    """
    if not responses:
        raise ValueError("Cannot create compare summary from empty responses list")

    # Validate index
    if selected_model_index >= len(responses):
        selected_model_index = 0

    selected = responses[selected_model_index]

    # Build summary in structured markdown format
    summary_parts = []

    # Part 1: Selected answer (for conversation continuity)
    summary_parts.append(
        f"**Selected Answer** (from {selected.provider.title()} {selected.model}):"
    )
    summary_parts.append(f"{selected.text}\n")
    summary_parts.append("---\n")

    # Part 2: Compact comparison results
    summary_parts.append("**Comparison Results:**\n")

    for i, resp in enumerate(responses, 1):
        # Model header with compact stats
        is_selected = (i - 1) == selected_model_index
        selected_marker = " ✓" if is_selected else ""

        summary_parts.append(f"\n**{i}. {resp.provider.title()} - {resp.model}{selected_marker}**")
        summary_parts.append(
            f"_Cost: ${resp.estimated_cost:.6f} | "
            f"Tokens: {resp.token_usage.total_tokens} | "
            f"Latency: {resp.latency_ms}ms | "
            f"Request ID: `{resp.request_id[:8]}...`_\n"
        )

        # Response preview (full text if selected, preview otherwise)
        if is_selected:
            summary_parts.append("(See selected answer above)")
        else:
            # Show preview (first 200 chars)
            preview = resp.text[:200] + "..." if len(resp.text) > 200 else resp.text
            summary_parts.append(f"{preview}")

        summary_parts.append("\n---")

    summary = "\n".join(summary_parts)

    # Save as single assistant message
    return save_message(db, session_id, role="assistant", content=summary)
