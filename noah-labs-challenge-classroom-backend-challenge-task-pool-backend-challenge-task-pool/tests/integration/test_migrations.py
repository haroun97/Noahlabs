"""Alembic migration lifecycle tests (upgrade head / downgrade base)."""

from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from taskpool import config, db

pytestmark = pytest.mark.integration


def _alembic_config() -> Config:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    cfg = Config(os.path.join(project_root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(project_root, "migrations"))
    return cfg


def test_migrations_upgrade_and_downgrade(db_engine: Engine) -> None:
    """``downgrade base`` drops ``tasks``; ``upgrade head`` restores the schema."""
    cfg = _alembic_config()
    inspector = inspect(db_engine)

    # Session fixture already ran ``upgrade head``.
    assert inspector.has_table("tasks")

    config.get_settings.cache_clear()
    db.reset_engine_state()

    command.downgrade(cfg, "base")
    inspector = inspect(db_engine)
    assert not inspector.has_table("tasks")

    command.upgrade(cfg, "head")
    inspector = inspect(db_engine)
    assert inspector.has_table("tasks")

    columns = {col["name"] for col in inspector.get_columns("tasks")}
    assert {"id", "topic", "payload", "status"}.issubset(columns)

    # Restore empty table for any later tests in this session.
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE tasks"))
