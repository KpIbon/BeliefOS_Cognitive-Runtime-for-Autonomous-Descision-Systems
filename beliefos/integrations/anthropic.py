"""Anthropic integration.

Maps Claude responses into observations. The mapping mirrors ``openai.py``:
the goal is to keep the integrations symmetric so future code can route any
model through the same belief pipeline.
"""
from __future__ import annotations

from typing import Any, Iterable

from beliefos.core.engine import BeliefEngine
from beliefos.core.models import Observation


def observation_from_response(
    response: Any,
    *,
    subject: str = "anthropic.tool_success",
) -> Observation:
    stop_reason = getattr(response, "stop_reason", None)
    success = stop_reason not in {"error", "refusal"}
    return Observation(
        subject=subject,
        value=0.7 if success else 0.3,
        source="anthropic",
        note=str(stop_reason or ""),
    )


def feed_response(
    engine: BeliefEngine, response: Any, *, subject: str | None = None
) -> None:
    engine.observe(observation_from_response(response, subject=subject or "anthropic.tool_success"))


def feed_batch(
    engine: BeliefEngine, responses: Iterable[Any], *, subject: str | None = None
) -> None:
    for r in responses:
        feed_response(engine, r, subject=subject)
