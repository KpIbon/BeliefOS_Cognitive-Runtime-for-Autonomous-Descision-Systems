"""Belief update logic.

The update rule is intentionally small. We keep Belief instances as pure
data (Pydantic models) so they can be persisted and transmitted without
surprise.

The convention is "the new observation pulls the smoothed value toward it":

    new = (1 - alpha) * prev + alpha * observed

so alpha == 1 ignores history (and the first observation lands at the
observation value), and alpha == 0 freezes the belief in place.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable

from beliefos.core.config import get_settings
from beliefos.core.models import Belief, Evidence, Observation, Trend


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clip01(x: float) -> float:
    if math.isnan(x):
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def ema_update(prev: float, obs_value: float, alpha: float) -> float:
    """Standard EMA in the "pull toward new" direction."""
    return _clip01((1.0 - alpha) * prev + alpha * obs_value)


def update_confidence(
    prev_confidence: float,
    observation_count: int,
    observed_confidence: float,
    min_observations: int,
) -> float:
    """Confidence grows with observation count, but never exceeds 1.

    Below min_observations we cap growth so the decision layer doesn't
    act on shaky early signals.
    """
    if observation_count <= 0:
        return _clip01(observed_confidence)

    growth = 1.0 - math.exp(-observation_count / max(min_observations, 1))
    target = max(observed_confidence, growth)
    return _clip01(0.5 * prev_confidence + 0.5 * target)


def apply_decay(belief: Belief, now: datetime, half_life_seconds: float) -> Belief:
    """Time-based forgetting. Stale signals drift toward neutral (0.5)."""
    if half_life_seconds <= 0:
        return belief

    now_aware = (
        now
        if now.tzinfo
        else now.replace(tzinfo=timezone.utc)
    )
    last_aware = (
        belief.last_updated
        if belief.last_updated.tzinfo
        else belief.last_updated.replace(tzinfo=timezone.utc)
    )
    elapsed = max((now_aware - last_aware).total_seconds(), 0.0)
    if elapsed <= 0:
        return belief

    decay = math.pow(0.5, elapsed / half_life_seconds)

    new_strength = 0.5 + (belief.strength - 0.5) * decay
    new_confidence = belief.confidence * decay
    return belief.model_copy(
        update={
            "strength": _clip01(new_strength),
            "confidence": _clip01(new_confidence),
        }
    )


def record_observation(
    belief: Belief | None,
    observation: Observation,
    weight: float,
    max_evidence: int = 50,
) -> Belief:
    """Fold a new observation into the belief.

    The ``weight`` argument is the EMA pull-weight. Callers that pass a
    value in (0, 1] override the configured default for this observation
    (handy for high-importance signals). When belief is None we create a
    fresh belief seeded at the observed value so the first signal in a
    subject's life bootstraps correctly.
    """
    settings = get_settings()
    now = observation.timestamp or _utcnow()
    if belief is None or belief.observation_count == 0:
        # First observation for this subject: seed directly.
        belief = Belief(
            subject=observation.subject,
            strength=observation.value,
            confidence=observation.confidence,
            observation_count=1,
            last_value=observation.value,
            last_source=observation.source,
            trend=Trend.STABLE,
            first_seen=now,
            last_updated=now,
            previous_strength=0.0,
            value=observation.value,
            observations=1,
        )
        return belief

    decayed = apply_decay(belief, now, settings.decay_half_life_seconds)

    # When the caller passes an explicit per-observation weight in (0, 1]
    # we honor it; otherwise we use the configured default. weight == 0
    # means "don't move the belief" which is also a valid signal.
    if 0.0 <= weight <= 1.0:
        alpha = weight
    else:
        alpha = settings.ema_alpha
    new_strength = ema_update(decayed.strength, observation.value, alpha)
    new_count = decayed.observation_count + 1
    new_confidence = update_confidence(
        prev_confidence=decayed.confidence,
        observation_count=new_count,
        observed_confidence=observation.confidence,
        min_observations=settings.min_confidence_observations,
    )

    evidence = list(decayed.evidence)
    evidence.append(
        Evidence(
            observation_id=observation.id,
            value=observation.value,
            source=observation.source,
            weight=max(weight, 0.0),
            timestamp=now,
        )
    )
    if len(evidence) > max_evidence:
        evidence = evidence[-max_evidence:]

    trend = Trend.from_delta(new_strength - decayed.strength)

    return decayed.model_copy(
        update={
            "previous_strength": decayed.strength,
            "strength": new_strength,
            "confidence": new_confidence,
            "observation_count": new_count,
            "last_value": observation.value,
            "last_source": observation.source,
            "trend": trend,
            "evidence": evidence,
            "last_updated": now,
            "value": new_strength,
            "observations": new_count,
        }
    )


def merge_evidence(evidence: Iterable[Evidence]) -> list[Evidence]:
    return sorted(evidence, key=lambda e: e.timestamp)
