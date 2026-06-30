"""Admin/inspection CLI for operational debugging.

Subcommands:
    counts                       show task counts by status
    get <task_id>                show a single task (no full payload by default)
    stale [--seconds N]          list processing tasks older than threshold
    reap  [--seconds N]          mark stale processing tasks as abandoned
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

from taskpool.config import get_settings
from taskpool.logging import get_logger
from taskpool.service import (
    counts_by_status,
    get_task_by_id,
    list_stale_processing,
    mark_abandoned,
)

logger = get_logger("taskpool.admin")


def _cmd_counts() -> int:
    counts = counts_by_status()
    print(json.dumps({status.value: count for status, count in counts.items()}, indent=2))
    return 0


def _cmd_get(task_id: UUID) -> int:
    task = get_task_by_id(task_id)
    if task is None:
        print(f"Task not found: {task_id}", file=sys.stderr)
        return 1
    summary = {
        "id": str(task.id),
        "topic": task.topic.value,
        "status": task.status.value,
        "worker_id": task.worker_id,
        "created_at": task.created_at.isoformat(),
        "claimed_at": task.claimed_at.isoformat() if task.claimed_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "failed_at": task.failed_at.isoformat() if task.failed_at else None,
        "error_type": task.error_type,
        "error_message": task.error_message,
        "processing_duration_ms": task.processing_duration_ms,
    }
    print(json.dumps(summary, indent=2))
    return 0


def _cmd_stale(seconds: int) -> int:
    tasks = list_stale_processing(timedelta(seconds=seconds))
    for task in tasks:
        print(
            json.dumps(
                {
                    "id": str(task.id),
                    "topic": task.topic.value,
                    "worker_id": task.worker_id,
                    "claimed_at": task.claimed_at.isoformat() if task.claimed_at else None,
                }
            )
        )
    logger.info("stale_listed", extra={"count": len(tasks), "threshold_s": seconds})
    return 0


def _cmd_reap(seconds: int) -> int:
    tasks = list_stale_processing(timedelta(seconds=seconds))
    reaped = 0
    for task in tasks:
        try:
            mark_abandoned(task.id)
            reaped += 1
        except Exception:
            logger.exception("reap_failed", extra={"task_id": str(task.id)})
    logger.info("reap_done", extra={"reaped": reaped, "threshold_s": seconds})
    print(json.dumps({"reaped": reaped}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Task pool admin/inspection tools.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("counts", help="Show task counts by status.")

    get_p = sub.add_parser("get", help="Show a single task by id.")
    get_p.add_argument("task_id", type=UUID)

    default_threshold = get_settings().abandoned_threshold_seconds
    stale_p = sub.add_parser("stale", help="List stale processing tasks.")
    stale_p.add_argument("--seconds", type=int, default=default_threshold)

    reap_p = sub.add_parser("reap", help="Mark stale processing tasks as abandoned.")
    reap_p.add_argument("--seconds", type=int, default=default_threshold)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "counts":
        return _cmd_counts()
    if args.command == "get":
        return _cmd_get(args.task_id)
    if args.command == "stale":
        return _cmd_stale(args.seconds)
    if args.command == "reap":
        return _cmd_reap(args.seconds)
    return 2


if __name__ == "__main__":
    sys.exit(main())
