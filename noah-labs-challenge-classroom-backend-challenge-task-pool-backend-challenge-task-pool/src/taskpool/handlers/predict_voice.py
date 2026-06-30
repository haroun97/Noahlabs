"""Handler for the ``predict_voice`` topic (simulated work).

The handler is intentionally side-effect-free here: it validates/normalizes the
input, simulates download + inference latency, and returns a small result dict
for logging. Real implementations should be idempotent on ``user_id`` so a
manual re-creation of a task is a no-op rather than a duplicate effect.
"""

from __future__ import annotations

import hashlib
import time

from taskpool.payloads.predict_voice import PredictVoicePayload

HandlerResult = dict[str, object]


def handle_predict_voice(payload: PredictVoicePayload) -> HandlerResult:
    """Simulate downloading audio and running a voice prediction."""
    # Simulate I/O + inference. Deterministic, bounded for test stability.
    time.sleep(0.05)

    # A deterministic, fake "score" derived from the input (no real model).
    digest = hashlib.sha256(f"{payload.user_id}:{payload.audio_s3_url}".encode()).hexdigest()
    simulated_score = int(digest[:8], 16) / 0xFFFFFFFF

    return {
        "user_id": str(payload.user_id),
        "simulated_voice_score": round(simulated_score, 4),
    }
