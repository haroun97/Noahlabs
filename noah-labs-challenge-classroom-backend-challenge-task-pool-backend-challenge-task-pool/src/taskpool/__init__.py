"""taskpool: a PostgreSQL-backed task pool with safe concurrent claiming.

Public API is re-exported from :mod:`taskpool.service`.
"""

from taskpool.domain.task import Task
from taskpool.domain.topics import TaskStatus, Topic
from taskpool.service import (
    add_task,
    get_task,
    mark_task_completed,
    mark_task_failed,
)

__all__ = [
    "Task",
    "TaskStatus",
    "Topic",
    "add_task",
    "get_task",
    "mark_task_completed",
    "mark_task_failed",
]

__version__ = "0.1.0"
