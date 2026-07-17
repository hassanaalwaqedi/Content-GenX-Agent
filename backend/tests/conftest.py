from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import database


@pytest.fixture
def isolated_database(monkeypatch, tmp_path):
    """Point database helpers at a fresh SQLite file for each test."""
    previous = getattr(database._thread_local, "connection", None)
    if previous is not None:
        previous.close()
        delattr(database._thread_local, "connection")

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(sqlite_db_path=str(db_path)),
    )
    database.init_db()
    yield db_path

    connection = getattr(database._thread_local, "connection", None)
    if connection is not None:
        connection.close()
        delattr(database._thread_local, "connection")
