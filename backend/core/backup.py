"""Consistent SQLite backup and retention helpers."""

from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.config import get_settings

logger = logging.getLogger(__name__)


def _backup_directory(source: Path, output_dir: str | Path | None) -> Path:
    configured = Path(output_dir) if output_dir is not None else Path(get_settings().database_backup_dir)
    return configured if configured.is_absolute() else source.parent / configured


def prune_database_backups(
    *,
    source_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    retention_days: int | None = None,
) -> int:
    """Remove backups older than the configured retention period."""
    source = Path(source_path or get_settings().sqlite_db_path).expanduser().resolve()
    directory = _backup_directory(source, output_dir)
    if not directory.exists():
        return 0

    days = retention_days if retention_days is not None else get_settings().database_backup_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0
    for candidate in directory.glob(f"{source.stem}-*.sqlite3"):
        modified = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            candidate.unlink()
            removed += 1
    if removed:
        logger.info("Pruned %d expired database backup(s).", removed)
    return removed


def create_database_backup(
    *,
    source_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    retention_days: int | None = None,
) -> Path:
    """Create a consistent SQLite snapshot using SQLite's online backup API."""
    source = Path(source_path or get_settings().sqlite_db_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {source}")

    destination_dir = _backup_directory(source, output_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_dir / f"{source.stem}-{timestamp}.sqlite3"

    with sqlite3.connect(str(source)) as source_conn, sqlite3.connect(str(destination)) as destination_conn:
        source_conn.backup(destination_conn)

    prune_database_backups(
        source_path=source,
        output_dir=destination_dir,
        retention_days=retention_days,
    )
    logger.info("Database backup created: %s", destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite database backup.")
    parser.add_argument("--source", help="SQLite database path (defaults to SQLITE_DB_PATH).")
    parser.add_argument("--output-dir", help="Backup destination directory.")
    parser.add_argument("--retention-days", type=int, help="Delete older backups after creation.")
    args = parser.parse_args()
    print(
        create_database_backup(
            source_path=args.source,
            output_dir=args.output_dir,
            retention_days=args.retention_days,
        )
    )


if __name__ == "__main__":
    main()
