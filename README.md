# BeliefOS

> A cognitive runtime for evolving beliefs over time.
 
BeliefOS maintains an evolving, probabilistic view of the world from noisy observations.
Observations arrive → beliefs are updated with confidence tracked separately → a fused
world state is computed → a policy turns that into a decision.

## Why
Raw signals are noisy. A spike is not a crisis. Three correlated spikes are a pattern.
BeliefOS fuses signals, tracks confidence, and only escalates when the world state is
both strong *and* well-supported. The output is a Decision you can route to a human,
a drone, a ROS2 node, or an LLM agent.

## Architecture

```
observations  ─►  Beliefs  ─►  WorldState  ─►  Decision
                  (EMA,           (weighted        (policy:
                  decay,          fusion,          STABLE | WATCH
                  confidence)     correlation)     | ALERT | CRITICAL)
```

Four layers, each pluggable:

- **Observation Layer** — normalized signals from any source (HTTP, ROS2, OpenAI, logs, drones).
- **Belief Layer** — per-subject EMA-smoothed strength, separate confidence, rolling evidence.
- **World State Layer** — confidence-weighted fusion with a multi-signal agreement bonus.
- **Decision Layer** — conservative policy that escalates only on strength *and* confidence.

## Quickstart

```bash
# 1. install (Python 3.12)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. run tests
pytest

# 3. run the API + dashboard
uvicorn beliefos.api.app:create_app --factory --reload
# open http://localhost:8000 for the dashboard
# open http://localhost:8000/docs for the API
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/observe` | record an observation, get the updated belief |
| GET  | `/beliefs` | list all current beliefs |
| GET  | `/world-state` | fused world state |
| GET  | `/decide` | current decision (policy) |
| GET  | `/report` | beliefs + world state + decision in one payload |
| GET  | `/health` | liveness probe |
| GET  | `/` | live dashboard |

### Example

```bash
curl -X POST localhost:8000/observe -H 'content-type: application/json' \
  -d '{"subject":"cpu","value":0.8,"source":"prometheus"}'
curl -X POST localhost:8000/observe -H 'content-type: application/json' \
  -d '{"subject":"error_rate","value":0.95,"source":"sentry"}'
curl localhost:8000/decide
# → {"state":"alert","action":"Page on-call. Capture evidence snapshot.","rationale":"..."}
```

## Python usage

```python
from beliefos import BeliefEngine, Observation

engine = BeliefEngine()
engine.observe(Observation(subject="cpu", value=0.7, source="prom"))
engine.observe(Observation(subject="error_rate", value=0.9, source="sentry"))

print(engine.world_state().overall_strength)  # fused strength in [0, 1]
print(engine.decide().state)                  # one of stable | watch | alert | critical
print(engine.full_report())                   # everything at once
```

## Configuration

All settings are environment variables with the `BELIEFOS_` prefix.

| Variable | Default | Meaning |
|---|---|---|
| `BELIEFOS_DATABASE_URL` | `sqlite:///./beliefos.db` | SQLAlchemy URL. Use `postgresql+psycopg://...` in production. |
| `BELIEFOS_REDIS_URL` | _(unset)_ | Enable Redis cache when set. |
| `BELIEFOS_EMA_ALPHA` | `0.35` | EMA smoothing for belief updates. |
| `BELIEFOS_DECAY_HALF_LIFE_SECONDS` | `300` | Time-based forgetting. |
| `BELIEFOS_WATCH_THRESHOLD` | `0.55` | World strength that escalates to `watch`. |
| `BELIEFOS_ALERT_THRESHOLD` | `0.70` | World strength that escalates to `alert`. |
| `BELIEFOS_CRITICAL_THRESHOLD` | `0.85` | World strength that escalates to `critical`. |
| `BELIEFOS_MIN_CONFIDENCE_TO_ACT` | `0.40` | Below this confidence, hold posture. |
| `BELIEFOS_LOG_LEVEL` | `INFO` | Standard log level. |

## Project layout

```
beliefos/
├── api/                FastAPI app, routes, dependencies
├── core/               domain models, engine, config, update/decay logic
├── decision/           policy → severity mapping
├── dashboard/          HTML/JS dashboard served at GET /
├── fusion/             world-state fusion (weights, correlation)
├── integrations/       OpenAI, Anthropic, ROS2, drone adapters
└── storage/            SQLAlchemy ORM, repository, Redis cache
docker/                 Dockerfile + compose
docs/                   architecture, API, integration guides
examples/               runnable demo scripts
tests/                  pytest suite (in-memory SQLite, hermetic)
```

## Run with Docker

```bash
cd docker
docker compose up --build
# API:    http://localhost:8000
# Docs:   http://localhost:8000/docs
# UI:     http://localhost:8000/
```

PostgreSQL and Redis are wired up in the compose file. Override credentials via `.env` in the same directory.

## Testing

```bash
pip install -e '.[dev]'
pytest -v
```

The test suite is hermetic: each test gets an isolated SQLite file and an in-memory cache. No network or external services required.

## Extending

- **Custom signal weights** — call `beliefos.fusion.weights.set_weight("my_signal", 0.9)`.
- **Custom decision policy** — subclass `DecisionPolicy` and inject it into the engine.
- **Pluggable storage** — implement the `BeliefRepository` interface against your database.
- **Integrations** — see `beliefos/integrations/` for OpenAI, Anthropic, ROS2, and drone adapters.

## License

MIT

## Operat

## Oper

## Operations

### Health



## Operations

### Health

```bash
curl localhost:8000/health
# {"status":"ok","version":"0.1.0","environment":"development","cache":"InProcessCache","cache_alive":true}
```

### Configuration

All settings come from environment variables prefixed `BELIEFOS_`:

| Variable | Default | Description |
|---|---|---|
| `BELIEFOS_DATABASE_URL` | `sqlite:///./beliefos.db` | SQLAlchemy URL. Use `postgresql+psycopg://...` in production. |
| `BELIEFOS_REDIS_URL` | _(unset)_ | Optional. If set, enables the Redis cache layer. |
| `BELIEFOS_EMA_ALPHA` | `0.35` | EMA smoothing factor for belief strength. |
| `BELIEFOS_DECAY_HALF_LIFE_SECONDS` | `300.0` | Time-based forgetting half-life. |
| `BELIEFOS_WATCH_THRESHOLD` | `0.45` | Distance from 0.5 that triggers WATCH. |
| `BELIEFOS_ALERT_THRESHOLD` | `0.65` | Distance from 0.5 that triggers ALERT. |
| `BELIEFOS_CRITICAL_THRESHOLD` | `0.82` | Distance from 0.5 that triggers CRITICAL. |
| `BELIEFOS_ALERT_CONFIDENCE` | `0.5` | Minimum confidence required for ALERT/CRITICAL. |
| `BELIEFOS_MIN_CONFIDENCE_TO_ACT` | `0.4` | Below this we hold posture. |
| `BELIEFOS_ENABLE_DASHBOARD` | `true` | Serve the dashboard at `/`. |

### Logs

Structured JSON logs are written to stdout. In production, pipe to your
log shipper (Loki, CloudWatch, Datadog) and key off the `module` and
`event` fields.

## Design choices

- **EMA, not Bayesian** — interpretable, fast, single parameter. Swappable
  later (the `update` rule is a function, not a method).
- **Confidence separate from strength** — a belief of 0.9 after one
  observation is not the same as 0.9 after fifty. Confidence lets the
  decision layer distinguish "high, uncertain" from "high, well-supported".
- **Correlation boost** — a single high signal can be noise; three
  correlated high signals is a pattern. The boost rewards multi-signal
  agreement.
- **Pluggable storage** — SQLite is the dev/test default; PostgreSQL in
  production; the engine does not care which one is connected.

## Extending

### Custom signal weights

```python
from beliefos.fusion.weights import set_weight
set_weight("my_custom_signal", 0.85)
```

### Custom update rules

Implement the same shape as `record_observation` in
`beliefos/core/update.py` and inject it into the engine. The interface
is a function: `(Belief, Observation, weight) -> Belief`.

### Add an integration

The `beliefos.integrations` package is the right place to add adapters
for OpenAI, Anthropic, ROS2, or drone control planes. Each adapter
should expose a `to_observations(payload) -> Iterable[Observation]`
function and (where applicable) a `decision_to_action(Decision)` mapping.

## License

MIT

### Backups

PostgreSQL is the source of truth. Take a