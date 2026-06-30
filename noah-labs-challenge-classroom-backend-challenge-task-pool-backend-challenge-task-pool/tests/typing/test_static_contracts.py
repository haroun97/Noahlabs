"""Static-typing contract checks.

This module is exercised by mypy (CI step "type check"), not at runtime. With
``warn_unused_ignores = true`` in the mypy config, each ``# type: ignore`` below
is itself an assertion: if the mismatched call were *not* a type error, mypy
would report the ignore as unused and fail. This is how we prove that the
overloads reject e.g. a RaiseVoiceAlertPayload on the predict_voice topic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import assert_type
from uuid import uuid4

from taskpool.domain.task import Task
from taskpool.domain.topics import Topic
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload
from taskpool.service import add_task

_predict = PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://b/k.wav")
_alert = RaiseVoiceAlertPayload(
    user_id=uuid4(), measured_at=datetime.now(tz=UTC), audio_quality=0.5, voice_score=0.5
)


def correct_calls_typecheck() -> None:
    # Correct topic/payload pairings: no ignore needed, precise return types.
    assert_type(add_task(Topic.PREDICT_VOICE, _predict), Task[PredictVoicePayload])
    assert_type(add_task(Topic.RAISE_VOICE_ALERT, _alert), Task[RaiseVoiceAlertPayload])


def mismatches_are_static_errors() -> None:
    # Wrong payload for the topic must be a static error (the ignore proves it).
    add_task(Topic.PREDICT_VOICE, _alert)  # type: ignore[call-overload]
    add_task(Topic.RAISE_VOICE_ALERT, _predict)  # type: ignore[call-overload]
