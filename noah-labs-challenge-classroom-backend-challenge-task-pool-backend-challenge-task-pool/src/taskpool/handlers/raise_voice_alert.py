"""Handler for the ``raise_voice_alert`` topic (simulated work)."""

from __future__ import annotations

import time

from taskpool.payloads.raise_voice_alert import RaiseVoiceAlertPayload

HandlerResult = dict[str, object]

# Below this combined quality/score we would (simulate) raising an alert.
_ALERT_THRESHOLD = 0.5


def handle_raise_voice_alert(payload: RaiseVoiceAlertPayload) -> HandlerResult:
    """Evaluate a voice measurement and simulate an alert decision."""
    time.sleep(0.05)

    # Weight the alert decision by audio quality so noisy samples alert less.
    weighted = payload.voice_score * payload.audio_quality
    should_alert = weighted < _ALERT_THRESHOLD

    return {
        "user_id": str(payload.user_id),
        "measured_at": payload.measured_at.isoformat(),
        "weighted_score": round(weighted, 4),
        "alert_raised": should_alert,
    }
