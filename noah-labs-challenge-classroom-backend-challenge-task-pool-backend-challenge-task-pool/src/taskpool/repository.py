"""Data-access layer: all SQL for the task pool.

The repository owns *how* we talk to the database (the claim query, guarded
updates, lookups). It does not own *policy* (validation, idempotency decisions,
logging of payloads) — that belongs to the service layer. Every method operates
on a caller-provided :class:`~sqlalchemy.orm.Session`; the caller controls the
transaction boundary (commit/rollback).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from taskpool.domain.topics import TaskStatus, Topic
from taskpool.persistence.models import TaskRow


class TaskRepository:
    """Thin, fully-typed wrapper around the ``tasks`` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- writes -------------------------------------------------------------

    def insert(
        self,
        *,
        topic: Topic,
        payload: dict[str, object],
        idempotency_key: str | None,
    ) -> TaskRow:
        """Insert a new ``pending`` task and flush to obtain server defaults."""
        row = TaskRow(
            topic=topic,
            payload=payload,
            status=TaskStatus.PENDING,
            idempotency_key=idempotency_key,
        )
        self._session.add(row)
        self._session.flush()
        self._session.refresh(row)
        return row

    def claim_one(self, *, topics: Sequence[Topic], worker_id: str) -> TaskRow | None:
        """Atomically claim a single pending task.

        "Claim" means: this worker takes ownership of one job from the queue.
        The row moves from ``pending`` to ``processing`` so no other worker
        can pick the same job. All of this happens in one database transaction.
        """
        # Step 1: Find one job that is still waiting (pending) and lock it.
        #   - FOR UPDATE = "I am reserving this row; others must wait or skip it"
        #   - SKIP LOCKED = if another worker already locked a row, skip it and
        #     try the next one (so workers grab different jobs, not the same one)
        candidate = (
            select(TaskRow.id)
            .where(TaskRow.status == TaskStatus.PENDING)  # only unclaimed jobs
            .where(TaskRow.topic.in_(list(topics)))  # only topics this worker handles
            .order_by(TaskRow.created_at)  # oldest first (best effort, not strict FIFO)
            .with_for_update(skip_locked=True)
            .limit(1)  # one job per claim
            .scalar_subquery()
        )
        # Step 2: In the SAME transaction, mark that row as "mine" (processing).
        #   Commit happens right after this in the service layer — before any
        #   slow work (sleep, API calls). The lock is not held during processing.
        stmt = (
            update(TaskRow)
            .where(TaskRow.id == candidate)
            .values(
                status=TaskStatus.PROCESSING,
                worker_id=worker_id,
                claimed_at=func.now(),
                updated_at=func.now(),
            )
            .returning(TaskRow)
            .execution_options(synchronize_session=False)
        )
        return self._session.execute(stmt).scalars().one_or_none()

    def mark_completed(self, *, task_id: UUID, duration_ms: int | None) -> TaskRow | None:
        """Transition ``processing -> completed`` (guarded). None if not applied."""
        stmt = (
            update(TaskRow)
            .where(TaskRow.id == task_id)
            .where(TaskRow.status == TaskStatus.PROCESSING)
            .values(
                status=TaskStatus.COMPLETED,
                completed_at=func.now(),
                updated_at=func.now(),
                processing_duration_ms=duration_ms,
            )
            .returning(TaskRow)
            .execution_options(synchronize_session=False)
        )
        return self._session.execute(stmt).scalars().one_or_none()

    def mark_failed(
        self,
        *,
        task_id: UUID,
        error_type: str,
        error_message: str,
        error_details: dict[str, object] | None,
        duration_ms: int | None,
    ) -> TaskRow | None:
        """Transition ``processing -> failed`` (guarded). None if not applied.

        Failed is final: this job will never be claimed again automatically.
        Operators can inspect it (admin CLI) or manually enqueue a new job.
        """
        stmt = (
            update(TaskRow)
            .where(TaskRow.id == task_id)
            .where(TaskRow.status == TaskStatus.PROCESSING)  # only from processing
            .values(
                status=TaskStatus.FAILED,
                failed_at=func.now(),
                updated_at=func.now(),
                error_type=error_type,
                error_message=error_message,
                error_details=error_details,
                processing_duration_ms=duration_ms,
            )
            .returning(TaskRow)
            .execution_options(synchronize_session=False)
        )
        return self._session.execute(stmt).scalars().one_or_none()

    def mark_abandoned(self, *, task_id: UUID) -> TaskRow | None:
        """Transition ``processing -> abandoned`` (operational). None if not applied."""
        stmt = (
            update(TaskRow)
            .where(TaskRow.id == task_id)
            .where(TaskRow.status == TaskStatus.PROCESSING)
            .values(status=TaskStatus.ABANDONED, updated_at=func.now())
            .returning(TaskRow)
            .execution_options(synchronize_session=False)
        )
        return self._session.execute(stmt).scalars().one_or_none()

    # --- reads --------------------------------------------------------------

    def get_by_id(self, task_id: UUID) -> TaskRow | None:
        """Return a task by id, or None."""
        return self._session.get(TaskRow, task_id)

    def find_by_idempotency_key(self, idempotency_key: str) -> TaskRow | None:
        """Return an existing task with this idempotency key, or None."""
        stmt = select(TaskRow).where(TaskRow.idempotency_key == idempotency_key)
        return self._session.execute(stmt).scalars().one_or_none()

    def list_stale_processing(self, *, older_than: timedelta) -> list[TaskRow]:
        """Return ``processing`` tasks claimed before ``now - older_than``."""
        cutoff = datetime.now(tz=UTC) - older_than
        stmt = (
            select(TaskRow)
            .where(TaskRow.status == TaskStatus.PROCESSING)
            .where(TaskRow.claimed_at < cutoff)
            .order_by(TaskRow.claimed_at)
        )
        return list(self._session.execute(stmt).scalars().all())

    def counts_by_status(self) -> dict[TaskStatus, int]:
        """Return a count of tasks grouped by status (zero-filled)."""
        stmt = select(TaskRow.status, func.count()).group_by(TaskRow.status)
        counts: dict[TaskStatus, int] = dict.fromkeys(TaskStatus, 0)
        for status, count in self._session.execute(stmt).all():
            counts[status] = count
        return counts
