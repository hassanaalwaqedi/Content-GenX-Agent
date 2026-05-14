"""
Pipeline runner for Content Intelligence Platform.

Orchestrates the full ETL flow:
  1. Purge stale YouTube data (freshness guarantee)
  2. Ingest real trending videos from YouTube (mostPopular)
  3. Process, score, and filter
  4. Enrich with AI-derived metadata
  5. Extract transcripts
  6. Store in database (upsert)

Usage:
  python main.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from config import get_settings
from database import (
    init_db, insert_videos, acquire_pipeline_lock, release_pipeline_lock,
    get_pipeline_config, generate_dataset_label,
)
from ingestion import ingest_videos, purge_stale_youtube_videos, PipelineConfig
from reddit_ingestion import ingest_reddit_posts
from processing import process_videos
from ai_enrichment import enrich_videos
from transcripts import fetch_transcript

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Set up structured logging based on config."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format=settings.log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def run_pipeline(triggered_by: str = "manual", config_id: int | None = None) -> Dict[str, Any]:
    """
    Execute the complete data pipeline.

    Args:
        triggered_by: Origin of the run ("manual", "api", "scheduler").
        config_id: Optional pipeline config ID for user-defined filters.

    Returns a summary dict with counts for each stage.
    """
    start = datetime.now(timezone.utc)

    # Load user config if provided
    pipeline_cfg: PipelineConfig | None = None
    config_summary = "Default (all regions, no filters)"
    if config_id:
        db_config = get_pipeline_config(config_id)
        if db_config:
            pipeline_cfg = PipelineConfig.from_dict(db_config)
            config_summary = (
                f"Config #{config_id}: regions={pipeline_cfg.regions}, "
                f"keywords={pipeline_cfg.keywords}, content_type={pipeline_cfg.content_type}"
            )
        else:
            logger.warning("Config #%d not found — using defaults.", config_id)

    logger.info("=" * 60)
    logger.info("  CONTENT INTELLIGENCE PIPELINE -- START")
    logger.info("  Timestamp: %s", start.isoformat())
    logger.info("  Triggered by: %s", triggered_by)
    logger.info("  Config: %s", config_summary)
    logger.info("=" * 60)

    # Build config snapshot for dataset provenance
    config_snapshot = {}
    if pipeline_cfg:
        config_snapshot = {
            "regions": pipeline_cfg.regions,
            "categories": pipeline_cfg.categories,
            "keywords": pipeline_cfg.keywords,
            "sources": pipeline_cfg.platforms,
            "content_type": pipeline_cfg.content_type,
            "config_id": config_id,
        }
    config_snapshot["dataset_label"] = generate_dataset_label(config_snapshot)
    logger.info("Dataset label: %s", config_snapshot["dataset_label"])

    result: Dict[str, Any] = {
        "started_at": start.isoformat(),
        "config_id": config_id,
        "ingested": 0,
        "processed": 0,
        "enriched": 0,
        "stored": 0,
        "stale_purged": 0,
        "status": "unknown",
    }

    # Acquire database-level pipeline lock
    run_id: int | None = None
    try:
        # ---- Step 0: Initialize database ------------------------------------
        logger.info("Step 0/6 -- Initializing database...")
        init_db()

        run_id = acquire_pipeline_lock(
            triggered_by=triggered_by,
            config_snapshot=config_snapshot,
        )

        # ---- Step 1: Preflight check ----------------------------------------
        logger.info("Step 1/6 -- Preflight checks...")
        settings = get_settings()

        # Check if YouTube is in the platforms list (skip YT check if not needed)
        platforms = pipeline_cfg.platforms if pipeline_cfg else ["youtube"]

        if "youtube" in platforms:
            yt_key = settings.youtube_api_key
            if not yt_key or yt_key.strip().lower() in (
                "your_youtube_api_key_here", "your_api_key_here", "change_me", "xxx", ""
            ):
                logger.error(
                    "YouTube API key is missing or set to a placeholder! "
                    "Set a valid YOUTUBE_API_KEY in .env"
                )
                result["status"] = "failed"
                result["error"] = (
                    "YouTube API key not configured. "
                    "Set YOUTUBE_API_KEY in your .env file."
                )
                return result

        # ---- Step 2: Ingest -------------------------------------------------
        logger.info("Step 2/6 -- Ingesting content...")
        raw_videos = []

        if "youtube" in platforms:
            yt_videos = ingest_videos(config=pipeline_cfg)
            logger.info("YouTube: %d videos ingested.", len(yt_videos))
            raw_videos.extend(yt_videos)

        if "reddit" in platforms:
            reddit_posts = ingest_reddit_posts()
            logger.info("Reddit: %d posts ingested.", len(reddit_posts))
            raw_videos.extend(reddit_posts)

        result["ingested"] = len(raw_videos)
        logger.info("Total ingestion: %d items.", len(raw_videos))

        if not raw_videos:
            logger.warning("No content ingested -- check API keys.")
            result["status"] = "completed_empty"
            result["error"] = "Zero items ingested -- check YouTube/Reddit API keys."
            return result

        # ---- Step 2b: Purge stale data (AFTER successful ingestion) ---------
        # Only purge old data once we've confirmed new data is available.
        # This prevents the "purge everything → fail to ingest → empty DB" scenario.
        logger.info("Step 2b/6 -- Purging stale YouTube data (>7 days)...")
        stale_count = purge_stale_youtube_videos()
        result["stale_purged"] = stale_count
        logger.info("Purged %d stale records.", stale_count)

        # ---- Step 3: Process ------------------------------------------------
        logger.info("Step 3/6 -- Processing and scoring...")
        processed = process_videos(raw_videos, config=pipeline_cfg)
        result["processed"] = len(processed)
        logger.info("Processing complete: %d videos passed filters.", len(processed))

        if not processed:
            logger.warning("All videos filtered out -- nothing to store.")
            result["status"] = "completed_filtered"
            return result

        # ---- Step 4: AI Enrichment ------------------------------------------
        logger.info("Step 4/6 -- Enriching with AI metadata...")
        enriched = enrich_videos(processed)
        result["enriched"] = len(enriched)
        logger.info("Enrichment complete: %d videos enriched.", len(enriched))

        # ---- Step 5: Transcript Extraction ----------------------------------
        logger.info("Step 5/6 -- Extracting transcripts (YouTube only)...")
        transcript_count = 0
        for idx, video in enumerate(enriched):
            vid_id = video.get("video_id", "")
            if vid_id and not vid_id.startswith("reddit_"):
                transcript = fetch_transcript(vid_id)
                if transcript:
                    video["transcript"] = transcript
                    transcript_count += 1
                # Throttle to avoid YouTube IP blocking
                if idx < len(enriched) - 1:
                    import time
                    time.sleep(1.0)
        result["transcripts"] = transcript_count
        logger.info("Transcripts extracted: %d/%d videos.", transcript_count, len(enriched))

        # ---- Step 6: Store --------------------------------------------------
        logger.info("Step 6/6 -- Storing in database (upsert)...")
        # Tag every video with the pipeline run ID for dataset isolation
        for video in enriched:
            video["pipeline_run_id"] = run_id
        stored = insert_videos(enriched)
        result["stored"] = stored
        logger.info("Storage complete: %d videos upserted.", stored)

        result["status"] = "completed"

    except Exception as exc:
        logger.error("Pipeline FAILED: %s", exc, exc_info=True)
        result["status"] = "failed"
        result["error"] = str(exc)

    finally:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        result["elapsed_seconds"] = round(elapsed, 2)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()

        # Release database-level pipeline lock
        if run_id is not None:
            try:
                release_pipeline_lock(run_id, result)
            except Exception as lock_exc:
                logger.error("Failed to release pipeline lock: %s", lock_exc)

        logger.info("=" * 60)
        logger.info("  PIPELINE COMPLETE -- %s", result["status"].upper())
        logger.info(
            "  Purged=%d  Ingested=%d  Processed=%d  Enriched=%d  Stored=%d",
            result.get("stale_purged", 0),
            result["ingested"],
            result["processed"],
            result["enriched"],
            result["stored"],
        )
        logger.info("  Elapsed: %.2fs", elapsed)
        logger.info("=" * 60)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entry point."""
    _configure_logging()
    settings = get_settings()

    logger.info("Content Intelligence Platform v1.1.0")
    logger.info("Strategy: Global trending ingestion (mostPopular, NO niche bias)")
    logger.info("Regions: %s", ", ".join(["US", "GB", "CA", "DE", "FR", "AU", "AE"]))
    logger.info("Database: %s", settings.sqlite_db_path)

    result = run_pipeline()
    sys.exit(0 if result["status"].startswith("completed") else 1)


if __name__ == "__main__":
    main()
