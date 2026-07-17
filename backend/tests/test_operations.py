from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.versioning import V1PathPrefixMiddleware
from core.backup import create_database_backup, prune_database_backups
from core.logging import JsonFormatter


def test_versioned_api_prefix_reuses_current_routes() -> None:
    app = FastAPI()
    app.add_middleware(V1PathPrefixMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    response = TestClient(app).get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_json_formatter_includes_request_context() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "request_complete", (), None)
    record.request_id = "request-123"
    record.status_code = 200

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "request_complete"
    assert payload["request_id"] == "request-123"
    assert payload["status_code"] == 200


def test_sqlite_backup_is_queryable_and_prunes_expired_snapshots(isolated_database, tmp_path) -> None:
    backup = create_database_backup(source_path=isolated_database, output_dir=tmp_path / "backups")
    with sqlite3.connect(backup) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'videos'").fetchone()[0] == "videos"

    expired = backup.parent / f"{isolated_database.stem}-expired.sqlite3"
    expired.write_bytes(b"old")
    old_timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    os.utime(expired, (old_timestamp, old_timestamp))

    assert prune_database_backups(
        source_path=isolated_database,
        output_dir=backup.parent,
        retention_days=1,
    ) == 1
    assert not expired.exists()
