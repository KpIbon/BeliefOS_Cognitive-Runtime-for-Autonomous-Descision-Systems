"""Smoke tests for the integration adapters."""

from __future__ import annotations

from beliefos.core.engine import BeliefEngine
from beliefos.integrations import anthropic, drones, openai, ros2


def test_openai_observation_from_successful_response():
    class _Resp:
        choices = [type("C", (), {"finish_reason": "stop"})()]
        # usage exists on real responses; absence is fine.
    obs = openai.observation_from_response(_Resp(), subject="openai")
    assert obs.subject == "openai"
    assert 0.0 <= obs.value <= 1.0


def test_openai_observation_from_truncated_response():
    class _Resp:
        choices = [type("C", (), {"finish_reason": "length"})()]
    obs = openai.observation_from_response(_Resp())
    assert obs.value < 0.5  # truncated => low confidence in result


def test_anthropic_observation():
    class _Resp:
        stop_reason = "end_turn"
        content = [type("B", (), {"text": "ok"})()]
    obs = anthropic.observation_from_response(_Resp(), subject="anthropic")
    assert obs.subject == "anthropic"
    assert obs.value > 0.5


def test_ros2_topic_to_subject():
    assert ros2.topic_to_subject("/battery/state") == "ros2.battery.state"
    assert ros2.topic_to_subject("/imu") == "ros2.imu"


def test_ros2_feed_telemetry(engine):
    ros2.feed_telemetry(
        engine,
        {
            "/battery/state": {"percent": 22.0, "voltage": 11.1},
            "/imu": {"temperature_c": 65.0},
        },
    )
    subjects = {b.subject for b in engine.beliefs()}
    assert "ros2.battery.state" in subjects


def test_drones_decision_to_mavlink_action():
    from beliefos.core.models import Decision, Severity

    d = Decision(
        state=Severity.WATCH,
        action="Increase monitoring",
        rationale="test",
        fused_strength=0.6,
        overall_confidence=0.55,
    )
    action = drones.decision_to_mavlink_action(d)
    assert action in {"hold", "monitor", "loiter", "rtl", "land", "continue"}


def test_drones_decision_critical_returns_rtl_or_land():
    from beliefos.core.models import Decision, Severity

    d = Decision(
        state=Severity.CRITICAL,
        action="Return / land",
        rationale="crit",
        fused_strength=0.95,
        overall_confidence=0.9,
    )
    action = drones.decision_to_mavlink_action(d)
    assert action in {"rtl", "land"}
