"""Repository/service integration tests against a real PostgreSQL.

These cover the full public contract: create, claim, complete, fail, exclusion
of terminal tasks, idempotency, and invalid state transitions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from taskpool.domain.topics import TaskStatus, Topic
from taskpool.exceptions import InvalidStateTransitionError, TaskNotFoundError
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload
from taskpool.service import (
    add_task,
    counts_by_status,
    get_task,
    get_task_by_id,
    list_stale_processing,
    mark_abandoned,
    mark_task_completed,
    mark_task_failed,
)

pytestmark = pytest.mark.integration

WORKER = "test-worker-1"


def _predict() -> PredictVoicePayload:
    return PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://bucket/a.wav")


def _alert() -> RaiseVoiceAlertPayload:
    return RaiseVoiceAlertPayload(
        user_id=uuid4(), measured_at=datetime.now(tz=UTC), audio_quality=0.7, voice_score=0.3
    )


def test_add_task_creates_pending(clean_db: Engine) -> None:
    task = add_task(Topic.PREDICT_VOICE, _predict())
    assert task.status is TaskStatus.PENDING
    assert task.worker_id is None
    assert isinstance(task.payload, PredictVoicePayload)


def test_claim_complete_flow(clean_db: Engine) -> None:
    created = add_task(Topic.PREDICT_VOICE, _predict())
    claimed = get_task([Topic.PREDICT_VOICE], WORKER)
    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status is TaskStatus.PROCESSING
    assert claimed.worker_id == WORKER
    assert claimed.claimed_at is not None

    done = mark_task_completed(claimed.id, duration_ms=12)
    assert done.status is TaskStatus.COMPLETED
    assert done.completed_at is not None
    assert done.processing_duration_ms == 12


def test_claim_fail_flow_retains_error(clean_db: Engine) -> None:
    add_task(Topic.RAISE_VOICE_ALERT, _alert())
    claimed = get_task([Topic.RAISE_VOICE_ALERT], WORKER)
    assert claimed is not None
    failed = mark_task_failed(
        claimed.id,
        error_type="ValueError",
        error_message="boom",
        error_details={"k": "v"},
        duration_ms=5,
    )
    assert failed.status is TaskStatus.FAILED
    assert failed.failed_at is not None
    assert failed.error_type == "ValueError"
    assert failed.error_message == "boom"


def test_get_task_returns_none_when_empty(clean_db: Engine) -> None:
    assert get_task([Topic.PREDICT_VOICE], WORKER) is None


def test_completed_task_not_returned(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    claimed = get_task([Topic.PREDICT_VOICE], WORKER)
    assert claimed is not None
    mark_task_completed(claimed.id)
    assert get_task([Topic.PREDICT_VOICE], WORKER) is None


def test_failed_task_not_reprocessed(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    claimed = get_task([Topic.PREDICT_VOICE], WORKER)
    assert claimed is not None
    mark_task_failed(claimed.id, error_type="E", error_message="m")
    assert get_task([Topic.PREDICT_VOICE], WORKER) is None


def test_topic_filtering(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    # A consumer only configured for the other topic gets nothing.
    assert get_task([Topic.RAISE_VOICE_ALERT], WORKER) is None
    # But the matching consumer claims it.
    assert get_task([Topic.PREDICT_VOICE], WORKER) is not None


def test_double_claim_is_impossible(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    first = get_task([Topic.PREDICT_VOICE], "w1")
    second = get_task([Topic.PREDICT_VOICE], "w2")
    assert first is not None
    assert second is None


def test_idempotency_returns_existing(clean_db: Engine) -> None:
    payload = _predict()
    a = add_task(Topic.PREDICT_VOICE, payload, idempotency_key="dup-1")
    b = add_task(Topic.PREDICT_VOICE, _predict(), idempotency_key="dup-1")
    assert a.id == b.id
    counts = counts_by_status()
    assert counts[TaskStatus.PENDING] == 1


def test_complete_requires_processing(clean_db: Engine) -> None:
    created = add_task(Topic.PREDICT_VOICE, _predict())
    # Still pending -> completing must fail with InvalidStateTransition.
    with pytest.raises(InvalidStateTransitionError):
        mark_task_completed(created.id)


def test_complete_unknown_task_raises(clean_db: Engine) -> None:
    with pytest.raises(TaskNotFoundError):
        mark_task_completed(uuid4())


def test_cannot_complete_twice(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    claimed = get_task([Topic.PREDICT_VOICE], WORKER)
    assert claimed is not None
    mark_task_completed(claimed.id)
    with pytest.raises(InvalidStateTransitionError):
        mark_task_completed(claimed.id)


def test_error_message_truncated(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    claimed = get_task([Topic.PREDICT_VOICE], WORKER)
    assert claimed is not None
    failed = mark_task_failed(claimed.id, error_type="E" * 1000, error_message="m" * 100_000)
    assert failed.error_type is not None
    assert failed.error_message is not None
    assert len(failed.error_type) <= 255
    assert len(failed.error_message) <= 2000


def test_stale_processing_and_abandon(clean_db: Engine) -> None:
    add_task(Topic.PREDICT_VOICE, _predict())
    claimed = get_task([Topic.PREDICT_VOICE], WORKER)
    assert claimed is not None
    # Immediately, nothing is stale with a large threshold.
    assert list_stale_processing(timedelta(hours=1)) == []
    # With a zero threshold everything processing is "stale".
    stale = list_stale_processing(timedelta(seconds=0))
    assert len(stale) == 1
    abandoned = mark_abandoned(claimed.id)
    assert abandoned.status is TaskStatus.ABANDONED
    assert get_task_by_id(claimed.id) is not None
