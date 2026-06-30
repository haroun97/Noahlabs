"""The single source of truth mapping topics to their payload models.

This registry is what makes the system "typing-first" at runtime: given a topic
read back from the database, we know exactly which Pydantic model validates it.
Static overloads in :mod:`taskpool.service` provide the compile-time guarantee.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from taskpool.domain.topics import Topic
from taskpool.exceptions import PayloadValidationError, UnknownTopicError
from taskpool.payloads.base import TaskPayload
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload

AnyPayload = PredictVoicePayload | RaiseVoiceAlertPayload
"""Union of every concrete payload type."""

TOPIC_PAYLOADS: dict[Topic, type[TaskPayload]] = {
    Topic.PREDICT_VOICE: PredictVoicePayload,
    Topic.RAISE_VOICE_ALERT: RaiseVoiceAlertPayload,
}


def payload_model_for(topic: Topic) -> type[TaskPayload]:
    """Return the payload model registered for ``topic``."""
    try:
        return TOPIC_PAYLOADS[topic]
    except KeyError as exc:
        raise UnknownTopicError(str(topic)) from exc


def parse_payload(topic: Topic, raw: dict[str, Any]) -> TaskPayload:
    """Validate a raw JSONB dict into the concrete payload model for ``topic``.

    Raises :class:`PayloadValidationError` on failure (wrapping Pydantic).
    """
    model = payload_model_for(topic)
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise PayloadValidationError(f"Invalid payload for topic {topic.value!r}: {exc}") from exc
