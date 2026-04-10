"""
Unit tests for database module — schema, upsert, migration, and pipeline lock.

Run with: python -m pytest tests/test_database.py -v
"""

import os
import sys
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import (
    get_connection,
    init_db,
    insert_videos,
    get_video_count,
    get_distinct_niches,
    is_pipeline_running,
    acquire_pipeline_lock,
    release_pipeline_lock,
    _apply_migrations,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a temporary SQLite file."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("database._get_db_path", lambda: db_path)
    # Clear thread-local cache so each test gets a fresh connection
    import database
    if hasattr(database._thread_local, "connection"):
        del database._thread_local.connection
    init_db()
    yield db_path
    # Clean up thread-local connection
    conn = getattr(database._thread_local, "connection", None)
    if conn:
        conn.close()
        del database._thread_local.connection


def _make_video(**overrides):
    """Create a minimal valid video dict."""
    defaults = {
        "video_id": "test_vid_001",
        "platform": "youtube",
        "niche": "AI for business",
        "title": "Test Video Title",
        "views": 10000,
        "likes": 500,
        "comments": 100,
        "engagement_rate": 0.06,
        "score": 0.75,
        "published_at": "2026-01-01T00:00:00Z",
        "channel": "TestChannel",
        "thumbnail_url": "https://example.com/thumb.jpg",
        "description": "A test video description.",
        "target_audience": "developers",
        "strategic_advice": "1) Tip one. 2) Tip two. 3) Tip three.",
        "content_gap": "Missing topic X.",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Schema & Init
# ---------------------------------------------------------------------------
class TestSchemaInit:
    """Tests for init_db() and schema creation."""

    def test_init_creates_tables(self):
        """init_db() should create videos and pipeline_runs tables."""
        count = get_video_count()
        assert count == 0  # Table exists, empty

    def test_init_idempotent(self):
        """Calling init_db() multiple times should not error."""
        init_db()
        init_db()
        assert get_video_count() == 0


# ---------------------------------------------------------------------------
# Schema Migration
# ---------------------------------------------------------------------------
class TestSchemaMigration:
    """Tests for _apply_migrations() auto-column-addition."""

    def test_adds_missing_columns(self, _use_temp_db):
        """Migration should add columns that don't exist yet."""
        db_path = _use_temp_db
        # Drop a column by recreating table without it
        conn = sqlite3.connect(db_path)
        conn.execute("ALTER TABLE videos RENAME TO videos_old")
        conn.execute("""
            CREATE TABLE videos (
                video_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL DEFAULT 'youtube',
                niche TEXT NOT NULL,
                title TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                engagement_rate REAL NOT NULL DEFAULT 0.0,
                score REAL NOT NULL DEFAULT 0.0,
                published_at TEXT,
                channel TEXT,
                thumbnail_url TEXT,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("DROP TABLE videos_old")
        conn.commit()

        # Verify columns are missing
        cols = {row[1] for row in conn.execute("PRAGMA table_info(videos)").fetchall()}
        assert "target_audience" not in cols
        assert "strategic_advice" not in cols
        assert "content_gap" not in cols

        # Run migration
        _apply_migrations(conn)
        conn.commit()

        # Verify columns were added
        cols = {row[1] for row in conn.execute("PRAGMA table_info(videos)").fetchall()}
        assert "target_audience" in cols
        assert "strategic_advice" in cols
        assert "content_gap" in cols
        conn.close()


# ---------------------------------------------------------------------------
# Upsert Logic
# ---------------------------------------------------------------------------
class TestUpsert:
    """Tests for insert_videos() upsert behavior."""

    def test_insert_single_video(self):
        """A single video should be inserted correctly."""
        video = _make_video()
        count = insert_videos([video])
        assert count == 1
        assert get_video_count() == 1

    def test_upsert_updates_existing(self):
        """Inserting the same video_id should update, not duplicate."""
        v1 = _make_video(views=1000)
        v2 = _make_video(views=5000)  # Same video_id, updated views

        insert_videos([v1])
        insert_videos([v2])

        assert get_video_count() == 1  # Still one row

        with get_connection() as conn:
            row = conn.execute(
                "SELECT views FROM videos WHERE video_id = ?", ("test_vid_001",)
            ).fetchone()
        assert row["views"] == 5000  # Updated, not 1000

    def test_upsert_allows_views_decrease(self):
        """Views should decrease on upsert (reflects YouTube truth)."""
        v1 = _make_video(views=10000)
        v2 = _make_video(views=8000)  # YouTube removed spam views

        insert_videos([v1])
        insert_videos([v2])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT views FROM videos WHERE video_id = ?", ("test_vid_001",)
            ).fetchone()
        assert row["views"] == 8000  # Decreased correctly

    def test_created_at_is_server_time(self):
        """created_at should always be server-generated, not from input."""
        video = _make_video()
        video["created_at"] = "2020-01-01T00:00:00"  # Attacker-supplied value

        insert_videos([video])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT created_at FROM videos WHERE video_id = ?",
                ("test_vid_001",),
            ).fetchone()
        # Should be a recent timestamp, not the injected 2020 date
        assert "2026" in row["created_at"]

    def test_batch_insert(self):
        """Multiple videos should be inserted in a single call."""
        videos = [_make_video(video_id=f"vid_{i}") for i in range(10)]
        count = insert_videos(videos)
        assert count == 10
        assert get_video_count() == 10

    def test_empty_list_returns_zero(self):
        """Inserting an empty list should return 0 without error."""
        assert insert_videos([]) == 0

    def test_distinct_niches(self):
        """get_distinct_niches() should return unique sorted niches."""
        videos = [
            _make_video(video_id="v1", niche="prompt engineering"),
            _make_video(video_id="v2", niche="AI for business"),
            _make_video(video_id="v3", niche="AI for business"),  # Duplicate
        ]
        insert_videos(videos)
        niches = get_distinct_niches()
        assert niches == ["AI for business", "prompt engineering"]


# ---------------------------------------------------------------------------
# Pipeline Lock
# ---------------------------------------------------------------------------
class TestPipelineLock:
    """Tests for database-level pipeline locking."""

    def test_no_running_pipeline(self):
        """When no pipeline is running, is_pipeline_running() returns False."""
        assert is_pipeline_running() is False

    def test_acquire_and_check(self):
        """After acquiring lock, is_pipeline_running() returns True."""
        run_id = acquire_pipeline_lock(triggered_by="test")
        assert is_pipeline_running() is True
        # Clean up
        release_pipeline_lock(run_id, {"status": "completed"})

    def test_release_frees_lock(self):
        """After releasing lock, is_pipeline_running() returns False."""
        run_id = acquire_pipeline_lock(triggered_by="test")
        release_pipeline_lock(run_id, {"status": "completed"})
        assert is_pipeline_running() is False

    def test_double_acquire_raises(self):
        """Acquiring lock twice should raise RuntimeError."""
        run_id = acquire_pipeline_lock(triggered_by="test")
        with pytest.raises(RuntimeError, match="already in progress"):
            acquire_pipeline_lock(triggered_by="test2")
        # Clean up
        release_pipeline_lock(run_id, {"status": "completed"})

    def test_stale_lock_auto_recovery(self):
        """A stale 'running' entry (>30 min) should be auto-recovered."""
        # Insert a fake old running entry
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO pipeline_runs (started_at, status, triggered_by)
                   VALUES (?, 'running', 'test')""",
                (old_time,),
            )

        # Should not see this as running (stale)
        assert is_pipeline_running() is False

        # Should be able to acquire a new lock
        run_id = acquire_pipeline_lock(triggered_by="test_new")
        assert run_id is not None
        release_pipeline_lock(run_id, {"status": "completed"})

    def test_release_records_result(self):
        """release_pipeline_lock should store the result data."""
        run_id = acquire_pipeline_lock(triggered_by="test")
        release_pipeline_lock(run_id, {
            "status": "completed",
            "ingested": 100,
            "processed": 80,
            "enriched": 80,
            "stored": 80,
            "elapsed_seconds": 42.5,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)
            ).fetchone()
        assert row["status"] == "completed"
        assert row["videos_ingested"] == 100
        assert row["elapsed_seconds"] == 42.5
