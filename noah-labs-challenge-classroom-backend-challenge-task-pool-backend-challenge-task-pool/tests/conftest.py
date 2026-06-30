"""Shared pytest fixtures.

Integration/concurrency/e2e tests require a *real* PostgreSQL (SQLite has
different locking semantics and would invalidate the claim tests). They connect
using ``TASKPOOL_TEST_DATABASE_URL`` (or a sensible local default) and skip
gracefully if no database is reachable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

DEFAULT_TEST_DSN = "postgresql+psycopg://taskpool:taskpool@localhost:5433/taskpool"


def _test_dsn() -> str:
    return os.environ.get("TASKPOOL_TEST_DATABASE_URL", DEFAULT_TEST_DSN)


def _configure_environment() -> None:
    """Point the application at the test database and reset cached state."""
    os.environ["DATABASE_URL"] = _test_dsn()
    # Keep things deterministic/fast for tests.
    os.environ.setdefault("LOG_FORMAT", "console")
    os.environ.setdefault("POLL_INTERVAL_SECONDS", "0.05")
    os.environ.setdefault("POLL_JITTER_SECONDS", "0")

    from taskpool import config, db

    config.get_settings.cache_clear()
    db.reset_engine_state()


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Session-scoped engine against a migrated test database.

    Skips the whole integration suite if PostgreSQL is unreachable.
    """
    _configure_environment()

    from alembic import command
    from alembic.config import Config

    from taskpool.db import create_app_engine

    engine = create_app_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover - environment dependent
        engine.dispose()
        pytest.skip(f"PostgreSQL not reachable at {_test_dsn()}: {exc}")

    project_root = os.path.dirname(os.path.dirname(__file__))
    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(project_root, "migrations"))
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(db_engine: Engine) -> Iterator[Engine]:
    """Truncate the tasks table before each test for isolation."""
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE tasks"))
    # Ensure the app uses a fresh engine bound to the test DSN.
    from taskpool import db as db_module

    db_module.reset_engine_state()
    yield db_engine
