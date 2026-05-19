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
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ingestion import RawVideo, PipelineConfig
from config import get_settings

logger = logging.getLogger(__name__)

# Default regions that indicate a broad (not region-specific) run
_GLOBAL_REGION_SET = {
    "US", "CA", "BR", "MX",
    "GB", "DE", "FR", "NL", "ES", "IT", "SE", "CH", "PL", "NO",
    "AE", "SA", "KW", "QA", "BH", "EG", "TR",
    "AU", "JP", "KR", "SG",
}
_REGION_SPECIFIC_THRESHOLD = 8  # Relax filters if fewer than this many regions


# ---------------------------------------------------------------------------
# Typed output model
# ---------------------------------------------------------------------------
class ProcessedVideo(BaseModel):
    """
    Validated, scored video record ready for database insertion.
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
    source_region: str = ""
    content_type: str = "all"

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
def process_videos(
    raw_videos: List[RawVideo],
    config: Optional[PipelineConfig] = None,
) -> List[Dict[str, Any]]:
    """
    Full processing pipeline with dynamic threshold relaxation.

    When a region-specific config is detected (fewer than 4 regions),
    thresholds are relaxed to min_views=500, min_engagement=0.01
    to avoid filtering out niche regional content.
    """
    settings = get_settings()
    weights = settings.scoring_weights
    thresholds = settings.filter_thresholds

    # Part 2: Dynamic threshold relaxation
    min_views = thresholds.min_views
    min_engagement = thresholds.min_engagement_rate

    if config and len(config.regions) < _REGION_SPECIFIC_THRESHOLD:
        # Region-specific run — relax filters
        min_views = min(min_views, 500)
        min_engagement = min(min_engagement, 0.01)
        logger.info(
            "Region-specific run (%d regions) — relaxed thresholds: min_views=%d, min_engagement=%.3f",
            len(config.regions), min_views, min_engagement,
        )

    if not raw_videos:
        logger.warning("No raw videos to process.")
        return []

    # ---- Step 1: Clean & enrich -------------------------------------------
    enriched: List[Dict[str, Any]] = []
    for rv in raw_videos:
        # Handle both RawVideo dataclass instances and plain dicts
        # (connectors return dicts via NormalizedContent.to_raw_video())
        if isinstance(rv, dict):
            d = rv
        else:
            d = rv.to_dict() if hasattr(rv, 'to_dict') else vars(rv)

        if not d.get("video_id") or not d.get("title"):
            continue

        views = int(d.get("views", 0) or 0)
        likes = int(d.get("likes", 0) or 0)
        comments_count = int(d.get("comments", 0) or 0)
        engagement = _safe_engagement_rate(views, likes, comments_count)
        recency = _recency_factor(d.get("published_at", ""))

        enriched.append(
            {
                **d,
                "engagement_rate": round(engagement, 6),
                "recency_factor": recency,
                "log_views": math.log1p(views),
            }
        )

    logger.info("Enriched %d / %d videos.", len(enriched), len(raw_videos))

    # ---- Step 2: Compute score ---
    log_views_vals = [v["log_views"] for v in enriched]
    eng_vals = [v["engagement_rate"] for v in enriched]

    lv_min, lv_max = min(log_views_vals), max(log_views_vals)
    eng_min, eng_max = min(eng_vals), max(eng_vals)

    for v in enriched:
        norm_lv = _normalize(v["log_views"], lv_min, lv_max)
        norm_eng = _normalize(v["engagement_rate"], eng_min, eng_max)
        recency = v["recency_factor"]

        v["score"] = round(
            weights.views * norm_lv
            + weights.engagement * norm_eng
            + weights.recency * recency,
            6,
        )

    # ---- Step 3: Filter with dynamic thresholds ---
    before_filter = len(enriched)
    filtered = [
        v for v in enriched
        if v["views"] >= min_views
        and v["engagement_rate"] >= min_engagement
    ]
    logger.info(
        "Filtered %d -> %d videos (min_views=%d, min_engagement=%.4f).",
        before_filter, len(filtered), min_views, min_engagement,
    )

    # ---- Step 4: Sort by score desc ----------------------------------------
    filtered.sort(key=lambda v: v["score"], reverse=True)

    # ---- Step 5: Validate through Pydantic model ---------------------------
    validated: List[Dict[str, Any]] = []
    for v in filtered:
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
