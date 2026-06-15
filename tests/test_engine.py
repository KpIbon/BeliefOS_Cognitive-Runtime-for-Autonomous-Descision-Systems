"""Tests for the BeliefEngine orchestration."""

from __future__ import annotations

import pytest

from beliefos.core.engine import BeliefEngine
from beliefos.core.models import Severity, Observation
from beliefos.storage.repository import BeliefRepository


def test_observe_creates_belief(engine):
    belief = engine.observe(Observation(subject="cpu", value=0.6))
    assert belief.subject == "cpu"
    assert belief.value == pytest.approx(0.6)
    assert belief.observations == 1


def test_repeated_observations_grow_confidence(engine):
    b = engine.observe(Observation(subject="cpu", value=0.6))
    for _ in range(20):
        b = engine.observe(Observation(subject="cpu", value=0.6))
    assert b.observations == 21
    assert b.confidence > 0.8


def test_world_state_reflects_fused_beliefs(engine):
    engine.observe(Observation(subject="cpu", value=0.9))
    engine.observe(Observation(subject="error_rate", value=0.95))
    ws = engine.world_state()
    assert ws.fused_strength > 0.5
    assert ws.overall_confidence > 0.0


def test_decide_returns_decision_with_state(engine):
    for _ in range(8):
        engine.observe(Observation(subject="error_rate", value=0.95))
    d = engine.decide()
    assert d.state in (
        Severity.STABLE,
        Severity.WATCH,
        Severity.ALERT,
        Severity.CRITICAL,
    )


def test_beliefs_endpoint_lists_all(engine):
    engine.observe(Observation(subject="a", value=0.7))
    engine.observe(Observation(subject="b", value=0.3))
    beliefs = engine.beliefs()
    subjects = {b.subject for b in beliefs}
    assert subjects == {"a", "b"}


def test_engine_persists_across_calls(engine):
    engine.observe(Observation(subject="persist", value=0.7))
    # The repository must contain the new belief after observe.
    with engine.repository.session() as s:
        repo = BeliefRepository(s)
        row = repo.get_belief("persist")
        assert row is not None
        assert row.observations == 1


def test_engine_observe_returns_belief(engine):
    belief = engine.observe(Observation(subject="disk", value=0.5))
    assert belief.subject == "disk"
    assert 0.0 <= belief.strength <= 1.0


def test_engine_ready_initializes_schema():
    """`BeliefEngine.ready()` should init the DB and return a usable engine."""
    from beliefos.storage.database import init_db

    init_db()  # idempotent — only creates missing tables
    engine = BeliefEngine.ready()
    belief = engine.observe(Observation(subject="memory", value=0.4))
    assert belief.subject == "memory"
    assert 0.0 <= belief.strength <= 1.0
