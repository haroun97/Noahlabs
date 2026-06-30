"""Pydantic payload models and the typed topic->payload registry."""

from taskpool.payloads.base import TaskPayload
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload
from taskpool.payloads.registry import (
    TOPIC_PAYLOADS,
    AnyPayload,
    parse_payload,
    payload_model_for,
)

__all__ = [
    "TOPIC_PAYLOADS",
    "AnyPayload",
    "PredictVoicePayload",
    "RaiseVoiceAlertPayload",
    "TaskPayload",
    "parse_payload",
    "payload_model_for",
]
