"""Repository: read/write domain models to the database."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from beliefos.core.models import (
    Belief,
    Decision,
    Evidence,
    Observation,
    Severity,
    Trend,
    WorldState,
)
from beliefos.storage.orm import (
    BeliefRow,
    DecisionRow,
    ObservationRow,
    WorldStateRow,
)


def _to_evidence_list(rows):
    if not rows:
        return []
    return [Evidence.model_validate(item) for item in rows]


def belief_from_row(row):
    return Belief(
        subject=row.subject,
        strength=row.strength,
        confidence=row.confidence,
        trend=Trend(row.trend),
        observation_count=row.observation_count,
        last_value=row.last_value,
        last_source=row.last_source,
        evidence=_to_evidence_list(row.evidence or []),
        first_seen=row.first_seen,
        last_updated=row.last_updated,
        value=row.last_value,
        observations=row.observation_count,
        # last_observation_at is alias of last_updated on the ORM
        previous_strength=row.previous_strength,

    )


def world_state_from_row(row):
    return WorldState(
        overall_strength=row.strength,
        overall_confidence=row.confidence,
        risk_score=row.risk_score,
        volatility=row.volatility if hasattr(row, "volatility") else 0.0,
        trend=Trend(row.trend) if hasattr(row, "trend") else Trend.STABLE,
        contributing_subjects=list(row.contributing_subjects or []),
        summary=dict(row.summary or {}),
        generated_at=row.created_at,
    )


def decision_from_row(row):
    return Decision(
        state=Severity(row.state),
        action=row.action,
        rationale=row.rationale or "",
        risk_score=row.risk_score,
        created_at=row.created_at,
        generated_at=row.created_at,
    )


class BeliefRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_observation(self, obs: Observation) -> ObservationRow:
        context = obs.context or {}
        source_ref = obs.source_ref or context.get("source_ref")
        row = ObservationRow(
            subject=obs.subject,
            value=obs.value,
            source=obs.source,
            source_ref=source_ref,
            context=context,
            created_at=obs.timestamp,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def recent_observations(self, subject, limit=50):
        stmt = (
            select(ObservationRow)
            .where(ObservationRow.subject == subject)
            .order_by(desc(ObservationRow.created_at))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_belief(self, subject):
        row = self.session.get(BeliefRow, subject)
        return belief_from_row(row) if row else None

    def upsert_belief(self, belief):
        row = self.session.get(BeliefRow, belief.subject)
        if row is None:
            row = BeliefRow(subject=belief.subject)
            self.session.add(row)
        row.strength = belief.strength
        row.confidence = belief.confidence
        row.trend = belief.trend.value
        row.observation_count = belief.observation_count
        row.last_value = belief.last_value
        row.last_source = belief.last_source
        row.evidence = [e.model_dump(mode="json") for e in belief.evidence]
        row.first_seen = belief.first_seen
        row.last_updated = belief.last_updated
        row.previous_strength = belief.previous_strength
        # last_observation_at is alias of last_updated
        self.session.flush()
        return belief_from_row(row)

    def list_beliefs(self):
        stmt = select(BeliefRow).order_by(BeliefRow.subject)
        return [belief_from_row(r) for r in self.session.execute(stmt).scalars().all()]

    def save_world_state(self, state):
        row = WorldStateRow(
            strength=state.overall_strength,
            confidence=state.overall_confidence,
            risk_score=state.risk_score,
            created_at=state.generated_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest_world_state(self):
        stmt = select(WorldStateRow).order_by(desc(WorldStateRow.created_at)).limit(1)
        row = self.session.execute(stmt).scalar_one_or_none()
        return world_state_from_row(row) if row else None

    def save_decision(self, decision, world_snapshot_id=None):
        row = DecisionRow(
            state=decision.state.value,
            action=decision.action,
            rationale=decision.rationale or "",
            risk_score=decision.risk_score,
            world_snapshot_id=world_snapshot_id,
            created_at=decision.created_at or decision.generated_at,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest_decision(self):
        stmt = select(DecisionRow).order_by(desc(DecisionRow.created_at)).limit(1)
        row = self.session.execute(stmt).scalar_one_or_none()
        return decision_from_row(row) if row else None
