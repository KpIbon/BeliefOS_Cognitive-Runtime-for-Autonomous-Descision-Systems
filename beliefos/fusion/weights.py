"""Domain priors — a weight per subject.

Higher weight = the subject matters more when fusing beliefs. The defaults
are biased toward infrastructure health because that's the SDK's first use
case, but the registry is open: integrations (OpenAI, Anthropic, ROS2,
drones) can register their own subjects at runtime.

``set_weight(name, None)`` is a no-op (or "reset to default" if a default
exists) so callers can do ``set_weight("x", override_or_none)`` without
type-checking.
"""
from __future__ import annotations

from threading import RLock
from typing import Mapping

DEFAULT_WEIGHTS: Mapping[str, float] = {
    # infrastructure
    "error_rate": 0.95,
    "request_latency": 0.80,
    "cpu_pressure": 0.70,
    "memory_pressure": 0.65,
    "disk_pressure": 0.50,
    # perception / agents
    "object_detection_confidence": 0.85,
    "anomaly_score": 0.90,
    # autonomy
    "drone_battery": 0.95,
    "drone_weather_risk": 0.80,
    "drone_obstacle_proximity": 0.95,
    "drone_gnss_quality": 0.70,
    # language models
    "llm_hallucination_risk": 0.90,
    "llm_tool_call_failure": 0.85,
}

DEFAULT_WEIGHT = 0.5

_lock = RLock()
_weights: dict[str, float] = dict(DEFAULT_WEIGHTS)


def get_weight(subject: str) -> float:
    with _lock:
        return _weights.get(subject.lower(), DEFAULT_WEIGHT)


def set_weight(subject: str, weight: float | None) -> None:
    """Register a weight override for a subject.

    ``None`` is a no-op (it just ensures no override exists for this name),
    so callers can pass an override-or-None without branching.
    """
    if weight is None:
        with _lock:
            _weights.pop(subject.lower(), None)
        return
    if not 0.0 <= weight <= 1.0:
        raise ValueError("weight must be in [0, 1]")
    with _lock:
        _weights[subject.lower()] = float(weight)


def reset_weights() -> None:
    with _lock:
        _weights.clear()
        _weights.update(DEFAULT_WEIGHTS)


def all_weights() -> dict[str, float]:
    with _lock:
        return dict(_weights)
