"""Unit tests for the topic->payload registry and parsing."""

from __future__ import annotations

from uuid import uuid4

import pytest

from taskpool.domain.topics import ALL_TOPICS, Topic
from taskpool.exceptions import PayloadValidationError
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload
from taskpool.payloads.registry import TOPIC_PAYLOADS, parse_payload, payload_model_for


def test_registry_covers_every_topic() -> None:
    assert set(TOPIC_PAYLOADS) == set(ALL_TOPICS)


def test_payload_model_for() -> None:
    assert payload_model_for(Topic.PREDICT_VOICE) is PredictVoicePayload
    assert payload_model_for(Topic.RAISE_VOICE_ALERT) is RaiseVoiceAlertPayload


def test_parse_payload_roundtrip() -> None:
    raw = {"user_id": str(uuid4()), "audio_s3_url": "s3://bucket/a.wav"}
    parsed = parse_payload(Topic.PREDICT_VOICE, raw)
    assert isinstance(parsed, PredictVoicePayload)


def test_parse_payload_invalid_raises() -> None:
    with pytest.raises(PayloadValidationError):
        parse_payload(Topic.PREDICT_VOICE, {"user_id": "bad", "audio_s3_url": "s3://b/k"})


def test_parse_payload_wrong_shape_for_topic_raises() -> None:
    # raise_voice_alert payload sent to predict_voice topic -> validation error.
    raw = {
        "user_id": str(uuid4()),
        "measured_at": "2024-01-01T00:00:00+00:00",
        "audio_quality": 0.5,
        "voice_score": 0.5,
    }
    with pytest.raises(PayloadValidationError):
        parse_payload(Topic.PREDICT_VOICE, raw)
