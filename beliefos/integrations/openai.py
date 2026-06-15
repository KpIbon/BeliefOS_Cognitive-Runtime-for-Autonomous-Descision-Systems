"""OpenAI integration.

Maps model confidence / tool-call success into observations. This module
does not import ``openai`` at import time; it requires it lazily.
"""
from __future__ import annotations

from typing import Any, Iterable

from beliefos.core.engine import BeliefEngine
from beliefos.core.models import Observation


def observation_from_response(
    response: Any,
    *,
    subject: str = "openai.tool_success",
) -> Observation:
    """Build a belief-worthy observation from a model response.

    Heuristic:
    * truncated (finish_reason == "length") → low confidence in result (value 0.3)
    * error / refusal → low confidence (value 0.3)
    * normal completion → moderate confidence (value 0.7)
    """
    success = True
    note = ""
    if hasattr(response, "choices") and response.choices:
        first = response.choices[0]
        finish = getattr(first, "finish_reason", None)
        if finish in {"error", "refusal"}:
            success = False
        if finish == "length":  # truncated
            success = False
            note = "truncated"
        if hasattr(first, "message") and getattr(first.message, "refusal", None):
            success = False
            note = "refusal"
    return Observation(
        subject=subject,
        value=0.7 if success else 0.3,
        source="openai",
        note=note,
    )


def feed_response(
    engine: BeliefEngine, response: Any, *, subject: str | None = None
) -> None:
    engine.observe(observation_from_response(response, subject=subject or "openai.tool_success"))


def feed_batch(
    engine: BeliefEngine, responses: Iterable[Any], *, subject: str | None = None
) -> None:
    for r in responses:
        feed_response(engine, r, subject=subject)
