"""Domain models.

The four core objects are expressed as Pydantic models so they can be
serialized across the API, persisted via SQLAlchemy, and reused by future
integrations (OpenAI tool calls, ROS2 messages, drone control planes).

The model layer is intentionally framework-free — it has no dependency on
FastAPI, SQLAlchemy, or the storage layer. That keeps it portable and easy
to reason about in isolation.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Trend(str, Enum):
    """Direction a belief is moving over recent observations."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"

    @classmethod
    def from_delta(cls, delta: float, eps: float = 0.02) -> "Trend":
        if delta > eps:
            return cls.RISING
        if delta < -eps:
            return cls.FALLING
        return cls.STABLE


class Severity(str, Enum):
    STABLE = "stable"
    WATCH = "watch"
    ALERT = "alert"
    CRITICAL = "critical"


# --- Observation Layer ---------------------------------------------------- #


class Observation(BaseModel):
    """A single piece of evidence arriving from the outside world.

    ``value`` is a normalized strength in [0.0, 1.0] where 0.0 is "no signal"
    and 1.0 is "fully on". ``source`` describes where the observation came
    from (e.g. ``"prometheus"``, ``"openai"``, ``"ros2:drone-3"``) so we can
    reason about provenance.
    """

    id: str = Field(default_factory=_new_id)
    subject: str = Field(..., min_length=1, max_length=128)
    value: float = Field(..., ge=0.0, le=1.0)
    source: str = Field(default="default", max_length=64)
    source_ref: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    context: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    metadata: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)

    @field_validator("subject")
    @classmethod
    def _normalize_subject(cls, v: str) -> str:
        return v.strip().lower()


# --- Belief Layer --------------------------------------------------------- #


class Evidence(BaseModel):
    """A retained piece of evidence supporting (or refuting) a belief."""

    observation_id: str
    value: float = Field(..., ge=0.0, le=1.0)
    source: str
    weight: float = Field(..., ge=0.0)
    timestamp: datetime = Field(default_factory=_utcnow)


class Belief(BaseModel):
    """A continuously-updated probabilistic view of one subject.

    The naming is symmetric across the layers: ``strength``, ``value``,
    ``confidence``, ``observation_count``, and ``observations`` are all
    accepted (and normalized) so callers can use whichever feels natural
    for their domain. The canonical names are ``strength`` and
    ``observation_count``; the others are kept as legacy aliases.
    """

    subject: str
    # --- canonical fields -----------------------------------------------
    strength: float = 0.0
    confidence: float = 0.0
    observation_count: int = 0
    last_value: float | None = None
    last_source: str | None = None
    trend: Trend = Trend.STABLE
    evidence: list[Evidence] = Field(default_factory=list)
    first_seen: datetime = Field(default_factory=_utcnow)
    last_updated: datetime = Field(default_factory=_utcnow)
    previous_strength: float = 0.0
    last_observation_at: datetime | None = None
    version: int = 0
    updated_at: datetime = Field(default_factory=_utcnow)
    # --- legacy aliases (sync'd via model_validator) --------------------
    value: float | None = None
    observations: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _sync_aliases(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("value") is not None and "strength" not in data:
            data["strength"] = data["value"]
        if "last_value" not in data and data.get("value") is not None:
            data["last_value"] = data["value"]
        if data.get("observations") is not None and "observation_count" not in data:
            data["observation_count"] = data["observations"]
        return data

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def clamped(self) -> "Belief":
        return self.model_copy(
            update={
                "strength": _clip01(self.strength),
                "confidence": _clip01(self.confidence),
            }
        )


def _clip01(x: float) -> float:
    if math.isnan(x):
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


# --- World State Layer ---------------------------------------------------- #


class WorldState(BaseModel):
    """A snapshot of the fused belief state at a point in time.

    The naming uses ``overall_strength`` / ``overall_confidence`` /
    ``volatility`` as the canonical field set, with ``fused_strength``,
    ``fused_confidence``, ``strength``, and ``confidence`` exposed as
    read-only aliases so older callers and future API responses can use
    either form without breakage.
    """

    overall_strength: float = 0.5
    overall_confidence: float = 0.0
    risk_score: float = 0.0
    volatility: float = 0.0
    trend: Trend = Trend.STABLE
    contributing_subjects: list[str] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    beliefs: dict[str, "Belief"] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_fields(cls, data):
        if isinstance(data, dict):
            if "fused_strength" in data and "overall_strength" not in data:
                data["overall_strength"] = data.pop("fused_strength")
            if "fused_confidence" in data and "overall_confidence" not in data:
                data["overall_confidence"] = data.pop("fused_confidence")
            if "strength" in data and "overall_strength" not in data:
                data["overall_strength"] = data["strength"]
            if "confidence" in data and "overall_confidence" not in data:
                data["overall_confidence"] = data["confidence"]
        return data

    @property
    def fused_strength(self) -> float:
        return self.overall_strength

    @property
    def fused_confidence(self) -> float:
        return self.overall_confidence

    @property
    def strength(self) -> float:
        return self.overall_strength

    @property
    def confidence(self) -> float:
        return self.overall_confidence

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# --- Decision Layer -------------------------------------------------------- #


class Decision(BaseModel):
    """A policy-derived recommendation.

    ``state`` is one of ``stable | watch | alert | critical``. ``action`` is
    a short human-readable string safe to embed in notifications, drone
    control planes, or ROS2 topics. ``rationale`` explains why the
    decision was made so the dashboard and on-call can read it at a glance.
    """

    state: Severity = Severity.STABLE
    action: str = "Hold posture. Continue routine observation."
    rationale: str = ""
    recommended_policies: list[str] = Field(default_factory=list)
    risk_score: float = 0.0
    world_state: WorldState | None = None
    fused_strength: float | None = None
    overall_confidence: float | None = None
    generated_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_fields(cls, data):
        if isinstance(data, dict):
            if "fused_strength" in data and data.get("fused_strength") is not None:
                data.setdefault("overall_confidence", data.get("overall_confidence"))
        return data

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# --- API DTOs ------------------------------------------------------------- #


class ObserveRequest(BaseModel):
    subject: str
    value: float = Field(..., ge=0.0, le=1.0)
    source: str = "default"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObserveResponse(BaseModel):
    observation: Observation
    belief: Belief


class BeliefListResponse(BaseModel):
    beliefs: list[Belief]
    count: int


class DecideRequest(BaseModel):
    include_world_state: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    environment: str
    storage: str
    cache: str
