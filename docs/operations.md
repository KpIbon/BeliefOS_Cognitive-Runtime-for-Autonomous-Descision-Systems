# Operations

Production deployment guide for BeliefOS.

## Architecture in production

```
        ┌─────────────┐    ┌─────────────┐
        │  PostgreSQL │    │    Redis    │
        │  (asyncpg)  │    │  (cache +   │
        │             │    │   pub/sub)  │
        └──────▲──────┘    └──────▲──────┘
               │                  │
        ┌──────┴──────────────────┴──────┐
        │           BeliefOS            │
        │   FastAPI + Uvicorn workers   │
        │   (Observation → Belief →     │
        │    WorldState → Decision)     │
        └──────────────┬────────────────┘
                       │  HTTPS / WS
                       ▼
        ┌────────────────────────────────┐
        │  Dashboard · LLMs · ROS2 ·     │
        │  Drone control plane · Alerts  │
        └────────────────────────────────┘
```

## Containers

The repo ships a multi-stage `Dockerfile` and a `docker-compose.yml`
with three services:

- `postgres` — durable belief store, history, and world-state snapshots.
- `redis` — last-N belief cache and pub/sub fanout for live dashboards.
- `api` — the BeliefOS FastAPI app, wired to the two stores.

Bring everything up:

```bash
docker compose up -d
docker compose logs -f api
```

## Configuration

All settings come from environment variables (or a `.env` file at
startup). See [`.env.example`](../.env.example) for the full list. The
key knobs:

| Var | Purpose | Default |
|---|---|---|
| `BELIEFOS_DATABASE_URL` | asyncpg DSN | `postgresql+asyncpg://beliefos:beliefos@localhost:5432/beliefos` |
| `BELIEFOS_REDIS_URL` | redis URL | `redis://localhost:6379/0` |
| `BELIEFOS_DEFAULT_EMA_WEIGHT` | per-signal pull weight | `0.30` |
| `BELIEFOS_DECAY_HALF_LIFE_SECONDS` | time-based forgetting | `3600` |
| `BELIEFOS_WATCH_THRESHOLD` | min distance from 0.5 to enter WATCH | `0.45` |
| `BELIEFOS_ALERT_THRESHOLD` | distance for ALERT | `0.65` |
| `BELIEFOS_CRITICAL_THRESHOLD` | distance for CRITICAL | `0.82` |

## Migrations

Schema is created on first boot via the SQLAlchemy metadata in
`beliefos/storage/database.py`. For production, generate an Alembic
migration before the first deploy:

```bash
alembic init beliefos/migrations
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

## Observability

- Logs: structured JSON to stdout. Loki tail in `/dev/shm/`.
- Metrics: standard `/metrics` endpoint can be added via `prometheus-fastapi-instrumentator`.
- Tracing: FastAPI middleware ready — drop in OpenTelemetry by adding
  `OpenTelemetryMiddleware` to `beliefos/api/app.py`.

## Scaling

- Stateless API: scale horizontally behind a load balancer. The engine
  is per-request; the storage layer is the only shared state.
- Read scaling: Redis cache absorbs most of the dashboard traffic.
  Snapshot the world state into Redis every N seconds for read-heavy
  fleets.
- Write scaling: PostgreSQL handles thousands of observations per
  second on modest hardware; partition the `belief` table on `subject`
  if you have many distinct subjects.
