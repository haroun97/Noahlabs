"""Exhaustive, type-safe dispatch from a claimed task to its handler.

Dispatch narrows on the payload union and ends with :func:`assert_never`, so
adding a new payload type without a handler is a *static* error (mypy will flag
the ``assert_never`` call). Handlers never touch task status; they only do work
and return a small result (or raise).
"""

from __future__ import annotations

from typing import assert_never

from taskpool.domain.task import Task
from taskpool.handlers.predict_voice import handle_predict_voice
from taskpool.handlers.raise_voice_alert import handle_raise_voice_alert
from taskpool.payloads.predict_voice import PredictVoicePayload
from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload

HandlerResult = dict[str, object]

ClaimedTask = Task[PredictVoicePayload] | Task[RaiseVoiceAlertPayload]


def dispatch(task: ClaimedTask) -> HandlerResult:
    """Route a claimed task to its topic handler (total over payload types)."""
    payload = task.payload
    if isinstance(payload, PredictVoicePayload):
        return handle_predict_voice(payload)
    if isinstance(payload, RaiseVoiceAlertPayload):
        return handle_raise_voice_alert(payload)
    assert_never(payload)
