"""Producer CLI: generate realistic sample tasks via the public ``add_task``.

Usage:
    python -m taskpool.cli.producer --topic all --count 50 [--seed 42]
"""

from __future__ import annotations

import argparse
import random
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from taskpool.domain.topics import Topic
from taskpool.logging import get_logger
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload
from taskpool.service import add_task

logger = get_logger("taskpool.producer")


def _make_predict_voice(rng: random.Random) -> PredictVoicePayload:
    user_id = UUID(int=rng.getrandbits(128))
    return PredictVoicePayload(
        user_id=user_id,
        audio_s3_url=f"s3://voice-recordings/{user_id}/sample.wav",
    )


def _make_raise_voice_alert(rng: random.Random) -> RaiseVoiceAlertPayload:
    user_id = UUID(int=rng.getrandbits(128))
    measured_at = datetime.now(tz=UTC) - timedelta(seconds=rng.randint(0, 3600))
    return RaiseVoiceAlertPayload(
        user_id=user_id,
        measured_at=measured_at,
        audio_quality=round(rng.uniform(0.0, 1.0), 4),
        voice_score=round(rng.uniform(0.0, 1.0), 4),
    )


def _topics_for(selection: str) -> list[Topic]:
    if selection == "all":
        return list(Topic)
    return [Topic(selection)]


def produce(
    *,
    topics: Sequence[Topic],
    count: int,
    rng: random.Random,
    idempotency_prefix: str | None,
) -> int:
    """Create ``count`` tasks spread across ``topics``. Returns number created."""
    created = 0
    for index in range(count):
        topic = topics[index % len(topics)]
        key = f"{idempotency_prefix}-{index}" if idempotency_prefix else None
        if topic is Topic.PREDICT_VOICE:
            task_id = add_task(
                Topic.PREDICT_VOICE,
                _make_predict_voice(rng),
                idempotency_key=key,
            ).id
        elif topic is Topic.RAISE_VOICE_ALERT:
            task_id = add_task(
                Topic.RAISE_VOICE_ALERT,
                _make_raise_voice_alert(rng),
                idempotency_key=key,
            ).id
        else:  # pragma: no cover - defensive, unreachable with current enum
            raise ValueError(f"Unsupported topic: {topic}")
        created += 1
        logger.info("task_created", extra={"task_id": str(task_id), "topic": topic.value})
    return created


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Produce sample tasks into the pool.")
    parser.add_argument(
        "--topic",
        choices=[*[t.value for t in Topic], "all"],
        default="all",
        help="Topic to produce (or 'all' to round-robin both).",
    )
    parser.add_argument("--count", type=int, default=10, help="Number of tasks to create.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for deterministic test data.",
    )
    parser.add_argument(
        "--idempotency-prefix",
        type=str,
        default=None,
        help="If set, each task gets idempotency_key '<prefix>-<index>'.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.count <= 0:
        logger.error("invalid_count", extra={"count": args.count})
        return 2
    rng = random.Random(args.seed)
    topics = _topics_for(args.topic)
    try:
        created = produce(
            topics=topics,
            count=args.count,
            rng=rng,
            idempotency_prefix=args.idempotency_prefix,
        )
    except Exception:
        logger.exception("producer_failed")
        return 1
    logger.info("producer_done", extra={"tasks_created": created})
    return 0


if __name__ == "__main__":
    sys.exit(main())
