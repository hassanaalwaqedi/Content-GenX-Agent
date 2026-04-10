"""
Query module for Content Intelligence Platform.

Provides high-level, typed query functions against the videos database.
Each function returns a list of dicts suitable for API serialization.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database import get_connection

logger = logging.getLogger(__name__)


def get_top_videos_per_niche(
    niche: str,
    days: int = 30,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return top-scoring videos for a given *niche* published within the last
    *days* days, ordered by score descending.
    """
    query = """
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            target_audience, strategic_advice, content_gap
        FROM videos
        WHERE niche = ?
          AND published_at >= datetime('now', ?)
        ORDER BY score DESC
        LIMIT ?;
    """
    modifier = f"-{days} days"

    with get_connection() as conn:
        rows = conn.execute(query, (niche, modifier, limit)).fetchall()

    results = [dict(r) for r in rows]
    logger.info(
        "get_top_videos_per_niche(niche='%s', days=%d): %d results",
        niche,
        days,
        len(results),
    )
    return results


def get_fastest_growing_videos(
    days: int = 7,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return videos with the highest engagement rates published within
    the last *days* days. These represent "fastest growing" content.

    Heuristic: engagement_rate × log(views) gives a balanced signal
    between raw virality and actual reach.
    """
    query = """
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            target_audience, strategic_advice, content_gap
        FROM videos
        WHERE published_at >= datetime('now', ?)
        ORDER BY (engagement_rate * score) DESC
        LIMIT ?;
    """
    modifier = f"-{days} days"

    with get_connection() as conn:
        rows = conn.execute(query, (modifier, limit)).fetchall()

    results = [dict(r) for r in rows]
    logger.info(
        "get_fastest_growing_videos(days=%d): %d results", days, len(results)
    )
    return results


def get_top_creators(
    limit: int = 20,
    min_videos: int = 2,
) -> List[Dict[str, Any]]:
    """
    Aggregate creators by total score, average engagement, and video count.
    Only includes creators with at least *min_videos* in the database.
    """
    query = """
        SELECT
            channel,
            COUNT(*)            AS video_count,
            SUM(views)          AS total_views,
            ROUND(AVG(engagement_rate), 6) AS avg_engagement_rate,
            ROUND(AVG(score), 6)           AS avg_score,
            ROUND(SUM(score), 6)           AS total_score
        FROM videos
        WHERE channel != ''
        GROUP BY channel
        HAVING COUNT(*) >= ?
        ORDER BY total_score DESC
        LIMIT ?;
    """

    with get_connection() as conn:
        rows = conn.execute(query, (min_videos, limit)).fetchall()

    results = [dict(r) for r in rows]
    logger.info("get_top_creators(limit=%d): %d results", limit, len(results))
    return results


def get_video_stats() -> Dict[str, Any]:
    """
    Return aggregate statistics for the entire database:
    total videos, niches, average score, etc.  Includes per-niche and per-platform breakdown.
    """
    query = """
        SELECT
            COUNT(*)                        AS total_videos,
            COUNT(DISTINCT niche)           AS total_niches,
            COUNT(DISTINCT channel)         AS total_channels,
            ROUND(AVG(score), 4)            AS avg_score,
            ROUND(AVG(engagement_rate), 6)  AS avg_engagement_rate,
            MAX(score)                      AS max_score,
            MIN(published_at)              AS earliest_video,
            MAX(published_at)              AS latest_video
        FROM videos;
    """
    niche_query = """
        SELECT niche,
               COUNT(*) AS count,
               ROUND(AVG(score), 4) AS avg_score,
               ROUND(AVG(engagement_rate), 6) AS avg_engagement
        FROM videos
        GROUP BY niche
        ORDER BY count DESC;
    """
    platform_query = """
        SELECT platform, COUNT(*) AS count
        FROM videos
        GROUP BY platform
        ORDER BY count DESC;
    """
    with get_connection() as conn:
        row = conn.execute(query).fetchone()
        niche_rows = conn.execute(niche_query).fetchall()
        platform_rows = conn.execute(platform_query).fetchall()

    result = dict(row) if row else {}
    result["niche_stats"] = {
        r["niche"]: {"count": r["count"], "avg_score": r["avg_score"], "avg_engagement": r["avg_engagement"]}
        for r in niche_rows
    }
    result["platform_stats"] = {r["platform"]: r["count"] for r in platform_rows}
    return result


def get_video_by_id(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Return full details for a single video by its YouTube video ID.

    Returns None if the video is not found.
    """
    query = """
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            description, target_audience, strategic_advice, content_gap,
            transcript, created_at, updated_at
        FROM videos
        WHERE video_id = ?;
    """
    with get_connection() as conn:
        row = conn.execute(query, (video_id,)).fetchone()

    if row:
        result = dict(row)
        logger.info("get_video_by_id('%s'): found.", video_id)
        return result

    logger.info("get_video_by_id('%s'): not found.", video_id)
    return None


def get_transcript_stats() -> Dict[str, Any]:
    """
    Return transcript coverage statistics.

    Provides counts of videos with/without transcripts,
    coverage percentage, and per-niche breakdown.
    """
    query = """
        SELECT
            COUNT(*) AS total_youtube,
            COALESCE(SUM(CASE WHEN transcript IS NOT NULL AND transcript != '' THEN 1 ELSE 0 END), 0) AS with_transcript,
            COALESCE(SUM(CASE WHEN transcript IS NULL OR transcript = '' THEN 1 ELSE 0 END), 0) AS without_transcript,
            CASE WHEN COUNT(*) > 0 THEN
                ROUND(
                    100.0 * COALESCE(SUM(CASE WHEN transcript IS NOT NULL AND transcript != '' THEN 1 ELSE 0 END), 0) / COUNT(*),
                    1
                )
            ELSE 0.0 END AS coverage_pct
        FROM videos
        WHERE platform = 'youtube';
    """
    niche_query = """
        SELECT
            niche,
            COUNT(*) AS total,
            SUM(CASE WHEN transcript IS NOT NULL AND transcript != '' THEN 1 ELSE 0 END) AS with_transcript
        FROM videos
        WHERE platform = 'youtube'
        GROUP BY niche
        ORDER BY total DESC;
    """

    with get_connection() as conn:
        row = conn.execute(query).fetchone()
        niche_rows = conn.execute(niche_query).fetchall()

    result = dict(row) if row else {
        "total_youtube": 0,
        "with_transcript": 0,
        "without_transcript": 0,
        "coverage_pct": 0.0,
    }
    result["niche_breakdown"] = [
        {
            "niche": r["niche"],
            "total": r["total"],
            "with_transcript": r["with_transcript"],
        }
        for r in niche_rows
    ]
    return result
