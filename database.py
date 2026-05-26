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
    topics          TEXT DEFAULT '',
    source_region   TEXT DEFAULT '',
    content_type    TEXT DEFAULT 'all',
    pipeline_run_id INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    status              TEXT NOT NULL DEFAULT 'running',
    videos_ingested     INTEGER DEFAULT 0,
    videos_processed    INTEGER DEFAULT 0,
    videos_enriched     INTEGER DEFAULT 0,
    videos_stored       INTEGER DEFAULT 0,
    elapsed_seconds     REAL,
    error_message       TEXT,
    triggered_by        TEXT DEFAULT 'manual',
    config_regions      TEXT DEFAULT '[]',
    config_categories   TEXT DEFAULT '[]',
    config_keywords     TEXT DEFAULT '[]',
    config_sources      TEXT DEFAULT '["youtube"]',
    config_content_type TEXT DEFAULT 'all',
    dataset_label       TEXT DEFAULT '',
    is_active_dataset   INTEGER DEFAULT 0,
    config_id           INTEGER
);

CREATE INDEX IF NOT EXISTS idx_videos_niche ON videos(niche);
CREATE INDEX IF NOT EXISTS idx_videos_score ON videos(score DESC);
CREATE INDEX IF NOT EXISTS idx_videos_published ON videos(published_at DESC);
CREATE TABLE IF NOT EXISTS pipeline_configs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL DEFAULT 'Custom',
    regions       TEXT NOT NULL DEFAULT '[]',
    platforms     TEXT NOT NULL DEFAULT '["youtube"]',
    categories    TEXT NOT NULL DEFAULT '[]',
    keywords      TEXT NOT NULL DEFAULT '[]',
    content_type  TEXT NOT NULL DEFAULT 'all',
    is_preset     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_configs_preset ON pipeline_configs(is_preset);
"""

# Migration: add columns to existing databases
_MIGRATION_SQL = """
ALTER TABLE videos ADD COLUMN source_region TEXT DEFAULT '';
ALTER TABLE videos ADD COLUMN content_type TEXT DEFAULT 'all';
"""

_UPSERT_SQL = """
INSERT INTO videos (
    video_id, platform, niche, title, views, likes, comments,
    engagement_rate, score, published_at, channel, thumbnail_url,
    description, target_audience, strategic_advice, content_gap,
    transcript, topics, source_region, content_type, pipeline_run_id,
    hashtags, audio_name, hook_text, hook_category,
    trend_velocity, virality_score, shares, saves,
    author_followers, source_url, raw_payload,
    relevance_score, matched_keywords, matched_hashtags, match_reason,
    created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    topics            = CASE WHEN excluded.topics != '' THEN excluded.topics ELSE videos.topics END,
    source_region     = CASE WHEN excluded.source_region != '' THEN excluded.source_region ELSE videos.source_region END,
    content_type      = CASE WHEN excluded.content_type != 'all' THEN excluded.content_type ELSE videos.content_type END,
    pipeline_run_id   = excluded.pipeline_run_id,
    hashtags          = CASE WHEN excluded.hashtags != '' THEN excluded.hashtags ELSE videos.hashtags END,
    audio_name        = CASE WHEN excluded.audio_name != '' THEN excluded.audio_name ELSE videos.audio_name END,
    hook_text         = CASE WHEN excluded.hook_text != '' THEN excluded.hook_text ELSE videos.hook_text END,
    hook_category     = CASE WHEN excluded.hook_category != '' THEN excluded.hook_category ELSE videos.hook_category END,
    trend_velocity    = CASE WHEN excluded.trend_velocity > 0 THEN excluded.trend_velocity ELSE videos.trend_velocity END,
    virality_score    = CASE WHEN excluded.virality_score > 0 THEN excluded.virality_score ELSE videos.virality_score END,
    shares            = excluded.shares,
    saves             = excluded.saves,
    author_followers  = CASE WHEN excluded.author_followers > 0 THEN excluded.author_followers ELSE videos.author_followers END,
    source_url        = CASE WHEN excluded.source_url != '' THEN excluded.source_url ELSE videos.source_url END,
    raw_payload       = CASE WHEN excluded.raw_payload != '' THEN excluded.raw_payload ELSE videos.raw_payload END,
    relevance_score   = CASE WHEN excluded.relevance_score > 0 THEN excluded.relevance_score ELSE videos.relevance_score END,
    matched_keywords  = CASE WHEN excluded.matched_keywords != '' THEN excluded.matched_keywords ELSE videos.matched_keywords END,
    matched_hashtags  = CASE WHEN excluded.matched_hashtags != '' THEN excluded.matched_hashtags ELSE videos.matched_hashtags END,
    match_reason      = CASE WHEN excluded.match_reason != '' THEN excluded.match_reason ELSE videos.match_reason END,
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
    ("target_audience", "TEXT DEFAULT 'Analysis pending'"),
    ("strategic_advice", "TEXT DEFAULT 'Analysis pending'"),
    ("content_gap", "TEXT DEFAULT 'Analysis pending'"),
    ("transcript", "TEXT DEFAULT ''"),
    ("topics", "TEXT DEFAULT ''"),
    ("source_region", "TEXT DEFAULT ''"),
    ("content_type", "TEXT DEFAULT 'all'"),
    ("pipeline_run_id", "INTEGER"),
    # ---- Connector Architecture additions ----
    ("hashtags", "TEXT DEFAULT ''"),
    ("audio_name", "TEXT DEFAULT ''"),
    ("hook_text", "TEXT DEFAULT ''"),
    ("hook_category", "TEXT DEFAULT ''"),
    ("trend_velocity", "REAL DEFAULT 0.0"),
    ("virality_score", "REAL DEFAULT 0.0"),
    ("shares", "INTEGER DEFAULT 0"),
    ("saves", "INTEGER DEFAULT 0"),
    ("author_followers", "INTEGER DEFAULT 0"),
    ("source_url", "TEXT DEFAULT ''"),
    ("raw_payload", "TEXT DEFAULT ''"),
    # ---- Relevance Intelligence additions ----
    ("relevance_score", "REAL DEFAULT 0.0"),
    ("matched_keywords", "TEXT DEFAULT ''"),
    ("matched_hashtags", "TEXT DEFAULT ''"),
    ("match_reason", "TEXT DEFAULT ''"),
]

# Migrations for pipeline_runs table
_PIPELINE_RUNS_MIGRATIONS = [
    ("config_regions", "TEXT DEFAULT '[]'"),
    ("config_categories", "TEXT DEFAULT '[]'"),
    ("config_keywords", "TEXT DEFAULT '[]'"),
    ("config_sources", "TEXT DEFAULT '[\"youtube\"]'"),
    ("config_content_type", "TEXT DEFAULT 'all'"),
    ("dataset_label", "TEXT DEFAULT ''"),
    ("is_active_dataset", "INTEGER DEFAULT 0"),
    ("config_id", "INTEGER"),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """
    Introspect the existing schema and add any missing columns.

    This ensures existing databases are upgraded automatically without
    requiring manual ALTER TABLE scripts. Safe to run repeatedly.
    """
    # Videos table migrations
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(videos)").fetchall()
    }
    for col_name, col_def in _COLUMN_MIGRATIONS:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col_name} {col_def}")
            logger.info("Migration: added column '%s' to videos table.", col_name)

    # Pipeline_runs table migrations
    existing_pr_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()
    }
    for col_name, col_def in _PIPELINE_RUNS_MIGRATIONS:
        if col_name not in existing_pr_cols:
            conn.execute(f"ALTER TABLE pipeline_runs ADD COLUMN {col_name} {col_def}")
            logger.info("Migration: added column '%s' to pipeline_runs table.", col_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _cleanup_stale_pipeline_locks(conn: sqlite3.Connection) -> None:
    """
    Mark any 'running' pipeline records older than the stale threshold as
    'crashed'. This ensures a previous process crash never permanently
    blocks future pipeline runs.
    """
    cursor = conn.execute(
        """UPDATE pipeline_runs
           SET status = 'crashed',
               finished_at = ?,
               error_message = 'Auto-cleaned: stale lock on startup'
           WHERE status = 'running'
             AND started_at < datetime('now', ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            f"-{_STALE_RUN_MINUTES} minutes",
        ),
    )
    if cursor.rowcount > 0:
        logger.warning(
            "Cleaned up %d stale 'running' pipeline lock(s) on startup.",
            cursor.rowcount,
        )


def init_db() -> None:
    """Create tables, apply pending migrations, create indexes, and clean stale locks."""
    with get_connection() as conn:
        # Step 1: Create tables (executescript handles IF NOT EXISTS)
        conn.executescript(_CREATE_TABLE_SQL)

        # Step 2: Migrate — add any missing columns to existing tables
        _apply_migrations(conn)

        # Step 3: Create indexes (after migration ensures columns exist)
        _safe_create_indexes(conn)

        # Step 4: Clean stale locks
        _cleanup_stale_pipeline_locks(conn)

    logger.info("Database initialized (schema + migrations + indexes + lock cleanup verified).")


def _safe_create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes that depend on migrated columns, ignoring errors for existing ones."""
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_videos_region ON videos(source_region);",
        "CREATE INDEX IF NOT EXISTS idx_videos_content_type ON videos(content_type);",
        "CREATE INDEX IF NOT EXISTS idx_videos_run_id ON videos(pipeline_run_id);",
    ]
    for stmt in index_statements:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Index may already exist or column missing in edge cases


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
                        v.get("topics", ""),
                        v.get("source_region", ""),
                        v.get("content_type", "all"),
                        v.get("pipeline_run_id"),
                        # Connector architecture fields
                        v.get("hashtags", ""),
                        v.get("audio_name", ""),
                        v.get("hook_text", ""),
                        v.get("hook_category", ""),
                        v.get("trend_velocity", 0.0),
                        v.get("virality_score", 0.0),
                        v.get("shares", 0),
                        v.get("saves", 0),
                        v.get("author_followers", 0),
                        v.get("source_url", ""),
                        v.get("raw_payload", ""),
                        # Relevance intelligence fields
                        v.get("relevance_score", 0.0),
                        v.get("matched_keywords", ""),
                        v.get("matched_hashtags", ""),
                        v.get("match_reason", ""),
                        now,  # created_at
                        now,  # updated_at
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
_STALE_RUN_MINUTES: int = 15


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


def acquire_pipeline_lock(
    triggered_by: str = "manual",
    config_snapshot: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Create a 'running' pipeline_runs record as a database-level lock.

    Stores a snapshot of the pipeline config for dataset provenance.
    Returns the run ID. Raises RuntimeError if a run is already active.
    """
    import json as _json

    if is_pipeline_running():
        raise RuntimeError("A pipeline run is already in progress.")

    now = datetime.now(timezone.utc).isoformat()
    cfg = config_snapshot or {}
    regions = _json.dumps(cfg.get("regions", []))
    categories = _json.dumps(cfg.get("categories", []))
    keywords = _json.dumps(cfg.get("keywords", []))
    sources = _json.dumps(cfg.get("sources", ["youtube"]))
    content_type = cfg.get("content_type", "all")
    dataset_label = cfg.get("dataset_label", "")
    config_id = cfg.get("config_id")

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO pipeline_runs
               (started_at, status, triggered_by,
                config_regions, config_categories, config_keywords,
                config_sources, config_content_type, dataset_label, config_id)
               VALUES (?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, triggered_by, regions, categories, keywords,
             sources, content_type, dataset_label, config_id),
        )
        run_id = cursor.lastrowid
    logger.info("Pipeline lock acquired (run #%d, triggered_by=%s, label=%s).",
                run_id, triggered_by, dataset_label)
    return run_id


def release_pipeline_lock(run_id: int, result: Dict[str, Any]) -> None:
    """
    Update the pipeline_runs record to release the lock.

    Records final counts, elapsed time, status, and error (if any).
    On successful completion, auto-activates this run as the active dataset.
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

    # Auto-activate on successful completion
    status = result.get("status", "")
    if status.startswith("completed") and result.get("stored", 0) > 0:
        set_active_dataset(run_id)
        logger.info("Pipeline run #%d auto-activated as active dataset.", run_id)

    logger.info("Pipeline lock released (run #%d, status=%s).", run_id, result.get("status"))


# ---------------------------------------------------------------------------
# Pipeline config CRUD
# ---------------------------------------------------------------------------
def save_pipeline_config(config: Dict[str, Any]) -> int:
    """
    Insert or update a pipeline config. Returns the config ID.

    Expects a dict with keys: name, regions, platforms, categories,
    keywords, content_type, is_preset.
    """
    import json as _json

    now = datetime.now(timezone.utc).isoformat()
    regions = _json.dumps(config.get("regions", []))
    platforms = _json.dumps(config.get("platforms", ["youtube"]))
    categories = _json.dumps(config.get("categories", []))
    keywords = _json.dumps(config.get("keywords", []))
    content_type = config.get("content_type", "all")
    name = config.get("name", "Custom")
    is_preset = 1 if config.get("is_preset", False) else 0

    config_id = config.get("id")

    with get_connection() as conn:
        if config_id:
            conn.execute(
                """UPDATE pipeline_configs
                   SET name=?, regions=?, platforms=?, categories=?,
                       keywords=?, content_type=?, is_preset=?, updated_at=?
                   WHERE id=?""",
                (name, regions, platforms, categories, keywords,
                 content_type, is_preset, now, config_id),
            )
        else:
            cursor = conn.execute(
                """INSERT INTO pipeline_configs
                   (name, regions, platforms, categories, keywords,
                    content_type, is_preset, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, regions, platforms, categories, keywords,
                 content_type, is_preset, now, now),
            )
            config_id = cursor.lastrowid

    logger.info("Pipeline config saved (id=%d, name=%s).", config_id, name)
    return config_id


def get_pipeline_config(config_id: int) -> Optional[Dict[str, Any]]:
    """Return a single pipeline config by ID, with JSON fields parsed."""
    import json as _json

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pipeline_configs WHERE id = ?;", (config_id,)
        ).fetchone()

    if not row:
        return None

    d = dict(row)
    for field in ("regions", "platforms", "categories", "keywords"):
        try:
            d[field] = _json.loads(d[field]) if d[field] else []
        except (ValueError, TypeError):
            d[field] = []
    d["is_preset"] = bool(d.get("is_preset", 0))
    return d


def list_pipeline_configs(presets_only: bool = False) -> List[Dict[str, Any]]:
    """Return all pipeline configs, optionally filtered to presets only."""
    import json as _json

    query = "SELECT * FROM pipeline_configs"
    params: tuple = ()
    if presets_only:
        query += " WHERE is_preset = 1"
    query += " ORDER BY updated_at DESC;"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        for field in ("regions", "platforms", "categories", "keywords"):
            try:
                d[field] = _json.loads(d[field]) if d[field] else []
            except (ValueError, TypeError):
                d[field] = []
        d["is_preset"] = bool(d.get("is_preset", 0))
        results.append(d)
    return results


def delete_pipeline_config(config_id: int) -> bool:
    """Delete a pipeline config by ID. Returns True if deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM pipeline_configs WHERE id = ?;", (config_id,)
        )
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("Pipeline config #%d deleted.", config_id)
    return deleted


def get_last_used_config() -> Optional[Dict[str, Any]]:
    """Return the most recently updated non-preset config."""
    import json as _json

    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM pipeline_configs
               WHERE is_preset = 0
               ORDER BY updated_at DESC LIMIT 1;"""
        ).fetchone()

    if not row:
        return None

    d = dict(row)
    for field in ("regions", "platforms", "categories", "keywords"):
        try:
            d[field] = _json.loads(d[field]) if d[field] else []
        except (ValueError, TypeError):
            d[field] = []
    d["is_preset"] = bool(d.get("is_preset", 0))
    return d


# ---------------------------------------------------------------------------
# Dataset management
# ---------------------------------------------------------------------------
def _parse_run_config(row: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON fields in a pipeline_runs row into Python objects."""
    import json as _json
    d = dict(row)
    for field in ("config_regions", "config_categories", "config_keywords", "config_sources"):
        try:
            d[field] = _json.loads(d[field]) if d.get(field) else []
        except (ValueError, TypeError):
            d[field] = []
    d["is_active_dataset"] = bool(d.get("is_active_dataset", 0))
    return d


def set_active_dataset(run_id: int) -> None:
    """Mark a pipeline run as the active dataset, deactivating all others."""
    with get_connection() as conn:
        conn.execute("UPDATE pipeline_runs SET is_active_dataset = 0 WHERE is_active_dataset = 1;")
        conn.execute("UPDATE pipeline_runs SET is_active_dataset = 1 WHERE id = ?;", (run_id,))
    logger.info("Active dataset set to run #%d.", run_id)


def get_active_dataset() -> Optional[Dict[str, Any]]:
    """Return the active dataset (pipeline run) with parsed config, or None."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM pipeline_runs
               WHERE is_active_dataset = 1
               LIMIT 1;"""
        ).fetchone()

    if not row:
        # Fallback: use the most recent completed run
        with get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM pipeline_runs
                   WHERE status LIKE 'completed%' AND videos_stored > 0
                   ORDER BY started_at DESC LIMIT 1;"""
            ).fetchone()
        if row:
            # Auto-activate this fallback
            set_active_dataset(row["id"])

    if not row:
        return None

    return _parse_run_config(row)


def get_dataset_list(limit: int = 20) -> List[Dict[str, Any]]:
    """Return all completed pipeline runs as dataset entries for the switcher."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, started_at, finished_at, status,
                      videos_ingested, videos_processed, videos_enriched,
                      videos_stored, elapsed_seconds,
                      config_regions, config_categories, config_keywords,
                      config_sources, config_content_type, dataset_label,
                      is_active_dataset, config_id
               FROM pipeline_runs
               WHERE status LIKE 'completed%'
               ORDER BY started_at DESC
               LIMIT ?;""",
            (limit,),
        ).fetchall()

    return [_parse_run_config(r) for r in rows]


def get_dataset_stats(run_id: int) -> Dict[str, Any]:
    """Return aggregate stats for a specific pipeline run dataset."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS total_videos,
                   ROUND(AVG(score), 4) AS avg_score,
                   ROUND(AVG(engagement_rate), 6) AS avg_engagement,
                   SUM(views) AS total_views
               FROM videos
               WHERE pipeline_run_id = ?;""",
            (run_id,),
        ).fetchone()

        # Top category
        cat_row = conn.execute(
            """SELECT niche, COUNT(*) AS cnt FROM videos
               WHERE pipeline_run_id = ?
               GROUP BY niche ORDER BY cnt DESC LIMIT 1;""",
            (run_id,),
        ).fetchone()

        # Top creator
        creator_row = conn.execute(
            """SELECT channel, COUNT(*) AS cnt FROM videos
               WHERE pipeline_run_id = ? AND channel != ''
               GROUP BY channel ORDER BY cnt DESC LIMIT 1;""",
            (run_id,),
        ).fetchone()

    stats = dict(row) if row else {"total_videos": 0, "avg_score": 0, "avg_engagement": 0, "total_views": 0}
    stats["top_category"] = cat_row["niche"] if cat_row else ""
    stats["top_creator"] = creator_row["channel"] if creator_row else ""
    return stats


def generate_dataset_label(config: Dict[str, Any]) -> str:
    """Generate a human-readable label from a pipeline config."""
    parts = []

    regions = config.get("regions", [])
    if regions and len(regions) <= 3:
        region_names = {
            "US": "US", "GB": "UK", "CA": "Canada", "DE": "Germany",
            "FR": "France", "AU": "Australia", "AE": "UAE", "SA": "Saudi",
            "EG": "Egypt", "IN": "India", "BR": "Brazil", "JP": "Japan", "KR": "Korea",
        }
        parts.append(" ".join(region_names.get(r, r) for r in regions[:3]))
    elif regions:
        parts.append(f"{len(regions)} Regions")

    categories = config.get("categories", [])
    if categories and len(categories) <= 2:
        parts.append(" ".join(c.title() for c in categories[:2]))
    elif categories:
        parts.append(f"{len(categories)} Categories")

    content_type = config.get("content_type", "all")
    if content_type and content_type != "all":
        parts.append(content_type.title())

    return " · ".join(parts) if parts else "Global Trending"
