"""SQLAlchemy engine + session factory.

The default URL points at SQLite. Production sets ``BELIEFOS_DATABASE_URL`` to
a PostgreSQL DSN (e.g. ``postgresql+psycopg://user:pass@host:5432/beliefos``)
and everything else keeps working.

The engine is rebuilt on demand so tests can swap the URL between cases
without leaking connections.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from beliefos.core.config import get_settings


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    connect_args: dict = {}
    engine_kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if ":memory:" in url or url.endswith(":memory:"):
            # In-memory SQLite: each connection would otherwise get its own
            # private database. StaticPool pins a single shared connection
            # so the schema created at init_db is visible to every session.
            from sqlalchemy.pool import StaticPool

            engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = connect_args
    return create_engine(url, **engine_kwargs)


def get_engine() -> Engine:
    """Lazily build (or rebuild) the engine, picking up current settings."""
    global _engine, _SessionLocal
    settings = get_settings()
    if _engine is None or str(_engine.url) != settings.database_url:
        _engine = _build_engine()
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engine() -> None:
    """Discard the cached engine/sessionmaker. Used by tests."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped session."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for scripts and tests."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Safe to call on an empty database."""
    from beliefos.storage.orm import Base  # local import to avoid cycle

    Base.metadata.create_all(bind=get_engine())


def drop_db() -> None:
    """Drop all tables. Used by tests."""
    from beliefos.storage.orm import Base

    Base.metadata.drop_all(bind=get_engine())
    reset_engine()
