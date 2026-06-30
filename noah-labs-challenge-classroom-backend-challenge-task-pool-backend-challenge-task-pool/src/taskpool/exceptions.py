"""Typed exception hierarchy for the task pool.

These exceptions form the public error contract of the service layer. Callers
(CLIs, tests) can catch the specific subclass they care about.
"""

from __future__ import annotations

from uuid import UUID


class TaskPoolError(Exception):
    """Base class for all task-pool errors."""


class UnknownTopicError(TaskPoolError):
    """Raised when a topic has no registered payload model / handler."""

    def __init__(self, topic: str) -> None:
        self.topic = topic
        super().__init__(f"Unknown topic: {topic!r}")


class PayloadValidationError(TaskPoolError):
    """Raised when a payload fails Pydantic validation before insertion."""


class PayloadTooLargeError(TaskPoolError):
    """Raised when a serialized payload exceeds the configured size bound."""

    def __init__(self, size: int, limit: int) -> None:
        self.size = size
        self.limit = limit
        super().__init__(f"Payload of {size} bytes exceeds limit of {limit} bytes")


class DuplicateIdempotencyKeyError(TaskPoolError):
    """Raised when an idempotency key collides and the existing row differs."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"Duplicate idempotency_key: {idempotency_key!r}")


class TaskNotFoundError(TaskPoolError):
    """Raised when a task id does not exist."""

    def __init__(self, task_id: UUID) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


class InvalidStateTransitionError(TaskPoolError):
    """Raised when a status transition is not allowed (e.g. complete a non-processing task)."""

    def __init__(self, task_id: UUID, message: str) -> None:
        self.task_id = task_id
        super().__init__(f"Invalid state transition for task {task_id}: {message}")
