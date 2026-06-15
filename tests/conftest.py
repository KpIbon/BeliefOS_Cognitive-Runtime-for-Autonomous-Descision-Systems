"""Pytest configuration: isolated SQLite file per test, in-memory cache, fresh app."""

from __future__ import annotations

import os
import tempfile

# Configure env BEFORE importing the app, so settings pick them up.
os.environ.setdefault("BELIEFOS_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("BELIEFOS_ENABLE_DASHBOARD", "false")


def _reset_all() -> None:
    from beliefos.core.config import get_settings
    from beliefos.core.engine import reset_engine_for_tests
    from beliefos.storage.database import reset_engine

    get_settings.cache_clear()
    reset_engine_for_tests()
    reset_engine()


def _isolated_db() -> str:
    """Return a unique SQLite file path and create a fresh schema."""
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    os.environ["BELIEFOS_DATABASE_URL"] = f"sqlite:///{db_path}"
    _reset_all()
    from beliefos.storage.database import init_db

    init_db()
    return db_path


import pytest
from fastapi.testclient import TestClient

from beliefos.api.app import create_app
from beliefos.core.engine import get_engine


@pytest.fixture()
def engine():
    db_path = _isolated_db()
    yield get_engine()
    _reset_all()
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture()
def client():
    db_path = _isolated_db()
    app = create_app()
    with TestClient(app) as c:
        yield c
    _reset_all()
    try:
        os.unlink(db_path)
    except OSError:
        pass
