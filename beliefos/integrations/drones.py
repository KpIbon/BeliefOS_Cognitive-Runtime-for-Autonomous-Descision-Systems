"""Autonomous drone integration.

BeliefOS is well suited to drone state estimation because a drone produces
many noisy signals (battery, GPS lock, link quality, IMU health). A single
sensor is unreliable, but the *fused* belief is the right basis for action.

This adapter provides two pieces of glue:

*   :func:`feed_telemetry` - turn a telemetry dict into observations.
*   :func:`decision_to_mavlink_action` - turn a ``Decision`` into a
    high-level MAVLink action name (e.g. ``rtl``, ``land``, ``hold``,
    ``loiter``, ``continue``). MAVLink command serialization is the
    caller's responsibility (e.g. via ``pymavlink``).
"""
from __future__ import annotations

from typing import Mapping

from beliefos.core.engine import BeliefEngine
from beliefos.core.models import Decision, Observation, Severity


# Mapping of telemetry keys to belief subjects. Extend at runtime via
# :func:`register_mapping`.
DEFAULT_TELEMETRY_MAP: Mapping[str, str] = {
    "battery_percent": "drone.battery",
    "gps_satellites": "drone.gps",
    "link_quality": "drone.link",
    "imu_health": "drone.imu",
    "wind_speed_mps": "drone.wind",
}


def register_mapping(telemetry_key: str, subject: str) -> None:
    """Add or override a telemetry -> subject mapping at runtime."""
    globals()["DEFAULT_TELEMETRY_MAP"] = {**DEFAULT_TELEMETRY_MAP, telemetry_key: subject}


def _normalize(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def telemetry_to_observations(
    telemetry: Mapping[str, float], *, source: str = "drone"
) -> list[Observation]:
    obs: list[Observation] = []
    for key, value in telemetry.items():
        subject = DEFAULT_TELEMETRY_MAP.get(key, f"drone.{key}")
        # Battery and satellites are higher-is-better (so value=1 is good).
        # Wind speed is lower-is-better: invert.
        if key == "wind_speed_mps":
            value = 1.0 - min(1.0, float(value) / 25.0)
        else:
            value = _normalize(value)
        obs.append(Observation(subject=subject, value=value, source=source))
    return obs


def feed_telemetry(engine: BeliefEngine, telemetry: Mapping[str, float]) -> int:
    """Feed a single telemetry frame. Returns the number of observations added."""
    n = 0
    for obs in telemetry_to_observations(telemetry):
        engine.observe(obs)
        n += 1
    return n


# Action names are lower-case, MAVLink-style verbs the caller dispatches on.
_ACTION_BY_SEVERITY = {
    Severity.CRITICAL: "rtl",
    Severity.ALERT: "land",
    Severity.WATCH: "loiter",
    Severity.STABLE: "continue",
}


def decision_to_mavlink_action(decision: Decision) -> str:
    """Translate a Decision into a high-level MAVLink action name.

    * ``critical``   -> ``rtl`` (return to launch; or ``land`` for CRITICAL
       emergencies)
    * ``alert``      -> ``land`` (bring it down safely)
    * ``watch``      -> ``loiter`` (hold position, observe)
    * ``stable``     -> ``continue`` (resume mission)
    """
    return _ACTION_BY_SEVERITY[decision.state]
