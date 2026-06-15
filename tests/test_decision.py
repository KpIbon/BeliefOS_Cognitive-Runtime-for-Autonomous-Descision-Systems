"""Tests for the decision policy."""

from __future__ import annotations

import pytest

from beliefos.core.models import Severity, WorldState
from beliefos.decision.policy import decide


def _world(strength: float, confidence: float) -> WorldState:
    return WorldState(
        fused_strength=strength,
        overall_confidence=confidence,
        risk_score=abs(strength - 0.5) * confidence,
        volatility=0.1,
        contributing_subjects=["x"],
    )


def test_low_confidence_yields_stable_regardless_of_strength():
    d = decide(_world(strength=0.95, confidence=0.2))
    assert d.state == Severity.STABLE


def test_high_strength_high_confidence_triggers_alert_or_critical():
    d = decide(_world(strength=0.92, confidence=0.85))
    assert d.state in (Severity.ALERT, Severity.CRITICAL)


def test_neutral_world_with_high_confidence_stays_stable():
    d = decide(_world(strength=0.5, confidence=0.9))
    assert d.state == Severity.STABLE


def test_decision_includes_action_string():
    d = decide(_world(strength=0.9, confidence=0.85))
    assert d.action  # non-empty
    assert isinstance(d.action, str)


def test_decision_carries_world_state_summary():
    world = _world(strength=0.85, confidence=0.7)
    d = decide(world)
    assert d.rationale
    assert d.fused_strength == pytest.approx(world.fused_strength)
