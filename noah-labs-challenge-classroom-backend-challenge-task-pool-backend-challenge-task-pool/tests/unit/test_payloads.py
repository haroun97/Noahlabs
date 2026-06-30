"""Unit tests for payload validation (runtime guarantees via Pydantic)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload


def test_predict_voice_valid() -> None:
    payload = PredictVoicePayload(user_id=uuid4(), audio_s3_url="s3://bucket/key.wav")
    assert payload.audio_s3_url.startswith("s3://")


def test_predict_voice_rejects_bad_uuid() -> None:
    with pytest.raises(ValidationError):
        PredictVoicePayload(user_id="not-a-uuid", audio_s3_url="s3://b/k")


@pytest.mark.parametrize("bad_url", ["", "   ", "ftp://host/x", "not-a-url", "s3://"])
def test_predict_voice_rejects_bad_url(bad_url: str) -> None:
    with pytest.raises(ValidationError):
        PredictVoicePayload(user_id=uuid4(), audio_s3_url=bad_url)


def test_predict_voice_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PredictVoicePayload(  # type: ignore[call-arg]
            user_id=uuid4(), audio_s3_url="s3://b/k", extra="nope"
        )


def test_raise_voice_alert_valid() -> None:
    payload = RaiseVoiceAlertPayload(
        user_id=uuid4(),
        measured_at=datetime.now(tz=UTC),
        audio_quality=0.5,
        voice_score=0.9,
    )
    assert 0.0 <= payload.voice_score <= 1.0


def test_raise_voice_alert_requires_tz_aware_datetime() -> None:
    with pytest.raises(ValidationError):
        RaiseVoiceAlertPayload(
            user_id=uuid4(),
            measured_at=datetime(2024, 1, 1, 12, 0, 0),  # naive
            audio_quality=0.5,
            voice_score=0.5,
        )


@pytest.mark.parametrize("score", [-0.01, -1.0, 1.01, 2.0])
def test_raise_voice_alert_rejects_out_of_range_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        RaiseVoiceAlertPayload(
            user_id=uuid4(),
            measured_at=datetime.now(tz=UTC),
            audio_quality=score,
            voice_score=0.5,
        )
    with pytest.raises(ValidationError):
        RaiseVoiceAlertPayload(
            user_id=uuid4(),
            measured_at=datetime.now(tz=UTC),
            audio_quality=0.5,
            voice_score=score,
        )


@pytest.mark.parametrize("score", [0.0, 1.0, 0.5])
def test_raise_voice_alert_accepts_boundary_scores(score: float) -> None:
    payload = RaiseVoiceAlertPayload(
        user_id=uuid4(),
        measured_at=datetime.now(tz=UTC),
        audio_quality=score,
        voice_score=score,
    )
    assert payload.audio_quality == score
