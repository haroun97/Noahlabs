"""Engine, session factory, and a short-lived session context manager.

Design notes:
- A single module-level :class:`~sqlalchemy.engine.Engine` with a ``QueuePool``.
- ``pool_pre_ping=True`` drops dead connections (handles transient DB restarts).
- Sessions are short-lived: one per operation, context-managed. We never hold a
  session (or row lock) open across the long task-processing phase.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from taskpool.config import Settings, get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_app_engine(settings: Settings | None = None) -> Engine:
    """Create a new Engine from settings (mainly for tests / migrations)."""
    settings = settings or get_settings()
    return create_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_timeout=settings.db_pool_timeout_seconds,
        future=True,
    )


def get_engine() -> Engine:
    """Return the lazily-initialised process-wide engine."""
    global _engine
    if _engine is None:
        _engine = create_app_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the lazily-initialised session factory bound to the engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            future=True,
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on success, rolls back on exception, and always closes the session.
    Each call should wrap exactly one short logical unit of work.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_state() -> None:
    """Dispose the engine and clear cached factory (used by tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
