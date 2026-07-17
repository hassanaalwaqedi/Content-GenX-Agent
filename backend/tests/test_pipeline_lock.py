from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from core import database


@pytest.fixture
def isolated_database(monkeypatch, tmp_path):
    previous = getattr(database._thread_local, "connection", None)
    if previous is not None:
        previous.close()
        delattr(database._thread_local, "connection")

    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(sqlite_db_path=str(tmp_path / "test.db")),
    )
    database.init_db()
    yield

    connection = getattr(database._thread_local, "connection", None)
    if connection is not None:
        connection.close()
        delattr(database._thread_local, "connection")


def test_pipeline_lock_prevents_a_second_active_run(isolated_database) -> None:
    run_id = database.acquire_pipeline_lock(triggered_by="test")

    with pytest.raises(RuntimeError, match="already in progress"):
        database.acquire_pipeline_lock(triggered_by="test")

    database.release_pipeline_lock(run_id, {"status": "completed"})


def test_reserved_lock_snapshot_can_be_completed_by_the_worker(isolated_database) -> None:
    run_id = database.acquire_pipeline_lock(triggered_by="api", config_snapshot={"config_id": 7})
    database.update_pipeline_run_snapshot(
        run_id,
        {
            "config_id": 7,
            "regions": ["US"],
            "categories": ["technology"],
            "keywords": ["ai"],
            "sources": ["reddit"],
            "content_type": "all",
            "dataset_label": "US · Reddit",
        },
    )

    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT config_regions, config_sources, dataset_label FROM pipeline_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

    assert row["config_regions"] == '["US"]'
    assert row["config_sources"] == '["reddit"]'
    assert row["dataset_label"] == "US · Reddit"
    database.release_pipeline_lock(run_id, {"status": "completed"})


def test_pipeline_lock_is_atomic_across_threads(isolated_database) -> None:
    barrier = threading.Barrier(2)
    acquired: list[int] = []
    errors: list[Exception] = []

    def attempt_lock() -> None:
        try:
            barrier.wait()
            acquired.append(database.acquire_pipeline_lock(triggered_by="test"))
        except Exception as exc:  # Intentional: assert the losing lock attempt below.
            errors.append(exc)
        finally:
            connection = getattr(database._thread_local, "connection", None)
            if connection is not None:
                connection.close()
                delattr(database._thread_local, "connection")

    threads = [threading.Thread(target=attempt_lock) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(acquired) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)

    database.release_pipeline_lock(acquired[0], {"status": "completed"})
