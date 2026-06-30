"""SQLAlchemy ORM mapping for the single ``tasks`` table.

This module is intentionally thin: it describes the table and its constraints
and nothing else. No business policy, no logging, no validation lives here.
Schema creation is owned by Alembic migrations, never by ``create_all`` at app
startup.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from taskpool.domain.topics import TaskStatus, Topic

TASK_STATUS_ENUM = ENUM(
    TaskStatus,
    name="task_status",
    create_type=False,
    values_callable=lambda enum: [member.value for member in enum],
)
TASK_TOPIC_ENUM = ENUM(
    Topic,
    name="task_topic",
    create_type=False,
    values_callable=lambda enum: [member.value for member in enum],
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TaskRow(Base):
    """Row mapping for a single task in the pool."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    topic: Mapped[Topic] = mapped_column(TASK_TOPIC_ENUM, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        TASK_STATUS_ENUM,
        nullable=False,
        server_default=text("'pending'"),
    )

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    error_details: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index(
            "ix_tasks_pending",
            "topic",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_tasks_status", "status"),
        Index(
            "uq_tasks_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        CheckConstraint(
            "processing_duration_ms IS NULL OR processing_duration_ms >= 0",
            name="ck_tasks_duration_non_negative",
        ),
        CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL",
            name="ck_tasks_completed_has_timestamp",
        ),
        CheckConstraint(
            "status <> 'failed' OR failed_at IS NOT NULL",
            name="ck_tasks_failed_has_timestamp",
        ),
        CheckConstraint(
            "status <> 'processing' OR (claimed_at IS NOT NULL AND worker_id IS NOT NULL)",
            name="ck_tasks_processing_has_claim",
        ),
    )
