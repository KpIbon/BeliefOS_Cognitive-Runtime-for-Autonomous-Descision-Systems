# BeliefOS Architecture

> The four-layer model that turns raw signals into evolving
> probabilistic beliefs, a fused world state, and an actionable
> decision.

## Overview

```
                    ┌─────────────────┐
   raw signal  ───▶ │  Observation    │
                    └─────┬───────────┘
                          │  store + apply decay
                          ▼
                    ┌─────────────────┐
                    │     Belief      │  EMA, evidence, trend
                    └─────┬───────────┘
                          │  list of live beliefs
                          ▼
                    ┌─────────────────┐
                    │   WorldState    │  weighted fusion + correlation boost
                    └─────┬───────────┘
                          │  overall strength + confidence
                          ▼
                    ┌─────────────────┐
                    │    Decision     │  stable | watch | alert | critical
                    └─────────────────┘
```

Each layer is a Python module and a SQLAlchemy table; the data
shapes overlap (a Belief becomes a BeliefRow) but the contracts are
clean enough that you can swap any layer without touching the others.

## Observation layer

The lowest layer. An `Observation` is the smallest unit of evidence:

* `subject` — the dimension being measured (e.g. `cpu`, `error_rate`).
* `value` — a normalized strength in `[0.0, 1.0]`.
* `source` — provenance (e.g. `prometheus`, `openai`, `ros2:drone-3`).
* `confidence` — how much the source trusts the value.
* `metadata` — arbitrary context (request id, region, etc.).
* `timestamp` — when the observation occurred.

Observations are **append-only**. They are never mutated and never
deleted (except for full database rollbacks). Trends are reconstructed
by ordering observations by time.

## Belief layer

The continuous memory. A `Belief` is a single subject's evolving
probabilistic view:

* `strength` — exponentially smoothed value in `[0.0, 1.0]`.
* `confidence` — grows with observation count, shrinks under staleness.
* `evidence` — bounded ring buffer of recent observations.
* `trend` — `rising | stable | falling` based on the last delta.
* `last_value`, `last_source` — provenance of the most recent
  observation.

### Update rule

For each new observation:

1. Apply time-based decay to the existing belief (drift toward 0.5).
2. Blend the new value with the existing strength using an EMA:
   `new = α * obs + (1 - α) * old`.
3. Bump `observation_count`, update `evidence` buffer.
4. Compute trend from `new - old`.
5. Update `confidence` based on observation count and observed
   confidence.

The half-life controls how quickly old evidence is forgotten. The
alpha controls how quickly new evidence wins. Both are tunable via
`BELIEFOS_*` environment variables.

## World state layer

The fused view across subjects. A `WorldState` is computed from the
list of live beliefs:

* `overall_strength` — confidence-weighted mean of signed distances
  from neutral (0.5).
* `overall_confidence` — mean confidence scaled by subject breadth.
* `risk_score` — `strength * confidence * (1 + volatility)`.
* `contributing_subjects` — the subjects that drove this snapshot.
* `summary` — a free-form dict of derived metrics.

The fusion rule applies a **correlation boost** when three or more
subjects trend in the same direction. This rewards multi-signal
agreement without requiring correlation tracking.

## Decision layer

The action. A `Decision` is the policy's answer to the current world
state:

* `state` — one of `stable | watch | alert | critical`.
* `action` — a short human-readable string safe to embed in
  notifications, drone control planes, or ROS2 topics.
* `rationale` — a one-sentence explanation of why the policy chose
  this state.
* `recommended_policies` — optional list of runbook IDs to invoke.

The policy is **interpretable and tunable**. All thresholds live in
`beliefos.core.config` and can be overridden via environment
variables.

## Storage

* **PostgreSQL** (or SQLite for development) — durable history of
  observations, beliefs, world state snapshots, and decisions.
* **Redis** (optional) — write-through cache for the latest world
  state and decision. Falls back to an in-process cache when
  `BELIEFOS_REDIS_URL` is unset.

## Concurrency model

The engine is synchronous and uses one transaction per HTTP request.
The API is idempotent for reads. The fusion + decision step is
deterministic given the same belief list, so multiple instances of
the API can be run behind a load balancer without coordination.

When you need higher throughput, the next step is to add a queue
(Redis Streams, Kafka) in front of the engine. The
`engine.observe(observation)` method is already a single unit of
work — it can be called from a worker.

## Extension points

* **Integrations** — `beliefos.integrations.{openai,anthropic,ros2,drones}`
  expose `to_observations(payload) -> Iterable[Observation]` functions
  that turn domain events into beliefs.
* **Custom weights** — `beliefos.fusion.weights.set_weight(subject, weight)`
  overrides the default prior for a single subject.
* **Custom decision policy** — subclass or replace
  `beliefos.decision.policy.decide` to add organization-specific
  escalation rules.
* **Pluggable storage** — swap the `BeliefRepository` for a TimescaleDB
  or InfluxDB-backed implementation if you want per-observation
  retention.

