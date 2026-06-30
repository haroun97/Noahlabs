"""Public, fully-typed task-pool API.

This is the layer producers/consumers import. It owns:
- payload validation & safe JSONB serialization,
- idempotency policy,
- transaction boundaries (one short session per operation),
- mapping ORM rows into typed :class:`Task` domain objects,
- state-transition guards (complete/fail only from ``processing``).

It must not perform topic *processing* — that is the handlers' job.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Literal, NoReturn, cast, overload
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from taskpool.config import get_settings
from taskpool.db import session_scope
from taskpool.domain.task import Task
from taskpool.domain.topics import TaskStatus, Topic
from taskpool.exceptions import (
    DuplicateIdempotencyKeyError,
    InvalidStateTransitionError,
    PayloadTooLargeError,
    PayloadValidationError,
    TaskNotFoundError,
)
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload
from taskpool.payloads.registry import AnyPayload, parse_payload, payload_model_for
from taskpool.persistence.models import TaskRow
from taskpool.repository import TaskRepository

ClaimedTask = Task[PredictVoicePayload] | Task[RaiseVoiceAlertPayload]
"""A claimed task whose payload is one of the known concrete types."""


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _row_to_task(row: TaskRow) -> Task[AnyPayload]:
    """Map a persisted row to a typed domain task (payload re-validated)."""
    payload = parse_payload(row.topic, row.payload)
    return Task[AnyPayload](
        id=row.id,
        topic=row.topic,
        payload=cast(AnyPayload, payload),
        status=row.status,
        idempotency_key=row.idempotency_key,
        worker_id=row.worker_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        claimed_at=row.claimed_at,
        completed_at=row.completed_at,
        failed_at=row.failed_at,
        error_type=row.error_type,
        error_message=row.error_message,
        error_details=row.error_details,
        processing_duration_ms=row.processing_duration_ms,
    )


def _serialize_payload(topic: Topic, payload: AnyPayload) -> dict[str, Any]:
    """Validate payload<->topic match, then JSON-serialize within size bounds."""
    expected = payload_model_for(topic)
    if not isinstance(payload, expected):
        raise PayloadValidationError(
            f"Payload type {type(payload).__name__} does not match topic "
            f"{topic.value!r} (expected {expected.__name__})"
        )
    data = payload.model_dump(mode="json")
    size = len(json.dumps(data).encode("utf-8"))
    limit = get_settings().max_payload_bytes
    if size > limit:
        raise PayloadTooLargeError(size, limit)
    return data


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "\u2026"


# ---------------------------------------------------------------------------
# add_task
# ---------------------------------------------------------------------------


@overload
def add_task(
    topic: Literal[Topic.PREDICT_VOICE],
    payload: PredictVoicePayload,
    *,
    idempotency_key: str | None = ...,
) -> Task[PredictVoicePayload]: ...


@overload
def add_task(
    topic: Literal[Topic.RAISE_VOICE_ALERT],
    payload: RaiseVoiceAlertPayload,
    *,
    idempotency_key: str | None = ...,
) -> Task[RaiseVoiceAlertPayload]: ...


def add_task(
    topic: Topic,
    payload: AnyPayload,
    *,
    idempotency_key: str | None = None,
) -> Task[Any]:
    """Validate, serialize, and insert a new ``pending`` task.

    Idempotency: if ``idempotency_key`` is supplied and a task already exists
    with that key, the existing task is returned (no duplicate insert). A
    concurrent race that trips the unique constraint is resolved the same way.
    """
    data = _serialize_payload(topic, payload)

    if idempotency_key is not None:
        existing = _find_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

    try:
        with session_scope() as session:
            repo = TaskRepository(session)
            row = repo.insert(topic=topic, payload=data, idempotency_key=idempotency_key)
            return _row_to_task(row)
    except IntegrityError as exc:
        if idempotency_key is not None:
            existing = _find_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing
            raise DuplicateIdempotencyKeyError(idempotency_key) from exc
        raise


def _find_by_idempotency_key(idempotency_key: str) -> Task[Any] | None:
    with session_scope() as session:
        repo = TaskRepository(session)
        row = repo.find_by_idempotency_key(idempotency_key)
        return _row_to_task(row) if row is not None else None


# ---------------------------------------------------------------------------
# get_task (claim)
# ---------------------------------------------------------------------------


def get_task(topics: Sequence[Topic], worker_id: str) -> ClaimedTask | None:
    """Atomically claim one pending task in ``topics`` for ``worker_id``.

    Commits the ``pending -> processing`` transition immediately (before any
    processing), so no row lock is held during the long handler phase. Returns
    a typed task, or ``None`` when nothing is available.
    """
    if not topics:
        raise ValueError("get_task requires at least one topic")
    with session_scope() as session:
        repo = TaskRepository(session)
        row = repo.claim_one(topics=topics, worker_id=worker_id)
        if row is None:
            return None
        return cast(ClaimedTask, _row_to_task(row))


# ---------------------------------------------------------------------------
# terminal transitions
# ---------------------------------------------------------------------------


def mark_task_completed(task_id: UUID, *, duration_ms: int | None = None) -> Task[Any]:
    """Transition a task ``processing -> completed`` (guarded)."""
    with session_scope() as session:
        repo = TaskRepository(session)
        row = repo.mark_completed(task_id=task_id, duration_ms=duration_ms)
        if row is None:
            _raise_transition_error(repo, task_id, target="completed")
        return _row_to_task(row)


def mark_task_failed(
    task_id: UUID,
    *,
    error_type: str,
    error_message: str,
    error_details: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> Task[Any]:
    """Transition a task ``processing -> failed`` (guarded), bounding error info."""
    settings = get_settings()
    with session_scope() as session:
        repo = TaskRepository(session)
        row = repo.mark_failed(
            task_id=task_id,
            error_type=_truncate(error_type, settings.max_error_type_chars),
            error_message=_truncate(error_message, settings.max_error_message_chars),
            error_details=error_details,
            duration_ms=duration_ms,
        )
        if row is None:
            _raise_transition_error(repo, task_id, target="failed")
        return _row_to_task(row)


def _raise_transition_error(repo: TaskRepository, task_id: UUID, *, target: str) -> NoReturn:
    existing = repo.get_by_id(task_id)
    if existing is None:
        raise TaskNotFoundError(task_id)
    raise InvalidStateTransitionError(
        task_id,
        f"cannot mark {target}: current status is {existing.status.value!r}, "
        f"expected {TaskStatus.PROCESSING.value!r}",
    )


# ---------------------------------------------------------------------------
# inspection / admin  [Hardening]
# ---------------------------------------------------------------------------


def get_task_by_id(task_id: UUID) -> Task[Any] | None:
    """Return any task by id (for operational debugging)."""
    with session_scope() as session:
        repo = TaskRepository(session)
        row = repo.get_by_id(task_id)
        return _row_to_task(row) if row is not None else None


def list_stale_processing(older_than: timedelta) -> list[Task[Any]]:
    """Return tasks stuck in ``processing`` longer than ``older_than``."""
    with session_scope() as session:
        repo = TaskRepository(session)
        return [_row_to_task(row) for row in repo.list_stale_processing(older_than=older_than)]


def mark_abandoned(task_id: UUID) -> Task[Any]:
    """Operationally mark a stale ``processing`` task as ``abandoned``.

    Never auto-requeues (respects the "no reprocessing" rule).
    """
    with session_scope() as session:
        repo = TaskRepository(session)
        row = repo.mark_abandoned(task_id=task_id)
        if row is None:
            _raise_transition_error(repo, task_id, target="abandoned")
        return _row_to_task(row)


def counts_by_status() -> dict[TaskStatus, int]:
    """Return a count of tasks grouped by status."""
    with session_scope() as session:
        repo = TaskRepository(session)
        return repo.counts_by_status()
