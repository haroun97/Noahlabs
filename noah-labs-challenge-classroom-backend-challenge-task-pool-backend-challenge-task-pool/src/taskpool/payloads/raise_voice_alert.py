"""Payload for the ``raise_voice_alert`` topic."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field

from taskpool.payloads.base import TaskPayload

UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
"""A float constrained to the closed interval [0, 1]."""


class RaiseVoiceAlertPayload(TaskPayload):
    """Input for a simulated voice-alert evaluation.

    ``measured_at`` must be timezone-aware (enforced by :class:`AwareDatetime`).
    ``audio_quality`` and ``voice_score`` are constrained to ``[0, 1]``.
    """

    user_id: UUID
    measured_at: AwareDatetime
    audio_quality: UnitInterval
    voice_score: UnitInterval
