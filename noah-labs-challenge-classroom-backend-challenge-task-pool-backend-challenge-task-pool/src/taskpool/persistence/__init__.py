"""SQLAlchemy persistence layer (table mappings only, no business rules)."""

from taskpool.persistence.models import Base, TaskRow

__all__ = ["Base", "TaskRow"]
