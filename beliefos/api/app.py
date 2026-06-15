"""FastAPI application factory.

The factory pattern keeps the app importable for tests without side effects
and lets us mount the same routes in a worker process if we ever need to.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from beliefos.api.v1.routes import router as v1_router
from beliefos.core.config import get_settings
from beliefos.core.engine import get_engine
from beliefos.dashboard.routes import router as dashboard_router
from beliefos.storage.database import init_db


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # init_db is best-effort: on serverless (Vercel) we may have no Postgres
    # configured, in which case the engine falls back to in-memory storage.
    try:
        init_db()
    except Exception:  # noqa: BLE001
        pass
    get_engine()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="BeliefOS",
        version="0.1.0",
        description=(
            "A cognitive runtime that maintains evolving beliefs over time from "
            "observations. POST /observe to record, GET /beliefs, /world-state, "
            "/decide to query the running state."
        ),
        lifespan=_lifespan,
    )

    # Permissive CORS for the dashboard; tighten in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/v1")
    app.include_router(v1_router, prefix="")  # bare /observe, /beliefs, etc.
    app.include_router(dashboard_router)
    return app


app = create_app()
