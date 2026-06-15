"""ROS2 integration.

ROS2 topics are the natural place to express low-level robot state. We map
each topic of interest into a ``Subject`` namespace (``ros2.<topic>``) so the
belief engine can fuse dozens of topics without name collisions.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from beliefos.core.engine import BeliefEngine
from beliefos.core.models import Observation


def topic_to_subject(topic: str) -> str:
    """Convert a ROS2 topic name to a BeliefOS subject.

    >>> topic_to_subject("/battery/state")
    'ros2.battery.state'
    """
    return "ros2." + topic.lstrip("/").replace("/", ".")


def message_to_value(msg: Any) -> float:
    """Extract a scalar confidence in [0, 1] from a ROS2 message.

    Heuristic: if the message has a ``data``/``value``/``percent``/``level``
    float, use it (normalized); else 0.5.
    """
    for attr in ("data", "value", "percent", "level"):
        if hasattr(msg, attr):
            v = getattr(msg, attr)
            try:
                f = float(v)
                if 0.0 <= f <= 1.0:
                    return f
                return max(0.0, min(1.0, f / 100.0))
            except (TypeError, ValueError):
                continue
    return 0.5


def build_observation(topic: str, msg: Any, *, source: str = "ros2") -> Observation:
    return Observation(
        subject=topic_to_subject(topic),
        value=message_to_value(msg),
        source=source,
        note=getattr(msg, "_type", None) or "",
    )


def feed_topic(
    engine: BeliefEngine,
    topic: str,
    messages: Iterable[Any],
) -> int:
    """Feed all messages from a topic iterator into the engine."""
    count = 0
    for msg in messages:
        engine.observe(build_observation(topic, msg))
        count += 1
    return count


def feed_telemetry(
    engine: BeliefEngine,
    telemetry: Mapping[str, Mapping[str, float]],
) -> int:
    """Feed a dict-of-topic -> payload mapping.

    For testing or scripts where you don't want to spin up a real ROS2
    subscription, this lets you push an entire frame at once.
    """
    count = 0
    for topic, payload in telemetry.items():
        engine.observe(build_observation(topic, _DictLikeMsg(payload)))
        count += 1
    return count


def make_topic_callback(
    engine: BeliefEngine, topic: str
) -> Callable[[Any], None]:
    """Return a callback suitable for ``rclpy.subscription``."""
    def _cb(msg: Any) -> None:
        engine.observe(build_observation(topic, msg))
    return _cb


class _DictLikeMsg:
    """Wrapper so dict-based payloads work with ``message_to_value``."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)

    def __getattr__(self, item: str) -> Any:
        try:
            return self._payload[item]
        except KeyError:
            raise AttributeError(item)
