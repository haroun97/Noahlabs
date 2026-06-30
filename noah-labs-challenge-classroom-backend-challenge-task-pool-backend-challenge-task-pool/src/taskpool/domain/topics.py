"""Topic and status enumerations.

These are pure value types shared by every layer. They must not import
SQLAlchemy, Pydantic payloads, or anything persistence-related.
"""

from __future__ import annotations

from enum import StrEnum


class Topic(StrEnum):
    """Supported task topics.

    Adding a topic here is a deliberate, typed change: it forces a payload model
    (``TOPIC_PAYLOADS``), a handler, and a database migration (the DB uses a
    native enum).
    """

    PREDICT_VOICE = "predict_voice"
    RAISE_VOICE_ALERT = "raise_voice_alert"


class TaskStatus(StrEnum):
    """Lifecycle states of a task.

    ``pending -> processing -> completed | failed``; ``processing -> abandoned``
    is an operational (admin) transition only and is never auto-applied.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"

    @property
    def is_terminal(self) -> bool:
        """True for states that can never transition further."""
        return self in _TERMINAL_STATUSES


_TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABANDONED}
)

ALL_TOPICS: tuple[Topic, ...] = tuple(Topic)
