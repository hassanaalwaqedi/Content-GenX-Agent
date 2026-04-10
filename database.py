"""
Database module for Content Intelligence Platform.

Manages SQLite connections, schema initialization, and data persistence
with upsert semantics. Uses WAL mode for concurrent read access.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    video_id        TEXT PRIMARY KEY,
    platform        TEXT NOT NULL DEFAULT 'youtube',
    niche           TEXT NOT NULL,
    title           TEXT NOT NULL,
    views           INTEGER NOT NULL DEFAULT 0,
    likes           INTEGER NOT NULL DEFAULT 0,
    comments        INTEGER NOT NULL DEFAULT 0,
    engagement_rate REAL NOT NULL DEFAULT 0.0,
    score           REAL NOT NULL DEFAULT 0.0,
    published_at    TEXT,
    channel         TEXT,
    thumbnail_url   TEXT,
    description     TEXT,
    target_audience TEXT DEFAULT 'Analysis pending',
    strategic_advice TEXT DEFAULT 'Analysis pending',
    content_gap     TEXT DEFAULT 'Analysis pending',
    transcript      TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    status            TEXT NOT NULL DEFAULT 'running',
    videos_ingested   INTEGER DEFAULT 0,
    videos_processed  INTEGER DEFAULT 0,
    videos_enriched   INTEGER DEFAULT 0,
    videos_stored     INTEGER DEFAULT 0,
    elapsed_seconds   REAL,
    error_message     TEXT,
    triggered_by      TEXT DEFAULT 'manual'
);

CREATE INDEX IF NOT EXISTS idx_videos_niche ON videos(niche);
CREATE INDEX IF NOT EXISTS idx_videos_score ON videos(score DESC);
CREATE INDEX IF NOT EXISTS idx_videos_published ON videos(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at DESC);
"""

_UPSERT_SQL = """
INSERT INTO videos (
    video_id, platform, niche, title, views, likes, comments,
    engagement_rate, score, published_at, channel, thumbnail_url,
    description, target_audience, strategic_advice, content_gap,
    transcript, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(video_id) DO UPDATE SET
    views             = excluded.views,
    likes             = excluded.likes,
    comments          = excluded.comments,
    engagement_rate   = excluded.engagement_rate,
    score             = excluded.score,
    channel           = excluded.channel,
    thumbnail_url     = excluded.thumbnail_url,
    description       = excluded.description,
    target_audience   = excluded.target_audience,
    strategic_advice  = excluded.strategic_advice,
    content_gap       = excluded.content_gap,
    transcript        = CASE WHEN excluded.transcript != '' THEN excluded.transcript ELSE videos.transcript END,
    updated_at        = excluded.updated_at;
"""


# ---------------------------------------------------------------------------
# Connection management (thread-local pool)
# ---------------------------------------------------------------------------
_thread_local = threading.local()


def _get_db_path() -> str:
    settings = get_settings()
    return settings.sqlite_db_path


def _get_thread_connection() -> sqlite3.Connection:
    """Return a cached per-thread connection, creating one if needed."""
    conn = getattr(_thread_local, "connection", None)
    if conn is None:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        _thread_local.connection = conn
    return conn


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager that yields a thread-local SQLite connection with
    WAL mode and foreign-key enforcement. Commits on success, rolls back
    on error. Connections are reused within the same thread.
    """
    conn = _get_thread_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------
_COLUMN_MIGRATIONS = [
    # (column_name, full_column_definition)
    # Add new columns here as the schema evolves.
    ("target_audience", "TEXT DEFAULT 'Analysis pending'"),
    ("strategic_advice", "TEXT DEFAULT 'Analysis pending'"),
    ("content_gap", "TEXT DEFAULT 'Analysis pending'"),
    ("transcript", "TEXT DEFAULT ''"),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """
    Introspect the existing schema and add any missing columns.

    This ensures existing databases are upgraded automatically without
    requiring manual ALTER TABLE scripts. Safe to run repeatedly.
    """
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(videos)").fetchall()
    }

    for col_name, col_def in _COLUMN_MIGRATIONS:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_def}")
            logger.info("Migration: added column '%s' to videos table.", col_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create tables, indexes, and apply any pending schema migrations."""
    with get_connection() as conn:
        conn.executescript(_CREATE_TABLE_SQL)
        _apply_migrations(conn)
    logger.info("Database initialized (schema + migrations verified).")


def insert_videos(videos: List[dict]) -> int:
    """
    Upsert a batch of video records. Returns the number of rows affected.

    Each dict in *videos* must contain keys matching the table columns.
    Missing optional fields will be filled with sensible defaults.
    """
    if not videos:
        logger.warning("insert_videos called with empty list — skipping.")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    rows_affected = 0

    with get_connection() as conn:
        for v in videos:
            try:
                conn.execute(
                    _UPSERT_SQL,
                    (
                        v["video_id"],
                        v.get("platform", "youtube"),
                        v["niche"],
                        v["title"],
                        v.get("views", 0),
                        v.get("likes", 0),
                        v.get("comments", 0),
                        v.get("engagement_rate", 0.0),
                        v.get("score", 0.0),
                        v.get("published_at", ""),
                        v.get("channel", ""),
                        v.get("thumbnail_url", ""),
                        v.get("description", ""),
                        v.get("target_audience", "Analysis pending"),
                        v.get("strategic_advice", "Analysis pending"),
                        v.get("content_gap", "Analysis pending"),
                        v.get("transcript", ""),
                        now,  # created_at: always server timestamp
                        now,  # updated_at: always refreshed
                    ),
                )
                rows_affected += 1
            except sqlite3.IntegrityError as exc:
                logger.error("Integrity error for video %s: %s", v.get("video_id"), exc)
            except Exception as exc:
                logger.error(
                    "Unexpected error inserting video %s: %s",
                    v.get("video_id"),
                    exc,
                    exc_info=True,
                )

    logger.info("Upserted %d / %d videos.", rows_affected, len(videos))
    return rows_affected


def get_video_count() -> int:
    """Return total number of videos in the database."""
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM videos;").fetchone()
        return row["cnt"] if row else 0


def get_distinct_niches() -> List[str]:
    """Return a sorted list of distinct niches in the database."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT niche FROM videos ORDER BY niche;"
        ).fetchall()
        return [r["niche"] for r in rows]


# ---------------------------------------------------------------------------
# Pipeline run audit
# ---------------------------------------------------------------------------
def record_pipeline_run(
    result: Dict[str, Any], triggered_by: str = "manual"
) -> int:
    """
    Insert a pipeline run audit record. Returns the auto-generated row ID.

    Called at the end of every pipeline execution to maintain a full
    operational history for observability and debugging.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO pipeline_runs
               (started_at, finished_at, status, videos_ingested,
                videos_processed, videos_enriched, videos_stored,
                elapsed_seconds, error_message, triggered_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.get("started_at"),
                result.get("finished_at"),
                result.get("status", "unknown"),
                result.get("ingested", 0),
                result.get("processed", 0),
                result.get("enriched", 0),
                result.get("stored", 0),
                result.get("elapsed_seconds"),
                result.get("error"),
                triggered_by,
            ),
        )
        run_id = cursor.lastrowid
    logger.info("Pipeline run #%d recorded (status=%s).", run_id, result.get("status"))
    return run_id


def get_pipeline_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent pipeline run records."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, started_at, finished_at, status,
                      videos_ingested, videos_processed, videos_enriched,
                      videos_stored, elapsed_seconds, error_message,
                      triggered_by
               FROM pipeline_runs
               ORDER BY started_at DESC
               LIMIT ?;""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Database-level pipeline lock
# ---------------------------------------------------------------------------
_STALE_RUN_MINUTES: int = 30


def is_pipeline_running() -> bool:
    """
    Check if a pipeline run is currently active in the database.

    A run is considered stale (and ignored) if it has been 'running'
    for more than ``_STALE_RUN_MINUTES`` minutes, which indicates the
    previous process crashed without recording a finish.
    """
    with get_connection() as conn:
        row = conn.execute(
            """SELECT id, started_at FROM pipeline_runs
               WHERE status = 'running'
               ORDER BY started_at DESC LIMIT 1;"""
        ).fetchone()

    if not row:
        return False

    # Check for staleness
    try:
        started = datetime.fromisoformat(row["started_at"])
        elapsed_min = (datetime.now(timezone.utc) - started).total_seconds() / 60
        if elapsed_min > _STALE_RUN_MINUTES:
            logger.warning(
                "Pipeline run #%d has been 'running' for %.0f min -- treating as stale.",
                row["id"],
                elapsed_min,
            )
            # Mark the stale run as crashed
            with get_connection() as conn:
                conn.execute(
                    """UPDATE pipeline_runs SET status = 'crashed',
                       finished_at = ?, error_message = 'Marked stale after timeout'
                       WHERE id = ?""",
                    (datetime.now(timezone.utc).isoformat(), row["id"]),
                )
            return False
    except (ValueError, TypeError):
        pass

    return True


def acquire_pipeline_lock(triggered_by: str = "manual") -> int:
    """
    Create a 'running' pipeline_runs record as a database-level lock.

    Returns the run ID. Raises RuntimeError if a run is already active.
    """
    if is_pipeline_running():
        raise RuntimeError("A pipeline run is already in progress.")

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO pipeline_runs
               (started_at, status, triggered_by)
               VALUES (?, 'running', ?)""",
            (now, triggered_by),
        )
        run_id = cursor.lastrowid
    logger.info("Pipeline lock acquired (run #%d, triggered_by=%s).", run_id, triggered_by)
    return run_id


def release_pipeline_lock(run_id: int, result: Dict[str, Any]) -> None:
    """
    Update the pipeline_runs record to release the lock.

    Records final counts, elapsed time, status, and error (if any).
    """
    with get_connection() as conn:
        conn.execute(
            """UPDATE pipeline_runs SET
                   finished_at = ?,
                   status = ?,
                   videos_ingested = ?,
                   videos_processed = ?,
                   videos_enriched = ?,
                   videos_stored = ?,
                   elapsed_seconds = ?,
                   error_message = ?
               WHERE id = ?""",
            (
                result.get("finished_at"),
                result.get("status", "unknown"),
                result.get("ingested", 0),
                result.get("processed", 0),
                result.get("enriched", 0),
                result.get("stored", 0),
                result.get("elapsed_seconds"),
                result.get("error"),
                run_id,
            ),
        )
    logger.info("Pipeline lock released (run #%d, status=%s).", run_id, result.get("status"))
