# Quickstart

Get BeliefOS running locally in under five minutes.

## 1. Install

```bash
git clone https://github.com/beliefos/beliefos.git
cd beliefos
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The package targets Python 3.12+ and has no required third-party
dependencies beyond what the API/CLI entry points need (FastAPI, Uvicorn,
Pydantic, asyncpg, redis-py). The core engine itself is pure Python.

## 2. Run the API

```bash
# In-process (no DB / no Redis — falls back to memory)
uvicorn beliefos.api.app:app --reload --port 8000

# With Postgres + Redis via docker compose
docker compose up -d postgres redis
cp .env.example .env
uvicorn beliefos.api.app:app --reload --port 8000
```

Open <http://localhost:8000/> for the dashboard and <http://localhost:8000/docs>
for the auto-generated OpenAPI explorer.

## 3. Send your first observation

```bash
curl -X POST http://localhost:8000/v1/observe \
  -H 'content-type: application/json' \
  -d '{"subject": "cpu_spike", "value": 0.7, "source": "manual"}'
```

Then:

```bash
curl http://localhost:8000/v1/beliefs
curl http://localhost:8000/v1/world-state
curl http://localhost:8000/v1/decide
```

## 4. Run the example

```bash
python examples/basic_loop.py
```

This streams a few synthetic signals into the engine and prints the
resulting decision.

## 5. Run the tests

```bash
pytest
# or with coverage
pytest --cov=beliefos --cov-report=term-missing
```

The suite includes unit tests for the core engine, fusion, decision
policy, and integration tests for the FastAPI surface.
