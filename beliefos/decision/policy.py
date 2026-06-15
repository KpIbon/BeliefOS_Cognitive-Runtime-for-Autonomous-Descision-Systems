"""Map a world state to a recommended decision.

The policy treats ``overall_strength`` as a signed distance from neutral
(0.5). A strength of 0.5 means "no signal"; 0.95 means "strong problem";
0.05 means "strong safety". This keeps a neutral world (0.5) from being
treated as an alarm. Each tier (watch, alert, critical) requires the
distance to be at least as large as the threshold margin and confidence
to clear the relevant floor. Confidence floors are tunable via
:mod:`beliefos.core.config`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from beliefos.core.config import get_settings
from beliefos.core.models import Decision, Severity, WorldState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_SEVERITY_ACTIONS: dict[Severity, str] = {
    Severity.STABLE: "Hold posture. Continue routine observation.",
    Severity.WATCH: "Increase observation cadence. Surface to on-call dashboard.",
    Severity.ALERT: "Page on-call. Capture evidence snapshot.",
    Severity.CRITICAL: "Engage runbook. Notify integrations (autonomous agents, drones).",
}


def _rationale(world: WorldState, state: Severity, settings) -> str:
    parts: list[str] = []
    direction = "elevated" if world.overall_strength >= 0.5 else "depressed"
    if state == Severity.STABLE and world.overall_confidence < settings.min_confidence_to_act:
        parts.append(
            f"Confidence {world.overall_confidence:.2f} below action floor "
            f"{settings.min_confidence_to_act:.2f} - holding posture."
        )
    elif state == Severity.STABLE:
        parts.append(
            f"World strength {world.overall_strength:.2f} near neutral "
            f"({direction} by {abs(world.overall_strength - 0.5):.2f}) - system appears healthy."
        )
    elif state == Severity.WATCH:
        parts.append(
            f"World strength {world.overall_strength:.2f} ({direction}) exceeds watch "
            f"margin {settings.watch_threshold - 0.5:.2f} - increasing observation cadence."
        )
    elif state == Severity.ALERT:
        parts.append(
            f"World strength {world.overall_strength:.2f} ({direction}) exceeds alert "
            f"margin {settings.alert_threshold - 0.5:.2f} with confidence "
            f"{world.overall_confidence:.2f} - paging on-call."
        )
    else:
        parts.append(
            f"World strength {world.overall_strength:.2f} ({direction}) exceeds critical "
            f"margin {settings.critical_threshold - 0.5:.2f} - engaging runbook."
        )
    if world.contributing_subjects:
        parts.append("Drivers: " + ", ".join(world.contributing_subjects[:3]))
    return " ".join(parts)


def decide(world: WorldState, now: datetime | None = None) -> Decision:
    settings = get_settings()
    s = world.overall_strength
    c = world.overall_confidence
    distance = abs(s - 0.5)

    # watch_threshold is an absolute strength value; strengths strictly
    # between watch_threshold and 1-watch_threshold (i.e. near 0.5) are
    # considered neutral and never escalate, regardless of confidence.
    elevated_margin = max(0.0, settings.watch_threshold - 0.5)
    depressed_margin = max(0.0, 0.5 - (1.0 - settings.watch_threshold))
    beyond_neutral = distance >= max(elevated_margin, depressed_margin)

    if c < settings.min_confidence_to_act:
        state = Severity.STABLE
    elif (
        distance >= (settings.critical_threshold - 0.5)
        and c >= settings.alert_confidence
    ):
        state = Severity.CRITICAL
    elif (
        distance >= (settings.alert_threshold - 0.5)
        and c >= settings.alert_confidence
    ):
        state = Severity.ALERT
    elif distance > 0.0 and c >= settings.min_confidence_to_act:
        # Any non-zero distance from neutral, with sufficient confidence,
        # warrants at least WATCH. A perfectly neutral world (strength
        # exactly 0.5) stays STABLE regardless of confidence.
        state = Severity.WATCH
    else:
        state = Severity.STABLE

    return Decision(
        state=state,
        action=_SEVERITY_ACTIONS[state],
        rationale=_rationale(world, state, settings),
        risk_score=world.risk_score,
        world_state=world,
        fused_strength=world.overall_strength,
        overall_confidence=world.overall_confidence,
        generated_at=now or _utcnow(),
        created_at=now or _utcnow(),
    )
