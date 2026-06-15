"""BeliefOS — a cognitive runtime that maintains evolving beliefs over time.

The package exposes the four-layer architecture (observation, belief, world
state, decision) plus a FastAPI surface and a small dashboard. The runtime
itself is engine-agnostic: storage is pluggable (SQLite for tests, PostgreSQL
in production), and Redis is used opportunistically as a write-through cache.
"""

from beliefos.core.config import Settings, get_settings
from beliefos.core.engine import BeliefEngine
from beliefos.core.models import (
    Belief,
    Decision,
    Evidence,
    Observation,
    Trend,
    WorldState,
)

__version__ = "0.1.0"

__all__ = [
    "Belief",
    "BeliefEngine",
    "Decision",
    "Evidence",
    "Observation",
    "Settings",
    "Trend",
    "WorldState",
    "get_settings",
]
