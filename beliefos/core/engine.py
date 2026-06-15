"""The BeliefEngine: orchestrates the four layers.

This is the single entry point used by the FastAPI app, integrations, and
the dashboard. It is intentionally synchronous: each call performs one
observation, applies a belief update, fuses, and decides. The runtime is
fast enough that we don't need a worker queue yet — when the load grows,
we add a Redis-backed queue behind this same interface.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from beliefos.core.config import get_settings
from beliefos.core.models import (
    Belief,
    Decision,
    Observation,
    WorldState,
)
from beliefos.core.update import apply_decay, record_observation
from beliefos.decision.policy import decide as decide_on
from beliefos.fusion.fuse import fuse_beliefs
from beliefos.fusion.weights import get_weight
from beliefos.storage.cache import Cache, get_cache
from beliefos.storage.database import session_scope
from beliefos.storage.repository import BeliefRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BeliefEngine:
    """High-level facade.

    The engine keeps a single unit-of-work per call, so an HTTP request can
    observe, persist, fuse, and decide atomically. Higher-throughput callers
    can drive the same primitives directly via the repository.
    """

    def __init__(self, cache: Cache | None = None) -> None:
        self._cache = cache or get_cache()
        self._settings = get_settings()

    @classmethod
    def ready(cls) -> "BeliefEngine":
        """Initialize the schema and return a fresh engine.

        Convenience for scripts and the example: ensures the underlying
        database has the required tables before the first observation.
        The FastAPI app does the same on startup via lifespan.
        """
        from beliefos.storage.database import init_db

        init_db()
        return cls()

    # ----- observation ---------------------------------------------------
    def observe(self, observation: Observation) -> Belief:
        """Record an observation and update the matching belief."""
        with session_scope() as session:
            repo = BeliefRepository(session)
            existing = repo.get_belief(observation.subject)
            now = observation.created_at
            if existing is not None:
                existing = apply_decay(existing, now, self._settings.decay_half_life_seconds)
            updated = record_observation(existing, observation, self._settings.ema_alpha)
            repo.add_observation(observation)
            saved = repo.upsert_belief(updated)
            self._cache.delete("world_state")
            self._cache.delete("decision")
            return saved

    # ----- reads ---------------------------------------------------------
    def list_beliefs(self, with_decay: bool = True) -> list[Belief]:
        with session_scope() as session:
            beliefs = BeliefRepository(session).list_beliefs()
        if not with_decay:
            return beliefs
        now = _utcnow()
        return [apply_decay(b, now, self._settings.decay_half_life_seconds) for b in beliefs]

    # Short alias used by integrations.
    def beliefs(self) -> list[Belief]:
        return self.list_beliefs()

    def get_belief(self, subject: str) -> Belief | None:
        with session_scope() as session:
            belief = BeliefRepository(session).get_belief(subject)
        if belief is None:
            return None
        return apply_decay(belief, _utcnow(), self._settings.decay_half_life_seconds)

    # ----- world state ---------------------------------------------------
    def world_state(self) -> WorldState:
        cached = self._cache.get("world_state")
        if cached is not None:
            return WorldState.model_validate(cached)

        beliefs = self.list_beliefs()
        weights = {b.subject: get_weight(b.subject) for b in beliefs}
        state = fuse_beliefs(beliefs, weights=weights)
        with session_scope() as session:
            BeliefRepository(session).save_world_state(state)
        self._cache.set("world_state", state.model_dump(mode="json"), ttl_seconds=15)
        return state

    # ----- decision ------------------------------------------------------
    def decide(self) -> Decision:
        cached = self._cache.get("decision")
        if cached is not None:
            return Decision.model_validate(cached)

        state = self.world_state()
        decision = decide_on(state)
        with session_scope() as session:
            repo = BeliefRepository(session)
            row = repo.save_world_state(state)
            repo.save_decision(decision, world_snapshot_id=row.id)
        self._cache.set("decision", decision.model_dump(mode="json"), ttl_seconds=15)
        return decision

    # ----- reporting -----------------------------------------------------
    def full_report(self) -> dict:
        beliefs = self.list_beliefs()
        state = self.world_state()
        decision = self.decide()
        return {
            "beliefs": [b.model_dump(mode="json") for b in beliefs],
            "world_state": state.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
        }

    # ----- raw access ----------------------------------------------------
    @property
    def repository(self) -> "RepositoryContext":
        """A small accessor for tests that need to inspect the DB directly."""
        from beliefos.storage.database import session_scope

        return RepositoryContext(session_scope)


class RepositoryContext:
    """Tiny context manager that yields a session using the engine's DB."""

    def __init__(self, scope_factory) -> None:
        self._scope = scope_factory

    def session(self):
        return self._scope()


_engine: "BeliefEngine" | None = None
_schema_ready = False


def get_engine() -> "BeliefEngine":
    """Return a process-wide engine. Used by FastAPI dependencies.

    On first call, ensures the DB schema exists. Subsequent calls reuse the
    cached engine. Tests call ``reset_engine_for_tests()`` to clear both the
    engine and the schema-ready flag.
    """
    global _engine, _schema_ready
    if _engine is None:
        from beliefos.storage.database import init_db

        init_db()
        _schema_ready = True
        _engine = BeliefEngine()
    elif not _schema_ready:
        from beliefos.storage.database import init_db

        init_db()
        _schema_ready = True
    return _engine


def reset_engine_for_tests() -> None:
    """Clear the cached engine. Tests call this between cases."""
    global _engine, _schema_ready
    _engine = None
    _schema_ready = False
