"""Consumer CLI: a long-running worker that claims and processes tasks.

Loop: claim -> dispatch to typed handler -> mark completed/failed -> repeat.
A single task failure never kills the worker. Graceful shutdown on SIGTERM/SIGINT
finishes the in-flight task and stops claiming new ones.

Usage:
    python -m taskpool.cli.consumer [--topics predict_voice,raise_voice_alert]
                                    [--max-tasks N] [--poll-interval S]
"""

from __future__ import annotations

import argparse
import random
import signal
import sys
import time
from collections.abc import Sequence
from types import FrameType

from sqlalchemy.exc import OperationalError

from taskpool.config import get_settings
from taskpool.domain.topics import ALL_TOPICS, Topic
from taskpool.handlers.base import dispatch
from taskpool.logging import get_logger
from taskpool.observability import generate_worker_id
from taskpool.service import get_task, mark_task_completed, mark_task_failed

logger = get_logger("taskpool.consumer")

# When ``--max-tasks`` is set (bounded runs / demo), exit after this many empty
# polls so workers do not wait forever once the queue is drained.
_IDLE_EXIT_POLLS_WHEN_MAX_TASKS = 3


def resolve_topics(cli_topics: str | None) -> tuple[Topic, ...]:
    """Resolve the topic subset from CLI, then env, defaulting to all topics."""
    raw: tuple[str, ...]
    if cli_topics:
        raw = tuple(t.strip() for t in cli_topics.split(",") if t.strip())
    else:
        raw = get_settings().configured_topics
    if not raw:
        return ALL_TOPICS
    return tuple(Topic(value) for value in raw)


class Consumer:
    """Encapsulates worker state and the processing loop."""

    def __init__(
        self,
        *,
        topics: Sequence[Topic],
        worker_id: str | None = None,
        max_tasks: int | None = None,
    ) -> None:
        self.topics = tuple(topics)
        self.worker_id = worker_id or generate_worker_id()
        self.max_tasks = max_tasks
        self._stop = False
        self._processed = 0
        self._idle_polls = 0
        settings = get_settings()
        self._poll_interval = settings.poll_interval_seconds
        self._jitter = settings.poll_jitter_seconds
        self._backoff = settings.db_retry_backoff_seconds
        self._max_backoff = settings.db_retry_max_backoff_seconds
        self._rng = random.Random()

    # --- lifecycle ----------------------------------------------------------

    def request_stop(self, signum: int, _frame: FrameType | None) -> None:
        """Signal handler: request a graceful stop after the current task."""
        logger.info("shutdown_requested", extra={"signal": signum, "worker_id": self.worker_id})
        self._stop = True

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)

    # --- main loop ----------------------------------------------------------

    def run(self) -> int:
        """Run until stop is requested or ``max_tasks`` reached. Returns count."""
        logger.info(
            "consumer_started",
            extra={"worker_id": self.worker_id, "topics": [t.value for t in self.topics]},
        )
        current_backoff = self._backoff
        while not self._stop:
            if self.max_tasks is not None and self._processed >= self.max_tasks:
                break
            try:
                claimed = self._claim_and_process()
                current_backoff = self._backoff  # reset after a healthy cycle
                if claimed:
                    self._idle_polls = 0
                else:
                    self._idle_polls += 1
                    if (
                        self.max_tasks is not None
                        and self._idle_polls >= _IDLE_EXIT_POLLS_WHEN_MAX_TASKS
                    ):
                        logger.info(
                            "consumer_idle_exit",
                            extra={
                                "worker_id": self.worker_id,
                                "processed": self._processed,
                                "idle_polls": self._idle_polls,
                            },
                        )
                        break
                    self._sleep_poll()
            except OperationalError:
                logger.warning(
                    "db_connection_error",
                    extra={"worker_id": self.worker_id, "backoff_s": current_backoff},
                )
                time.sleep(current_backoff)
                current_backoff = min(current_backoff * 2, self._max_backoff)
        logger.info(
            "consumer_stopped",
            extra={"worker_id": self.worker_id, "processed": self._processed},
        )
        return self._processed

    def _claim_and_process(self) -> bool:
        """Claim one task and process it. Returns True if a task was handled."""
        task = get_task(self.topics, self.worker_id)
        if task is None:
            logger.debug("no_task_available", extra={"worker_id": self.worker_id})
            return False

        logger.info(
            "task_claimed",
            extra={
                "task_id": str(task.id),
                "topic": task.topic.value,
                "worker_id": self.worker_id,
            },
        )
        started = time.monotonic()
        try:
            result = dispatch(task)
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            mark_task_failed(
                task.id,
                error_type=type(exc).__name__,
                error_message=str(exc),
                duration_ms=duration_ms,
            )
            logger.warning(
                "task_failed",
                extra={
                    "task_id": str(task.id),
                    "topic": task.topic.value,
                    "worker_id": self.worker_id,
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                },
            )
        else:
            duration_ms = int((time.monotonic() - started) * 1000)
            mark_task_completed(task.id, duration_ms=duration_ms)
            logger.info(
                "task_completed",
                extra={
                    "task_id": str(task.id),
                    "topic": task.topic.value,
                    "worker_id": self.worker_id,
                    "duration_ms": duration_ms,
                    "result": result,
                },
            )
        self._processed += 1
        return True

    def _sleep_poll(self) -> None:
        delay = self._poll_interval + self._rng.uniform(0, self._jitter)
        # Sleep in small slices so shutdown stays responsive.
        deadline = time.monotonic() + delay
        while not self._stop and time.monotonic() < deadline:
            time.sleep(min(0.1, deadline - time.monotonic()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume and process tasks from the pool.")
    parser.add_argument(
        "--topics",
        type=str,
        default=None,
        help="Comma-separated topics to consume (default: TASKPOOL_TOPICS or all).",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Process at most N tasks then exit (useful for tests/e2e).",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Override the auto-generated worker id.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    topics = resolve_topics(args.topics)
    consumer = Consumer(topics=topics, worker_id=args.worker_id, max_tasks=args.max_tasks)
    consumer.install_signal_handlers()
    try:
        consumer.run()
    except Exception:
        logger.exception("consumer_crashed", extra={"worker_id": consumer.worker_id})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
