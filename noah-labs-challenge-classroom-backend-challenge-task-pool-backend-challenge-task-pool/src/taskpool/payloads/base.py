"""Base class for all topic payloads."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TaskPayload(BaseModel):
    """Common configuration for every task payload.

    - ``extra="forbid"``: unknown fields are a validation error (catches typos
      and topic/payload mismatches at runtime).
    - ``frozen=True``: payloads are immutable value objects.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
