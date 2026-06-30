"""End-to-end test driving the real producer and consumer entry points."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from taskpool.cli import consumer as consumer_cli
from taskpool.cli import producer as producer_cli
from taskpool.domain.topics import ALL_TOPICS, TaskStatus, Topic
from taskpool.handlers.base import ClaimedTask, HandlerResult
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.service import add_task, counts_by_status, get_task

pytestmark = pytest.mark.e2e


def _completed_counts_by_topic(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT topic::text, count(*)::int "
                "FROM tasks WHERE status = 'completed' GROUP BY topic"
            )
        ).all()
    return {str(topic): int(count) for topic, count in rows}


def test_producer_then_consumer(clean_db: Engine) -> None:
    # Produce a deterministic batch across both topics.
    rc = producer_cli.main(["--topic", "all", "--count", "10", "--seed", "7"])
    assert rc == 0
    assert counts_by_status()[TaskStatus.PENDING] == 10

    # Consume exactly those tasks with a single worker, then exit.
    consumer = consumer_cli.Consumer(
        topics=ALL_TOPICS,
        worker_id="e2e-worker",
        max_tasks=10,
    )
    processed = consumer.run()
    assert processed == 10

    counts = counts_by_status()
    assert counts[TaskStatus.PENDING] == 0
    assert counts[TaskStatus.PROCESSING] == 0
    assert counts[TaskStatus.COMPLETED] == 10
    assert _completed_counts_by_topic(clean_db) == {
        "predict_voice": 5,
        "raise_voice_alert": 5,
    }


def test_consumer_marks_failed_continues_and_does_not_reclaim(
    clean_db: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://b/k.wav")
    for _ in range(2):
        add_task(Topic.PREDICT_VOICE, payload)

    calls = 0

    def flaky_dispatch(task: ClaimedTask) -> HandlerResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated failure")
        return {"ok": True}

    monkeypatch.setattr("taskpool.cli.consumer.dispatch", flaky_dispatch)

    consumer = consumer_cli.Consumer(
        topics=ALL_TOPICS,
        worker_id="e2e-fail",
        max_tasks=2,
    )
    assert consumer.run() == 2

    counts = counts_by_status()
    assert counts[TaskStatus.FAILED] == 1
    assert counts[TaskStatus.COMPLETED] == 1
    assert counts[TaskStatus.PENDING] == 0
    assert get_task([Topic.PREDICT_VOICE], "other-worker") is None
