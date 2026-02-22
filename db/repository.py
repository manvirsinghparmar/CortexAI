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
from utils.api_key_utils import (
    compute_api_key_hash as _compute_api_key_hash,
    generate_api_key as _generate_api_key,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Import UnifiedResponse for type hints
try:
    from models.unified_response import UnifiedResponse
except ImportError:
    UnifiedResponse = Any  # Fallback if import fails

ALLOWED_PROMPT_CATEGORIES = {
    "coding",
    "financial",
    "educational",
    "math",
    "legal",
    "data_technical",
    "general",
    "unknown",
}

ALLOWED_RESEARCH_MODES = {"off", "auto", "on"}
ALLOWED_ROUTING_MODES = {"smart", "cheap", "strong", "explicit", "legacy"}
SERVICE_AUTH_PROVIDER = "service"
SERVICE_AUTH_SUBJECT = "api-service"
SERVICE_AUTH_ISSUER = "cortexai"


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
    return _compute_api_key_hash(api_key)


def generate_api_key(prefix: str = "cortex") -> str:
    """
    Generate a random API key string.

    Args:
        prefix: Key prefix label

    Returns:
        str: API key (raw, return-once secret)
    """
    return _generate_api_key(prefix)


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


def get_or_create_service_user(
    db: Session, email: str = "api@cortexai.local", display_name: str = "API Service User"
) -> UUID:
    """
    Get or create deterministic service user for API fallback/autoreg paths.

    Uses a dedicated auth identity that cannot collide with CLI identity:
    - auth_provider=service
    - auth_subject=api-service
    - auth_issuer=cortexai

    Args:
        db: Database session
        email: Service user email
        display_name: Service user display name

    Returns:
        UUID: user_id

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    users = get_table("users")

    # Identity-first lookup guarantees deterministic resolution.
    by_identity_stmt = select(users.c.id).where(
        and_(
            users.c.auth_provider == SERVICE_AUTH_PROVIDER,
            users.c.auth_subject == SERVICE_AUTH_SUBJECT,
            users.c.auth_issuer == SERVICE_AUTH_ISSUER,
        )
    )
    service_user_id = db.execute(by_identity_stmt).scalar_one_or_none()
    if service_user_id:
        return service_user_id

    # Protect against accidental email reuse by a non-service principal.
    by_email_stmt = select(
        users.c.id,
        users.c.auth_provider,
        users.c.auth_subject,
        users.c.auth_issuer,
    ).where(users.c.email == email)
    existing_email_user = db.execute(by_email_stmt).first()
    if existing_email_user:
        existing_id, provider, subject, issuer = existing_email_user
        if (
            provider == SERVICE_AUTH_PROVIDER
            and subject == SERVICE_AUTH_SUBJECT
            and issuer == SERVICE_AUTH_ISSUER
        ):
            return existing_id
        raise ValueError(
            "Configured API fallback user email is already used by a non-service identity. "
            f"email={email}"
        )

    stmt = (
        insert(users)
        .values(
            email=email,
            display_name=display_name,
            is_active=True,
            auth_provider=SERVICE_AUTH_PROVIDER,
            auth_subject=SERVICE_AUTH_SUBJECT,
            auth_issuer=SERVICE_AUTH_ISSUER,
        )
        .returning(users.c.id)
    )

    service_user_id = db.execute(stmt).scalar_one()
    logger.info(f"Created service user: {email} (id: {service_user_id})")
    return service_user_id


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
    request_group_id: UUID | None = None,
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
        request_group_id: Optional grouping UUID for multi-response flows (e.g., compare mode)
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
    values: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "request_id": request_id,
        "route_mode": route_mode,
        "provider": provider,
        "model": model,
        "prompt_sha256": prompt_sha256,
        "prompt_stored": store_prompt,
        "prompt_text": prompt if store_prompt else None,
        "input_tokens_est": input_tokens_est,
        "api_key_id": api_key_id,
    }
    column_names = {col.name for col in llm_requests.columns}
    if "request_group_id" in column_names:
        values["request_group_id"] = request_group_id

    stmt = insert(llm_requests).values(**values).returning(llm_requests.c.id)

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


def _build_api_key_insert_values(
    api_keys_table,
    *,
    user_id: UUID,
    key_hash: str,
    raw_api_key: str,
    label: str | None,
) -> dict[str, Any]:
    """
    Build insert payload for api_keys table while supporting schema variants.
    """
    values: dict[str, Any] = {"user_id": user_id, "key_hash": key_hash}
    column_names = {col.name for col in api_keys_table.columns}

    if "label" in column_names and label is not None:
        values["label"] = label
    if "name" in column_names and label is not None:
        values["name"] = label
    if "is_active" in column_names:
        values["is_active"] = True

    key_prefix = raw_api_key[:12]
    key_last4 = raw_api_key[-4:]
    if "key_prefix" in column_names:
        values["key_prefix"] = key_prefix
    if "prefix" in column_names:
        values["prefix"] = key_prefix
    if "key_last4" in column_names:
        values["key_last4"] = key_last4
    if "last4" in column_names:
        values["last4"] = key_last4

    missing_required: list[str] = []
    for col in api_keys_table.columns:
        if col.name in values:
            continue
        if col.nullable:
            continue
        if col.default is not None or col.server_default is not None:
            continue
        if col.primary_key:
            continue
        missing_required.append(col.name)

    if missing_required:
        raise ValueError(
            "api_keys has required columns not handled by insert payload: "
            f"{', '.join(sorted(missing_required))}"
        )

    return values


def create_api_key(
    db: Session,
    *,
    user_id: UUID,
    raw_api_key: str,
    label: str | None = None,
) -> tuple[UUID, UUID]:
    """
    Create or reuse API key mapping in api_keys table.

    Args:
        db: Database session
        user_id: User ID to own the key
        raw_api_key: Raw API key secret (will be hashed; not stored)
        label: Optional label/name for key

    Returns:
        tuple[UUID, UUID]: (api_key_id, owner_user_id)

    Note:
        Does NOT commit. Caller must commit.
        If key hash already exists for another owner, existing owner is always returned.
    """
    from db.tables import get_table

    api_keys = get_table("api_keys")
    key_hash = compute_api_key_hash(raw_api_key)

    # Reuse existing mapping if hash already exists.
    existing_stmt = select(api_keys.c.id, api_keys.c.user_id).where(api_keys.c.key_hash == key_hash)
    existing = db.execute(existing_stmt).first()
    if existing:
        api_key_id, owner_user_id = existing
        if owner_user_id != user_id:
            logger.warning(
                "API key hash already mapped to different owner; forcing existing owner",
                extra={
                    "extra_fields": {
                        "api_key_id": str(api_key_id),
                        "existing_owner_user_id": str(owner_user_id),
                        "requested_user_id": str(user_id),
                    }
                },
            )
        logger.debug(f"API key hash already exists: {str(api_key_id)[:8]}...")
        return api_key_id, owner_user_id

    values = _build_api_key_insert_values(
        api_keys,
        user_id=user_id,
        key_hash=key_hash,
        raw_api_key=raw_api_key,
        label=label,
    )

    stmt = insert(api_keys).values(**values).returning(api_keys.c.id)
    api_key_id = db.execute(stmt).scalar_one()
    logger.info(
        f"Created api_key mapping: api_key_id={api_key_id}, "
        f"user_id={user_id}, label={label or 'n/a'}"
    )
    return api_key_id, user_id


def _safe_json_dict(payload: Any) -> dict[str, Any]:
    """Ensure payload is JSONB-safe dict-like data."""
    if isinstance(payload, dict):
        return payload
    return {}


def _normalize_prompt_category(value: str | None) -> str:
    category = (value or "unknown").strip().lower()
    return category if category in ALLOWED_PROMPT_CATEGORIES else "unknown"


def _normalize_research_mode(value: str | None) -> str:
    mode = (value or "off").strip().lower()
    return mode if mode in ALLOWED_RESEARCH_MODES else "off"


def _normalize_routing_mode(value: str | None) -> str:
    mode = (value or "smart").strip().lower()
    return mode if mode in ALLOWED_ROUTING_MODES else "legacy"


def create_routing_decision(
    db: Session,
    llm_request_id: UUID,
    routing_metadata: dict[str, Any],
    *,
    prompt_category: str = "unknown",
    research_mode: str = "off",
    features: dict[str, Any] | None = None,
) -> UUID:
    """
    Upsert routing_decisions row for a request.

    Args:
        db: Database session
        llm_request_id: FK to llm_requests.id
        routing_metadata: metadata["routing"] payload from UnifiedResponse
        prompt_category: Prompt category enum value
        research_mode: off|auto|on
        features: Optional PromptAnalyzer-like features payload

    Returns:
        UUID: routing_decisions.id

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    routing_decisions = get_table("routing_decisions")

    trace = _safe_json_dict(routing_metadata)
    decision_reasons_raw = trace.get("decision_reasons", [])
    if isinstance(decision_reasons_raw, list):
        decision_reasons = [str(reason) for reason in decision_reasons_raw]
    else:
        decision_reasons = []

    attempts_raw = trace.get("attempts", [])
    attempt_count = trace.get("attempt_count")
    if attempt_count is None:
        attempt_count = len(attempts_raw) if isinstance(attempts_raw, list) else 1
    try:
        attempt_count = max(int(attempt_count), 1)
    except Exception:
        attempt_count = 1

    payload = {
        "llm_request_id": llm_request_id,
        "prompt_category": _normalize_prompt_category(prompt_category),
        "research_mode": _normalize_research_mode(research_mode),
        "routing_mode": _normalize_routing_mode(trace.get("mode")),
        "initial_tier": trace.get("initial_tier"),
        "final_tier": trace.get("final_tier"),
        "attempt_count": attempt_count,
        "fallback_used": bool(trace.get("fallback_used", False)),
        "decision_reasons": decision_reasons,
        "features": _safe_json_dict(features),
        "trace": trace,
    }

    stmt = (
        pg_insert(routing_decisions)
        .values(**payload)
        .on_conflict_do_update(
            index_elements=["llm_request_id"],
            set_={
                "prompt_category": payload["prompt_category"],
                "research_mode": payload["research_mode"],
                "routing_mode": payload["routing_mode"],
                "initial_tier": payload["initial_tier"],
                "final_tier": payload["final_tier"],
                "attempt_count": payload["attempt_count"],
                "fallback_used": payload["fallback_used"],
                "decision_reasons": payload["decision_reasons"],
                "features": payload["features"],
                "trace": payload["trace"],
            },
        )
        .returning(routing_decisions.c.id)
    )

    routing_decision_id = db.execute(stmt).scalar_one()
    logger.debug(
        f"Upserted routing_decision: {routing_decision_id} for llm_request_id: {llm_request_id}"
    )
    return routing_decision_id


def create_routing_attempts(
    db: Session,
    routing_decision_id: UUID,
    attempts: list[dict[str, Any]] | None,
) -> int:
    """
    Upsert routing_attempts rows from routing metadata.

    Args:
        db: Database session
        routing_decision_id: FK to routing_decisions.id
        attempts: Attempt payload list from selected_sequence/attempts

    Returns:
        int: Number of attempt rows processed

    Note:
        Does NOT commit. Caller must commit.
    """
    from db.tables import get_table

    if not attempts:
        return 0

    routing_attempts = get_table("routing_attempts")
    processed = 0

    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict):
            continue

        raw_attempt_number = attempt.get("attempt_number", index)
        try:
            attempt_number = int(raw_attempt_number)
        except Exception:
            attempt_number = index
        attempt_number = max(attempt_number, 1)

        validation = str(attempt.get("validation", "") or "").strip().lower()
        if not validation:
            status = str(attempt.get("status", "") or "").strip().lower()
            validation = "ok" if status == "success" else "unknown"

        error_message = attempt.get("error_message") or attempt.get("why_failed")
        if error_message is not None:
            error_message = str(error_message)
            if len(error_message) > 4000:
                error_message = error_message[:4000]

        error_type = attempt.get("error_type")
        if not error_type and validation != "ok":
            error_type = validation
        if error_type is not None:
            error_type = str(error_type)

        latency = attempt.get("latency_ms")
        if latency is not None:
            try:
                latency = int(latency)
            except Exception:
                latency = None

        payload = {
            "routing_decision_id": routing_decision_id,
            "attempt_number": attempt_number,
            "tier": attempt.get("tier"),
            "provider": attempt.get("provider"),
            "model": attempt.get("model"),
            "validation": validation,
            "latency_ms": latency,
            "error_type": error_type,
            "error_message": error_message,
        }

        stmt = pg_insert(routing_attempts).values(**payload).on_conflict_do_update(
            index_elements=["routing_decision_id", "attempt_number"],
            set_={
                "tier": payload["tier"],
                "provider": payload["provider"],
                "model": payload["model"],
                "validation": payload["validation"],
                "latency_ms": payload["latency_ms"],
                "error_type": payload["error_type"],
                "error_message": payload["error_message"],
            },
        )

        db.execute(stmt)
        processed += 1

    logger.debug(
        f"Upserted {processed} routing_attempts for routing_decision_id: {routing_decision_id}"
    )
    return processed


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
