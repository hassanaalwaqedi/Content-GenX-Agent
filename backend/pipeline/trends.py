"""
Trend Discovery & Opportunity Engine for Content Intelligence Platform.

Provides:
  - Topic-based trend clustering from video data
  - Trend scoring (engagement × score × volume)
  - Opportunity detection (high engagement, low competition)
  - Suggested title generation via LLM
  - In-memory caching with TTL
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_cache: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _set_cached(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# Topic parsing
# ---------------------------------------------------------------------------
def _parse_topics(topics_raw: Optional[str]) -> List[str]:
    """Safely parse a JSON topics string into a list of normalized strings."""
    if not topics_raw or not topics_raw.strip():
        return []
    try:
        parsed = json.loads(topics_raw)
        if isinstance(parsed, list):
            return [_normalize_topic(t) for t in parsed if isinstance(t, str) and t.strip()]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _normalize_topic(topic: str) -> str:
    """Normalize a topic string: lowercase, strip, collapse whitespace, replace underscores."""
    t = topic.lower().strip()
    t = t.replace("_", " ")
    t = re.sub(r"\s+", " ", t)
    return t


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
def _topics_similar(a: str, b: str) -> bool:
    """Check if two normalized topics are similar enough to merge."""
    if a == b:
        return True
    # One contains the other
    if a in b or b in a:
        return True
    # Word overlap >= 60%
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    min_len = min(len(words_a), len(words_b))
    return (overlap / min_len) >= 0.6 if min_len > 0 else False


def _find_canonical(topic: str, canonical_map: Dict[str, str]) -> str:
    """Find the canonical topic name for a given topic, or return itself."""
    if topic in canonical_map:
        return canonical_map[topic]
    for existing in canonical_map:
        if _topics_similar(topic, existing):
            canonical_map[topic] = canonical_map[existing]
            return canonical_map[existing]
    canonical_map[topic] = topic
    return topic


def build_trend_clusters(
    videos: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group videos by similar topics into trend clusters.

    Each video can belong to multiple clusters (one per topic).
    Returns a list of cluster dicts sorted by video count descending.
    """
    canonical_map: Dict[str, str] = {}
    clusters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for video in videos:
        topics = _parse_topics(video.get("topics", ""))
        if not topics:
            # Fallback: use category as topic (auto-detected from YouTube categoryId)
            topics = [_normalize_topic(video.get("niche", "general"))]

        for topic in topics:
            canonical = _find_canonical(topic, canonical_map)
            # Avoid duplicates in same cluster
            if not any(v.get("video_id") == video.get("video_id") for v in clusters[canonical]):
                clusters[canonical].append(video)

    result = []
    for trend_name, vids in clusters.items():
        if len(vids) < 1:
            continue
        result.append({
            "trend": trend_name,
            "videos": vids,
            "count": len(vids),
        })

    result.sort(key=lambda c: c["count"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# Trend Scoring
# ---------------------------------------------------------------------------
def score_trend(cluster: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a trend cluster based on engagement, quality, and volume.

    Formula: (avg_score * 0.4) + (avg_engagement * 0.3) + (log(count) * 0.3)
    All components normalized to [0, 1] range.
    """
    vids = cluster.get("videos", [])
    count = len(vids)
    if count == 0:
        cluster.update({"trend_score": 0, "avg_views": 0, "avg_engagement": 0, "avg_score": 0})
        return cluster

    avg_score = sum(v.get("score", 0) for v in vids) / count
    avg_engagement = sum(v.get("engagement_rate", 0) for v in vids) / count
    avg_views = sum(v.get("views", 0) for v in vids) / count
    total_views = sum(v.get("views", 0) for v in vids)

    # Normalize log(count) to ~[0,1] (log(1)=0, log(50)≈3.9 → /4)
    log_count = min(math.log(max(count, 1) + 1) / 4.0, 1.0)

    # Normalize avg_engagement (typically 0-0.1 → *10 to get 0-1)
    eng_normalized = min(avg_engagement * 10, 1.0)

    # avg_score is already 0-1 typically
    score_normalized = min(avg_score, 1.0)

    trend_score = (score_normalized * 0.4) + (eng_normalized * 0.3) + (log_count * 0.3)

    cluster.update({
        "trend_score": round(trend_score, 4),
        "avg_views": round(avg_views),
        "avg_engagement": round(avg_engagement, 6),
        "avg_score": round(avg_score, 4),
        "total_views": total_views,
    })
    return cluster


# ---------------------------------------------------------------------------
# Opportunity Engine
# ---------------------------------------------------------------------------
def compute_opportunity(cluster: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute an opportunity score for a trend cluster.

    Opportunity = high engagement + high score - high competition.
    Formula: (avg_engagement * 0.5) + (avg_score * 0.3) - (log(count) * 0.2)
    """
    vids = cluster.get("videos", [])
    count = len(vids)
    if count == 0:
        return {**cluster, "opportunity_score": 0, "reasons": []}

    avg_score = cluster.get("avg_score", 0)
    avg_engagement = cluster.get("avg_engagement", 0)

    if avg_score == 0:
        avg_score = sum(v.get("score", 0) for v in vids) / count
    if avg_engagement == 0:
        avg_engagement = sum(v.get("engagement_rate", 0) for v in vids) / count

    eng_normalized = min(avg_engagement * 10, 1.0)
    score_normalized = min(avg_score, 1.0)
    log_count = min(math.log(max(count, 1) + 1) / 4.0, 1.0)

    opportunity = (eng_normalized * 0.5) + (score_normalized * 0.3) - (log_count * 0.2)
    opportunity = max(0, min(1, opportunity))

    # Build reasons
    reasons = []
    if eng_normalized > 0.5:
        reasons.append("high engagement")
    if score_normalized > 0.5:
        reasons.append("high quality content")
    if count <= 5:
        reasons.append("low competition")
    if count <= 3:
        reasons.append("emerging topic")
    if eng_normalized > 0.3 and count <= 8:
        reasons.append("rising trend")

    cluster["opportunity_score"] = round(opportunity, 4)
    cluster["reasons"] = reasons
    return cluster


# ---------------------------------------------------------------------------
# Suggested Titles
# ---------------------------------------------------------------------------
def generate_suggested_titles(
    cluster: Dict[str, Any],
    client: Optional[Any] = None,
) -> List[str]:
    """
    Generate suggested video titles for a trend cluster.

    Uses LLM if client is provided, otherwise uses template-based generation.
    """
    trend = cluster.get("trend", "")
    top_titles = [v.get("title", "") for v in cluster.get("videos", [])[:5]]

    if client:
        try:
            prompt = (
                "You are a YouTube content strategist. Given a trending topic and existing top video titles, "
                "suggest 3 new compelling video titles that could capture remaining audience.\n\n"
                f"Trending Topic: {trend}\n"
                f"Existing Top Titles:\n" + "\n".join(f"- {t}" for t in top_titles) + "\n\n"
                "Respond with a JSON array of 3 title strings only. No explanation."
            )
            raw = client.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
            titles = json.loads(cleaned)
            if isinstance(titles, list):
                return [str(t) for t in titles[:3]]
        except Exception as exc:
            logger.warning("LLM title generation failed: %s", exc)

    # Template fallback
    trend_title = trend.replace("_", " ").title()
    return [
        f"How {trend_title} Is Changing Everything in 2025",
        f"I Tested {trend_title} for 30 Days — Here's What Happened",
        f"The Ultimate Guide to {trend_title} (Nobody Talks About This)",
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def discover_trends(
    videos: List[Dict[str, Any]],
    min_count: int = 2,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Full trend discovery pipeline: cluster → score → sort → limit.

    Returns scored trend clusters sorted by trend_score descending.
    """
    cache_key = f"trends_{len(videos)}_{min_count}_{limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug("Returning cached trends (%d clusters).", len(cached))
        return cached

    clusters = build_trend_clusters(videos)
    # Filter by minimum count
    clusters = [c for c in clusters if c["count"] >= min_count]
    # Score each cluster
    clusters = [score_trend(c) for c in clusters]
    # Sort by trend_score
    clusters.sort(key=lambda c: c["trend_score"], reverse=True)
    # Limit
    result = clusters[:limit]

    _set_cached(cache_key, result)
    logger.info("Discovered %d trends from %d videos.", len(result), len(videos))
    return result


def discover_opportunities(
    videos: List[Dict[str, Any]],
    min_count: int = 1,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """
    Full opportunity pipeline: cluster → score → opportunity → sort.

    Returns opportunities sorted by opportunity_score descending.
    """
    cache_key = f"opportunities_{len(videos)}_{min_count}_{limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug("Returning cached opportunities (%d).", len(cached))
        return cached

    clusters = build_trend_clusters(videos)
    clusters = [c for c in clusters if c["count"] >= min_count]
    clusters = [score_trend(c) for c in clusters]
    clusters = [compute_opportunity(c) for c in clusters]
    clusters.sort(key=lambda c: c["opportunity_score"], reverse=True)

    # Generate suggested titles for top opportunities
    for cluster in clusters[:5]:
        cluster["suggested_titles"] = generate_suggested_titles(cluster)

    result = clusters[:limit]
    _set_cached(cache_key, result)
    logger.info("Discovered %d opportunities from %d videos.", len(result), len(videos))
    return result
