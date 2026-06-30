"""Payload for the ``predict_voice`` topic."""

from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from pydantic import field_validator

from taskpool.payloads.base import TaskPayload


class PredictVoicePayload(TaskPayload):
    """Input for a simulated voice prediction job.

    ``audio_s3_url`` is validated for shape only (scheme/host). We never fetch it
    here, so there is no SSRF surface; validation simply rejects obvious garbage.
    """

    user_id: UUID
    audio_s3_url: str

    @field_validator("audio_s3_url")
    @classmethod
    def _validate_s3_url(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("audio_s3_url must not be empty")
        parsed = urlparse(value)
        if parsed.scheme not in {"s3", "https", "http"}:
            raise ValueError(
                f"audio_s3_url must use an s3:// or http(s):// scheme, got {parsed.scheme!r}"
            )
        if not parsed.netloc:
            raise ValueError("audio_s3_url must include a host/bucket")
        return value
