"""Runtime configuration.

The default configuration uses SQLite + an in-memory cache so the service can
boot in any environment. PostgreSQL and Redis are opt-in via env vars. This
makes the test suite hermetic and the developer experience smooth.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings.

    Environment variables use the ``BELIEFOS_`` prefix. For example,
    ``BELIEFOS_DATABASE_URL=postgresql+psycopg://...``.
    """

    model_config = SettingsConfigDict(
        env_prefix="BELIEFOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BeliefOS"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # Storage
    database_url: str = Field(
        default="sqlite:///./beliefos.db",
        description="SQLAlchemy URL. Use postgresql+psycopg://... in production.",
    )
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Cache
    redis_url: str | None = Field(
        default=None,
        description="If set, the cache layer is enabled. Leave blank for in-process.",
    )
    cache_ttl_seconds: int = 30

    # Belief update
    ema_alpha: float = Field(default=0.35, ge=0.0, le=1.0)
    decay_half_life_seconds: float = 300.0
    min_confidence_observations: int = 3

    # Decision policy thresholds
    watch_threshold: float = 0.45
    alert_threshold: float = 0.65
    critical_threshold: float = 0.82
    min_confidence_to_act: float = 0.40
    alert_confidence: float = 0.50

    # World state
    world_state_window: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings, cached for cheap access."""

    return Settings()
