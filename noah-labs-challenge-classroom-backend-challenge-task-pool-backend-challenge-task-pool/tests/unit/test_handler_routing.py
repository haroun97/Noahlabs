"""Unit tests for handler dispatch and individual handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from taskpool.domain.task import Task
from taskpool.domain.topics import TaskStatus, Topic
from taskpool.handlers.base import dispatch
from taskpool.handlers.predict_voice import handle_predict_voice
from taskpool.handlers.raise_voice_alert import handle_raise_voice_alert
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _predict_task() -> Task[PredictVoicePayload]:
    return Task[PredictVoicePayload](
        id=uuid4(),
        topic=Topic.PREDICT_VOICE,
        payload=PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://b/k.wav"),
        status=TaskStatus.PROCESSING,
        created_at=_now(),
        updated_at=_now(),
    )


def _alert_task() -> Task[RaiseVoiceAlertPayload]:
    return Task[RaiseVoiceAlertPayload](
        id=uuid4(),
        topic=Topic.RAISE_VOICE_ALERT,
        payload=RaiseVoiceAlertPayload(
            user_id=uuid4(), measured_at=_now(), audio_quality=0.2, voice_score=0.2
        ),
        status=TaskStatus.PROCESSING,
        created_at=_now(),
        updated_at=_now(),
    )


def test_handle_predict_voice_deterministic() -> None:
    payload = PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://b/k.wav")
    result_a = handle_predict_voice(payload)
    result_b = handle_predict_voice(payload)
    assert result_a == result_b
    assert 0.0 <= float(result_a["simulated_voice_score"]) <= 1.0  # type: ignore[arg-type]


def test_handle_raise_voice_alert_raises_on_low_score() -> None:
    payload = RaiseVoiceAlertPayload(
        user_id=uuid4(), measured_at=_now(), audio_quality=0.1, voice_score=0.1
    )
    result = handle_raise_voice_alert(payload)
    assert result["alert_raised"] is True


def test_dispatch_routes_predict_voice() -> None:
    result = dispatch(_predict_task())
    assert "simulated_voice_score" in result


def test_dispatch_routes_raise_voice_alert() -> None:
    result = dispatch(_alert_task())
    assert "alert_raised" in result
