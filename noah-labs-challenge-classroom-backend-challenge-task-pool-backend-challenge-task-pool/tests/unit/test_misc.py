"""Unit tests for small pure helpers (status FSM, truncation, config)."""

from __future__ import annotations

import os

from taskpool.config import Settings
from taskpool.domain.topics import TaskStatus
from taskpool.service import _truncate


def test_terminal_statuses() -> None:
    assert TaskStatus.COMPLETED.is_terminal
    assert TaskStatus.FAILED.is_terminal
    assert TaskStatus.ABANDONED.is_terminal
    assert not TaskStatus.PENDING.is_terminal
    assert not TaskStatus.PROCESSING.is_terminal


def test_truncate_no_change_when_short() -> None:
    assert _truncate("hello", 10) == "hello"


def test_truncate_shortens_and_marks() -> None:
    out = _truncate("x" * 100, 10)
    assert len(out) == 10
    assert out.endswith("\u2026")


def test_configured_topics_parsing() -> None:
    settings = Settings(taskpool_topics="predict_voice, , raise_voice_alert,predict_voice")
    assert settings.configured_topics == ("predict_voice", "raise_voice_alert")


def test_configured_topics_empty_means_all() -> None:
    settings = Settings(taskpool_topics="")
    assert settings.configured_topics == ()


def test_worker_id_unique() -> None:
    from taskpool.observability import generate_worker_id

    assert generate_worker_id() != generate_worker_id()
    assert str(os.getpid()) in generate_worker_id()
