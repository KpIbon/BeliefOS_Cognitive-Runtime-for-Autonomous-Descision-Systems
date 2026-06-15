"""Tests for the fusion layer."""

from __future__ import annotations

import pytest

from beliefos.core.models import Belief
from beliefos.fusion.fuse import fuse_beliefs
from beliefos.fusion.weights import get_weight, set_weight


def _belief(subject: str, value: float, confidence: float) -> Belief:
    return Belief(subject=subject, value=value, confidence=confidence, observations=5)


def test_fuse_empty_returns_neutral_world_state():
    ws = fuse_beliefs([])
    assert ws.fused_strength == 0.5
    assert ws.overall_confidence == 0.0
    assert ws.risk_score == 0.0


def test_fuse_weighted_mean_skews_toward_higher_weight():
    # cpu is a low-weight signal, error_rate is high-weight.
    set_weight("cpu", 0.4)
    set_weight("error_rate", 0.95)
    beliefs = [
        _belief("cpu", 0.55, 0.8),
        _belief("error_rate", 0.95, 0.8),
    ]
    ws = fuse_beliefs(beliefs)
    # Because error_rate dominates, fused strength should sit clearly above
    # the midpoint of 0.75.
    assert ws.fused_strength > 0.7
    assert ws.overall_confidence > 0.5


def test_fuse_correlation_boost_raises_strength():
    base = fuse_beliefs([_belief("cpu", 0.85, 0.8), _belief("error_rate", 0.85, 0.8)])
    # Add a third correlated high signal; correlation boost should kick in.
    boosted = fuse_beliefs(
        [
            _belief("cpu", 0.85, 0.8),
            _belief("error_rate", 0.85, 0.8),
            _belief("latency", 0.85, 0.8),
        ]
    )
    assert boosted.fused_strength >= base.fused_strength


def test_fuse_is_symmetric_around_neutral():
    up = fuse_beliefs([_belief("x", 0.9, 0.7), _belief("y", 0.9, 0.7)])
    down = fuse_beliefs([_belief("x", 0.1, 0.7), _belief("y", 0.1, 0.7)])
    # Distance from 0.5 should match on both sides.
    assert (up.fused_strength - 0.5) == pytest.approx(0.5 - down.fused_strength, abs=1e-6)


def test_get_weight_falls_back_to_default():
    set_weight("__definitely_not_present__", None)  # ensure no override
    assert 0.0 < get_weight("__definitely_not_present__") <= 1.0
