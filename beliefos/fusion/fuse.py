"""Fuse per-subject beliefs into a single world state.

The fusion rule is deliberately simple and interpretable.

Each belief contributes a weight = prior_weight * confidence.
The fused strength is the confidence-weighted mean of values in [0, 1],
biased toward the high-weight subjects.
A correlation boost rewards multi-signal agreement: when several beliefs
all point the same direction, we add a small bonus.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

from beliefos.core.models import Belief, Trend, WorldState
from beliefos.fusion.weights import DEFAULT_WEIGHT, get_weight


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _signed_distance(x: float) -> float:
    """Return x - 0.5 signed, mapped into [-1, 1]."""
    return max(-1.0, min(1.0, x - 0.5)) * 2.0


def correlation_boost(beliefs: Sequence[Belief]) -> float:
    """Multi-signal agreement bonus in [0, 0.15]."""
    if len(beliefs) < 3:
        return 0.0
    signed = [_signed_distance(_strength_of(b)) for b in beliefs]
    same_sign = (
        sum(1 for s in signed if s > 0) == len(signed)
        or sum(1 for s in signed if s < 0) == len(signed)
    )
    if not same_sign:
        return 0.0
    avg_abs = sum(abs(s) for s in signed) / len(signed)
    return min(0.15, 0.05 * math.log2(len(beliefs) + 1) * avg_abs)


def _strength_of(b: Belief) -> float:
    """Return the canonical [0, 1] strength for a belief."""
    return b.value if b.value is not None else b.strength


def fuse_beliefs(
    beliefs: Iterable[Belief],
    weights: Mapping[str, float] | None = None,
    now: datetime | None = None,
) -> WorldState:
    """Combine beliefs into a single WorldState.

    Returns a neutral world state when no beliefs exist. ``weights`` is an
    optional subject to weight map; if omitted, the registered default
    weights are used.
    """
    belief_list = list(beliefs)
    if not belief_list:
        return WorldState(
            overall_strength=0.5,
            overall_confidence=0.0,
            risk_score=0.0,
            generated_at=now or _utcnow(),
        )

    def _w(subject: str) -> float:
        if weights is not None and subject in weights:
            v = weights[subject]
            return float(v) if v is not None else DEFAULT_WEIGHT
        return get_weight(subject)

    weighted_sum = 0.0
    weight_total = 0.0
    confidence_sum = 0.0
    for b in belief_list:
        w = _w(b.subject) * max(b.confidence, 1e-6)
        weighted_sum += _strength_of(b) * w
        weight_total += w
        confidence_sum += b.confidence

    if weight_total <= 0:
        return WorldState(
            overall_strength=0.5,
            overall_confidence=0.0,
            risk_score=0.0,
            generated_at=now or _utcnow(),
        )

    mean_value = weighted_sum / weight_total
    mean_confidence = confidence_sum / len(belief_list)
    boost = correlation_boost(belief_list)

    # Smooth by scaling the signed distance from neutral so 0.9 and 0.1
    # move toward 0.5 by the same amount. Apply the correlation boost
    # after the smoothing so multi-signal agreement still lifts the world.
    signed = (mean_value - 0.5) * 0.85
    fused = max(0.0, min(1.0, 0.5 + signed + boost))
    breadth = min(1.0, math.log2(len(belief_list) + 1) / 4.0)
    confidence = max(0.0, min(1.0, mean_confidence * (0.6 + 0.4 * breadth)))
    risk = fused * confidence
    summary = [f"{b.subject}={_strength_of(b):.2f}" for b in belief_list[:5]]

    return WorldState(
        overall_strength=fused,
        overall_confidence=confidence,
        risk_score=risk,
        trend=_trend(belief_list),
        contributing_subjects=[b.subject for b in belief_list],
        summary=summary,
        generated_at=now or _utcnow(),
    )


def _trend(beliefs: Sequence[Belief]) -> Trend:
    deltas = []
    for b in beliefs:
        prev = b.previous_strength if b.previous_strength is not None else b.previous_strength
        cur = _strength_of(b)
        if b.observation_count > 0:
            deltas.append(cur - prev)
    if not deltas:
        return Trend.STABLE
    return Trend.from_delta(sum(deltas) / len(deltas))
