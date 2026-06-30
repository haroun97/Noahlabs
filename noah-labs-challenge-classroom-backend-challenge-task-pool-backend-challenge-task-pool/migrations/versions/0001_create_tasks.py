"""create tasks table, enums, indexes and constraints

Revision ID: 0001_create_tasks
Revises:
Create Date: 2026-06-25

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_tasks"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TASK_STATUS = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    "abandoned",
    name="task_status",
    create_type=False,  # created explicitly below; avoid duplicate on create_table
)
TASK_TOPIC = postgresql.ENUM(
    "predict_voice",
    "raise_voice_alert",
    name="task_topic",
    create_type=False,
)


def upgrade() -> None:
    # pgcrypto provides gen_random_uuid().
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    bind = op.get_bind()
    TASK_STATUS.create(bind, checkfirst=True)
    TASK_TOPIC.create(bind, checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("topic", TASK_TOPIC, nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            TASK_STATUS,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_type", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("error_details", postgresql.JSONB(), nullable=True),
        sa.Column("processing_duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "processing_duration_ms IS NULL OR processing_duration_ms >= 0",
            name="ck_tasks_duration_non_negative",
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL",
            name="ck_tasks_completed_has_timestamp",
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR failed_at IS NOT NULL",
            name="ck_tasks_failed_has_timestamp",
        ),
        sa.CheckConstraint(
            "status <> 'processing' OR (claimed_at IS NOT NULL AND worker_id IS NOT NULL)",
            name="ck_tasks_processing_has_claim",
        ),
    )

    # Small, hot partial index used by the claim query.
    op.create_index(
        "ix_tasks_pending",
        "tasks",
        ["topic", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index(
        "uq_tasks_idempotency_key",
        "tasks",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tasks_idempotency_key", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_pending", table_name="tasks")
    op.drop_table("tasks")

    bind = op.get_bind()
    TASK_TOPIC.drop(bind, checkfirst=True)
    TASK_STATUS.drop(bind, checkfirst=True)
    # Extension is left in place intentionally; it may be shared.
