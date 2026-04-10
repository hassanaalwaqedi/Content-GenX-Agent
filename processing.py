"""
Processing module for Content Intelligence Platform.

Responsibilities:
  - Clean and validate raw video data
  - Compute engagement_rate = (likes + comments) / views
  - Compute a composite score using configurable weights:
        score = w_views * norm(log(views))
              + w_engagement * norm(engagement_rate)
              + w_recency * recency_factor
  - Filter out low-quality videos (views < threshold, engagement < threshold)
  - Return typed ProcessedVideo models for downstream layers
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from ingestion import RawVideo
from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed output model
# ---------------------------------------------------------------------------
class ProcessedVideo(BaseModel):
    """
    Validated, scored video record ready for database insertion.

    Using Pydantic here provides type safety at the processing→database
    boundary and catches data quality issues before they reach storage.
    """
    video_id: str
    platform: str = "youtube"
    niche: str
    title: str
    description: str = ""
    channel: str = ""
    thumbnail_url: str = ""
    published_at: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    engagement_rate: float = Field(default=0.0, ge=0.0)
    score: float = Field(default=0.0, ge=0.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for database insertion."""
        return self.model_dump()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_engagement_rate(views: int, likes: int, comments: int) -> float:
    """Compute engagement rate, guarding against division by zero."""
    if views <= 0:
        return 0.0
    return (likes + comments) / views


def _recency_factor(published_at: str, *, half_life_days: float = 30.0) -> float:
    """
    Return a recency score in [0, 1] using exponential decay.

    A video published *today* scores ~1.0.
    A video published ``half_life_days`` ago scores ~0.5.
    """
    try:
        # YouTube timestamps are ISO-8601 with trailing 'Z'
        pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 0.0

    age_days = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 86_400
    if age_days < 0:
        age_days = 0
    decay = math.exp(-math.log(2) * age_days / half_life_days)
    return round(decay, 6)


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalize a value to [0, 1]."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


# ---------------------------------------------------------------------------
# Core processing pipeline
# ---------------------------------------------------------------------------
def process_videos(raw_videos: List[RawVideo]) -> List[Dict[str, Any]]:
    """
    Full processing pipeline:
      1. Validate & clean
      2. Compute engagement_rate
      3. Compute composite score
      4. Filter by thresholds
      5. Sort by score descending

    Returns a list of validated ProcessedVideo dicts ready for storage.
    """
    settings = get_settings()
    weights = settings.scoring_weights
    thresholds = settings.filter_thresholds

    if not raw_videos:
        logger.warning("No raw videos to process.")
        return []

    # ---- Step 1: Clean & enrich -------------------------------------------
    enriched: List[Dict[str, Any]] = []
    for rv in raw_videos:
        if not rv.video_id or not rv.title:
            logger.debug("Skipping invalid video (missing id/title): %s", rv)
            continue

        engagement = _safe_engagement_rate(rv.views, rv.likes, rv.comments)
        recency = _recency_factor(rv.published_at)

        enriched.append(
            {
                **rv.to_dict(),
                "engagement_rate": round(engagement, 6),
                "recency_factor": recency,
                "log_views": math.log1p(rv.views),  # log(1 + views)
            }
        )

    logger.info("Enriched %d / %d videos.", len(enriched), len(raw_videos))

    # ---- Step 2: Compute score (needs global min/max for normalization) ---
    log_views_vals = [v["log_views"] for v in enriched]
    eng_vals = [v["engagement_rate"] for v in enriched]

    lv_min, lv_max = min(log_views_vals), max(log_views_vals)
    eng_min, eng_max = min(eng_vals), max(eng_vals)

    for v in enriched:
        norm_lv = _normalize(v["log_views"], lv_min, lv_max)
        norm_eng = _normalize(v["engagement_rate"], eng_min, eng_max)
        recency = v["recency_factor"]  # already in [0, 1]

        v["score"] = round(
            weights.views * norm_lv
            + weights.engagement * norm_eng
            + weights.recency * recency,
            6,
        )

    # ---- Step 3: Filter ----------------------------------------------------
    before_filter = len(enriched)
    filtered = [
        v
        for v in enriched
        if v["views"] >= thresholds.min_views
        and v["engagement_rate"] >= thresholds.min_engagement_rate
    ]
    logger.info(
        "Filtered %d -> %d videos (min_views=%d, min_engagement=%.4f).",
        before_filter,
        len(filtered),
        thresholds.min_views,
        thresholds.min_engagement_rate,
    )

    # ---- Step 4: Sort by score desc ----------------------------------------
    filtered.sort(key=lambda v: v["score"], reverse=True)

    # ---- Step 5: Validate through Pydantic model ---------------------------
    validated: List[Dict[str, Any]] = []
    for v in filtered:
        # Remove transient keys before validation
        v.pop("log_views", None)
        v.pop("recency_factor", None)
        try:
            record = ProcessedVideo(**v)
            validated.append(record.to_dict())
        except Exception as exc:
            logger.warning(
                "Validation failed for video %s: %s", v.get("video_id"), exc
            )

    logger.info("Processing complete. %d videos validated and ready.", len(validated))
    return validated
