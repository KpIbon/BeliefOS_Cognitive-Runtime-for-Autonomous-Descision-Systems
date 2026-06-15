"""HTTP routes for v1 of the BeliefOS API.

The surface is intentionally small and stable:

*   ``POST /observe`` — record an observation, returns the updated belief
*   ``GET  /beliefs`` — list all current beliefs
*   ``GET  /world-state`` — fused world state
*   ``GET  /decide`` — current decision

Auxiliary endpoints (``/health``, ``/report``, ``/docs``) are also exposed
for operational visibility.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from beliefos.core.config import get_settings
from beliefos.core.engine import BeliefEngine, get_engine
from beliefos.core.models import (
    Belief,
    Decision,
    Observation,
    ObserveResponse,
    WorldState,
)

router = APIRouter()


def engine_dep() -> BeliefEngine:
    return get_engine()


@router.post("/observe", response_model=ObserveResponse, status_code=status.HTTP_201_CREATED)
def observe(payload: Observation, engine: BeliefEngine = Depends(engine_dep)) -> ObserveResponse:
    """Record an observation and return the updated belief."""

    try:
        belief = engine.observe(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ObserveResponse(observation=payload, belief=belief)


@router.get("/beliefs", response_model=list[Belief])
def list_beliefs(
    subject: str | None = Query(default=None, description="Filter to a single subject"),
    apply_decay: bool = Query(default=True),
    engine: BeliefEngine = Depends(engine_dep),
) -> list[Belief]:
    if subject:
        belief = engine.get_belief(subject)
        return [belief] if belief is not None else []
    return engine.list_beliefs(with_decay=apply_decay)


@router.get("/world-state", response_model=WorldState)
def world_state(engine: BeliefEngine = Depends(engine_dep)) -> WorldState:
    return engine.world_state()


@router.get("/decide", response_model=Decision)
def decide(engine: BeliefEngine = Depends(engine_dep)) -> Decision:
    return engine.decide()


@router.get("/report")
def report(engine: BeliefEngine = Depends(engine_dep)) -> dict:
    return engine.full_report()


@router.get("/health")
def health(engine: BeliefEngine = Depends(engine_dep)) -> dict:
    cache = engine._cache  # noqa: SLF001 — small read for ops
    import beliefos
    return {
        "status": "ok",
        "version": beliefos.__version__,
        "environment": get_settings().environment,
        "cache": type(cache).__name__,
        "cache_alive": bool(cache.ping()),
    }
