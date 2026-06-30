"""Application configuration loaded from the environment (12-factor).

All settings are read once at process start via :func:`get_settings`. No secrets
are hard-coded; ``.env.example`` documents every key with safe defaults.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings.

    Read from environment variables (and an optional ``.env`` file). Field names
    map to upper-case env vars, e.g. ``database_url`` -> ``DATABASE_URL``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://taskpool:taskpool@localhost:5433/taskpool",
        description="SQLAlchemy DSN. Must use the psycopg (v3) driver.",
    )
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)
    db_pool_pre_ping: bool = Field(default=True)
    db_pool_timeout_seconds: float = Field(default=30.0, gt=0)

    # --- Consumer behaviour -------------------------------------------------
    poll_interval_seconds: float = Field(default=1.0, gt=0)
    poll_jitter_seconds: float = Field(default=0.25, ge=0)
    db_retry_backoff_seconds: float = Field(default=2.0, gt=0)
    db_retry_max_backoff_seconds: float = Field(default=30.0, gt=0)

    # --- Topic selection (empty == all known topics) ------------------------
    taskpool_topics: str = Field(
        default="",
        description="Comma-separated topic subset for a consumer. Empty means all.",
    )

    # --- Logging ------------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    # --- Operational / hardening -------------------------------------------
    abandoned_threshold_seconds: int = Field(default=900, gt=0)
    max_payload_bytes: int = Field(default=64 * 1024, gt=0)
    max_error_message_chars: int = Field(default=2000, gt=0)
    max_error_type_chars: int = Field(default=255, gt=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def configured_topics(self) -> tuple[str, ...]:
        """Parsed, de-duplicated topic subset (order-preserving)."""
        raw = [t.strip() for t in self.taskpool_topics.split(",")]
        seen: dict[str, None] = {}
        for topic in raw:
            if topic:
                seen.setdefault(topic, None)
        return tuple(seen)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached process-wide settings instance."""
    return Settings()
