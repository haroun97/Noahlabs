"""The generic, fully-typed :class:`Task` domain model.

``Task[PayloadT]`` carries its concrete payload type, so a claimed
``predict_voice`` task is a ``Task[PredictVoicePayload]`` and the handler that
receives it sees the right payload type. This model is persistence-agnostic: the
repository maps the SQLAlchemy row into this structure.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from taskpool.domain.topics import TaskStatus, Topic
from taskpool.payloads.base import TaskPayload


class Task[PayloadT: TaskPayload](BaseModel):
    """An immutable snapshot of a task row, with a typed payload."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    topic: Topic
    payload: PayloadT
    status: TaskStatus

    idempotency_key: str | None = None
    worker_id: str | None = None

    created_at: datetime
    updated_at: datetime
    claimed_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None

    error_type: str | None = None
    error_message: str | None = None
    error_details: dict[str, object] | None = None
    processing_duration_ms: int | None = None
