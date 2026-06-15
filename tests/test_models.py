"""Tests for domain models and update math."""

from __future__ import annotations

import math

import pytest

from beliefos.core.models import (
    Belief,
    Evidence,
    Observation,
    Severity,
    Trend,
    WorldState,
    _clip01,
)
from beliefos.core.update import apply_decay, record_observation


def test_clip01_bounds_and_nan():
    assert _clip01(-0.5) == 0.0
    assert _clip01(1.5) == 1.0
    assert _clip01(0.3) == 0.3
    assert math.isnan(_clip01(float("nan"))) or _clip01(float("nan")) == 0.0


def test_trend_classification():
    assert Trend.from_delta(0.05) is Trend.RISING
    assert Trend.from_delta(-0.05) is Trend.FALLING
    assert Trend.from_delta(0.0) is Trend.STABLE
    assert Trend.from_delta(0.01) is Trend.STABLE  # within eps


def test_observation_normalizes_subject_and_validates_value():
    obs = Observation(subject="  CPU ", value=0.6, source="test")
    assert obs.subject == "cpu"
    with pytest.raises(Exception):
        Observation(subject="x", value=1.5)


def test_belief_starts_empty():
    b = Belief(subject="cpu")
    assert b.strength == 0.0
    assert b.confidence == 0.0
    assert b.observation_count == 0


def test_record_observation_first_observation_sets_strength_to_value():
    b = Belief(subject="cpu")
    obs = Observation(subject="cpu", value=0.7, source="test")
    updated = record_observation(b, obs, weight=0.5)
    assert updated.strength == pytest.approx(0.7)
    assert updated.observation_count == 1
    assert updated.confidence > 0.0
    assert updated.last_value == 0.7
    assert updated.last_source == "test"


def test_record_observation_ema_moves_gradually():
    b = Belief(subject="cpu", strength=0.3, confidence=0.4, observation_count=2)
    obs = Observation(subject="cpu", value=1.0, confidence=0.8, source="t")
    updated = record_observation(b, obs, weight=0.5)
    # EMA: 0.3*0.5 + 1.0*0.5 = 0.65
    assert updated.strength == pytest.approx(0.65)


def test_record_observation_appends_evidence_and_caps_length():
    b = Belief(subject="cpu")
    for i in range(60):
        obs = Observation(subject="cpu", value=0.5, source="t", confidence=0.5)
        b = record_observation(b, obs, weight=0.5, max_evidence=10)
    assert len(b.evidence) == 10


def test_apply_decay_drift_toward_neutral():
    b = Belief(subject="cpu", strength=0.9, confidence=0.8)
    now = b.last_updated  # no time passed
    decayed = apply_decay(b, now, half_life_seconds=10.0)
    assert decayed.strength == pytest.approx(b.strength, abs=0.01)


def test_apply_decay_actually_decays():
    from datetime import timedelta

    b = Belief(subject="cpu", strength=0.9, confidence=0.8)
    later = b.last_updated + timedelta(seconds=1000)
    decayed = apply_decay(b, later, half_life_seconds=10.0)
    # Many half-lives have passed; should be very close to 0.5
    assert decayed.strength == pytest.approx(0.5, abs=0.01)
    assert decayed.confidence < b.confidence


def test_severity_levels_exist():
    assert Severity.STABLE.value == "stable"
    assert Severity.WATCH.value == "watch"
    assert Severity.ALERT.value == "alert"
    assert Severity.CRITICAL.value == "critical"


def test_world_state_serialization_roundtrip():
    ws = WorldState(
        overall_strength=0.6,
        overall_confidence=0.7,
        risk_score=0.3,
        trend=Trend.RISING,
        summary=["cpu"],
    )
    d = ws.as_dict()
    restored = WorldState.model_validate(d)
    assert restored.overall_strength == 0.6
    assert restored.summary == ["cpu"]
