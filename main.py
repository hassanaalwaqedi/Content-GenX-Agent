"""
Pipeline runner for Content Intelligence Platform.

Orchestrates the full ETL flow:
  1. Ingest raw videos from YouTube
  2. Process, score, and filter
  3. Enrich with AI-derived metadata
  4. Store in database

Usage:
  python main.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from config import get_settings
from database import init_db, insert_videos, acquire_pipeline_lock, release_pipeline_lock
from ingestion import ingest_videos
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


def run_pipeline(triggered_by: str = "manual") -> Dict[str, Any]:
    """
    Execute the complete data pipeline.

    Args:
        triggered_by: Origin of the run ("manual", "api", "scheduler").

    Returns a summary dict with counts for each stage.
    """
    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("  CONTENT INTELLIGENCE PIPELINE -- START")
    logger.info("  Timestamp: %s", start.isoformat())
    logger.info("  Triggered by: %s", triggered_by)
    logger.info("=" * 60)

    result: Dict[str, Any] = {
        "started_at": start.isoformat(),
        "ingested": 0,
        "processed": 0,
        "enriched": 0,
        "stored": 0,
        "status": "unknown",
    }

    # Acquire database-level pipeline lock
    run_id: int | None = None
    try:
        # ---- Step 0: Initialize database ------------------------------------
        logger.info("Step 0/4 -- Initializing database...")
        init_db()

        run_id = acquire_pipeline_lock(triggered_by=triggered_by)

        # ---- Step 1: Ingest -------------------------------------------------
        logger.info("Step 1/4 -- Ingesting from YouTube + Reddit...")
        raw_videos = ingest_videos()
        logger.info("YouTube: %d videos ingested.", len(raw_videos))

        reddit_posts = ingest_reddit_posts()
        logger.info("Reddit: %d posts ingested.", len(reddit_posts))

        raw_videos.extend(reddit_posts)
        result["ingested"] = len(raw_videos)
        logger.info("Total ingestion: %d items (YouTube + Reddit).", len(raw_videos))

        if not raw_videos:
            logger.warning("No content ingested -- check API keys.")
            result["status"] = "completed_empty"
            result["error"] = "Zero items ingested -- check YouTube/Reddit API keys."
            return result

        # ---- Step 2: Process ------------------------------------------------
        logger.info("Step 2/4 -- Processing and scoring...")
        processed = process_videos(raw_videos)
        result["processed"] = len(processed)
        logger.info("Processing complete: %d videos passed filters.", len(processed))

        if not processed:
            logger.warning("All videos filtered out -- nothing to store.")
            result["status"] = "completed_filtered"
            return result

        # ---- Step 3: AI Enrichment ------------------------------------------
        logger.info("Step 3/5 -- Enriching with AI metadata...")
        enriched = enrich_videos(processed)
        result["enriched"] = len(enriched)
        logger.info("Enrichment complete: %d videos enriched.", len(enriched))

        # ---- Step 4: Transcript Extraction ----------------------------------
        logger.info("Step 4/5 -- Extracting transcripts (YouTube only)...")
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

        # ---- Step 5: Store --------------------------------------------------
        logger.info("Step 5/5 -- Storing in database...")
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
            "  Ingested=%d  Processed=%d  Enriched=%d  Stored=%d",
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

    logger.info("Content Intelligence Platform v1.0.0")
    logger.info("Niches: %s", settings.niche_keywords)
    logger.info("Database: %s", settings.sqlite_db_path)

    result = run_pipeline()
    sys.exit(0 if result["status"].startswith("completed") else 1)


if __name__ == "__main__":
    main()
