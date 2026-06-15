"""ORM models for Observation, Belief, WorldStateSnapshot, Decision.

The schema is intentionally simple: each row captures a moment in time, so
trends can be reconstructed with ``ORDER BY created_at``. We avoid storing
unbounded ``evidence`` blobs; large evidence should be offloaded to object
storage and referenced by URL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ObservationRow(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="api")
    source_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class BeliefRow(Base):
    __tablename__ = "beliefs"

    subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trend: Mapped[str] = mapped_column(String(16), nullable=False, default="stable")
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    previous_strength: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )


class WorldStateRow(Base):
    __tablename__ = "world_state_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[str] = mapped_column(String(16), nullable=False, default="stable")
    summary: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    world_snapshot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("world_state_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
