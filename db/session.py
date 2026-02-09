"""
SQLAlchemy session management for CortexAI.
Provides get_db() dependency for FastAPI and session factory for CLI.

CRITICAL: Session factory must NOT call get_engine() at import time.
Engine binding happens lazily when first session is created.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from db.engine import get_engine


def _create_session_factory() -> sessionmaker:
    """
    Create session factory with lazy engine binding.

    Returns:
        sessionmaker: Session factory

    Note:
        Engine is NOT created here - it's created when first session is made.
    """
    # Do NOT call get_engine() here - that would bind at import time
    # Instead, create factory that will bind lazily
    return sessionmaker(
        autocommit=False,
        autoflush=False,
    )


# Session factory (unbound at import time)
_SessionFactory = _create_session_factory()


def SessionLocal() -> Session:
    """
    Lazy session factory that binds engine on first use.

    Returns:
        Session: SQLAlchemy session

    Usage:
        session = SessionLocal()
        try:
            # Use session
        finally:
            session.close()
    """
    # Bind engine NOW (lazy - only when session is created)
    _SessionFactory.configure(bind=get_engine())
    return _SessionFactory()


def get_db() -> Generator[Session, None, None]:
    """
    Get a database session (FastAPI dependency or CLI usage).

    Yields:
        Session: SQLAlchemy session

    Usage:
        FastAPI:
            @router.post("/v1/chat")
            def chat(db: Session = Depends(get_db)):
                ...

        CLI:
            db = next(get_db())
            try:
                # Use db
                db.commit()
            finally:
                db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
