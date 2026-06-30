"""Cross-cutting observability helpers (worker identity, log field names)."""

from __future__ import annotations

import os
import socket
from uuid import uuid4


def generate_worker_id() -> str:
    """Return a process-unique worker id: ``<hostname>-<pid>-<rand>``."""
    hostname = socket.gethostname()
    return f"{hostname}-{os.getpid()}-{uuid4().hex[:8]}"
