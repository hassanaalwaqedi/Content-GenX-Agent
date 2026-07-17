"""
Pipeline runner for Content Intelligence Platform.

Orchestrates the full ETL flow:
  1. Purge stale YouTube data (freshness guarantee)
   2. Ingest real trending videos from YouTube (mostPopular)
   3. Ingest from connector-based platforms (Reddit, TikTok, Instagram via Apify)
  5. Process, score, and filter
  6. Enrich with AI-derived metadata
  7. Extract transcripts
  8. Store in database (upsert)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from dataclasses import replace
from typing import Any, Dict

from core.config import get_settings
from core.logging import configure_logging
from core.database import (
    init_db, insert_videos, acquire_pipeline_lock, release_pipeline_lock,
    get_pipeline_config, generate_dataset_label, update_pipeline_run_snapshot,
)
from pipeline.ingestion import ingest_videos, purge_stale_youtube_videos, PipelineConfig, RawVideo
from pipeline.processing import process_videos
from enrichment.ai import enrich_videos
from pipeline.transcripts import fetch_transcript
from connectors.registry import ConnectorRegistry
from services.query_intelligence import QueryIntelligenceEngine

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Set up structured logging based on config."""
    configure_logging(get_settings())


def _platform_keywords(pipeline_cfg: PipelineConfig | None, platform: str) -> list[str]:
    """Expand saved keywords into a bounded platform-specific query set."""
    if not pipeline_cfg or not pipeline_cfg.keywords:
        return []

    settings = get_settings()
    engine = QueryIntelligenceEngine(
        max_synonyms=settings.query_max_synonyms,
        max_hashtag_variants=settings.query_max_hashtag_variants,
    )
    context = engine.merge_contexts(engine.expand_multi(pipeline_cfg.keywords))
    variants = getattr(context, f"{platform}_variants", None) or pipeline_cfg.keywords
    terms = list(dict.fromkeys(term.strip() for term in variants if term and term.strip()))[:8]
    logger.info("Query intelligence selected %d %s search term(s).", len(terms), platform)
    return terms


def run_pipeline(
    triggered_by: str = "manual",
    config_id: int | None = None,
    pre_acquired_run_id: int | None = None,
) -> Dict[str, Any]:
    """
    Execute the complete data pipeline.

    Args:
        triggered_by: Origin of the run ("manual", "api", "scheduler").
        config_id: Optional pipeline config ID for user-defined filters.
        pre_acquired_run_id: A lock reserved by an API request before the
            background worker is started.

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
    run_id: int | None = pre_acquired_run_id
    try:
        # ---- Step 0: Initialize database ------------------------------------
        logger.info("Step 0/6 -- Initializing database...")
        init_db()

        if run_id is None:
            run_id = acquire_pipeline_lock(
                triggered_by=triggered_by,
                config_snapshot=config_snapshot,
            )
        else:
            update_pipeline_run_snapshot(run_id, config_snapshot)

        # ---- Step 1: Preflight check ----------------------------------------
        logger.info("Step 1/6 -- Preflight checks...")
        settings = get_settings()

        # Check which platforms are configured (all available if no user config)
        platforms = pipeline_cfg.platforms if pipeline_cfg else ["all"]

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
            youtube_config = pipeline_cfg
            if pipeline_cfg and pipeline_cfg.keywords:
                youtube_config = replace(
                    pipeline_cfg,
                    keywords=_platform_keywords(pipeline_cfg, "youtube"),
                )
            yt_videos = ingest_videos(config=youtube_config)
            logger.info("YouTube: %d videos ingested.", len(yt_videos))
            raw_videos.extend(yt_videos)

        # Connector-based platforms (Reddit, TikTok, Instagram, etc.)
        registry = ConnectorRegistry()
        for platform_id, connector in registry.get_all_connectors().items():
            if platform_id == "youtube":
                continue
            if platform_id in platforms or "all" in platforms:
                try:
                    region = pipeline_cfg.regions[0] if pipeline_cfg and pipeline_cfg.regions else "US"
                    if pipeline_cfg and pipeline_cfg.keywords:
                        # TikTok and Instagram expand the raw terms inside their
                        # connectors. YouTube and Reddit use the shared variants
                        # here because their clients accept plain search phrases.
                        keywords = (
                            _platform_keywords(pipeline_cfg, platform_id)
                            if platform_id in {"reddit", "youtube"}
                            else pipeline_cfg.keywords
                        )
                        items = connector.fetch_by_keywords(
                            keywords, limit=30, region=region,
                        )
                    else:
                        kw = pipeline_cfg.keywords if pipeline_cfg else None
                        items = connector.fetch_trending(
                            limit=30, region=region, keywords=kw,
                        )
                    for item in items:
                        d = item.to_raw_video()
                        raw_videos.append(RawVideo(
                            video_id=d["video_id"],
                            title=d["title"],
                            channel=d["channel"],
                            description=d["description"],
                            published_at=d["published_at"],
                            thumbnail_url=d["thumbnail_url"],
                            views=d["views"],
                            likes=d["likes"],
                            comments=d["comments"],
                            niche=d["niche"],
                            platform=d["platform"],
                            source_region=d["source_region"],
                            content_type=d["content_type"],
                            source_url=d.get("source_url", ""),
                            platform_metadata=d.get("platform_metadata", {}),
                        ))
                    logger.info(
                        "%s connector: %d items ingested.",
                        platform_id.title(), len(items),
                    )
                except Exception as exc:
                    logger.error("%s connector failed: %s", platform_id.title(), exc)

        result["ingested"] = len(raw_videos)
        logger.info("Total ingestion: %d items.", len(raw_videos))

        if not raw_videos:
            logger.warning("No content ingested -- check API keys.")
            result["status"] = "completed_empty"
            result["error"] = "Zero items ingested -- check API keys and credentials."
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
