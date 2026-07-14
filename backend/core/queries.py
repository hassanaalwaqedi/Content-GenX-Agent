"""
Query module for Content Intelligence Platform.

Provides high-level, typed query functions against the videos database.
Each function returns a list of dicts suitable for API serialization.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.database import get_connection

logger = logging.getLogger(__name__)


def get_top_videos_per_niche(
    niche: Optional[str] = None,
    days: int = 30,
    limit: int = 20,
    region: Optional[str] = None,
    category: Optional[str] = None,
    content_type: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return top-scoring videos with optional filters for region, category, content_type.
    When pipeline_run_id is set, scopes to that dataset only.
    """
    modifier = f"-{days} days"
    conditions = ["published_at >= datetime('now', ?)"]
    params: list = [modifier]

    if pipeline_run_id is not None:
        conditions.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)
    if niche:
        conditions.append("niche = ?")
        params.append(niche)
    if region:
        conditions.append("source_region = ?")
        params.append(region)
    if category:
        conditions.append("niche = ?")
        params.append(category)
    if content_type and content_type != "all":
        conditions.append("content_type = ?")
        params.append(content_type)

    where = " AND ".join(conditions)
    query = f"""
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            target_audience, strategic_advice, content_gap,
            source_region, content_type
        FROM videos
        WHERE {where}
        ORDER BY score DESC
        LIMIT ?;
    """
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = [dict(r) for r in rows]
    logger.info(
        "get_top_videos_per_niche(niche=%s, run_id=%s, days=%d): %d results",
        niche or "ALL", pipeline_run_id, days, len(results),
    )
    return results


def get_fastest_growing_videos(
    days: int = 7,
    limit: int = 20,
    region: Optional[str] = None,
    category: Optional[str] = None,
    content_type: Optional[str] = None,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return fastest-growing videos with optional filters.
    """
    modifier = f"-{days} days"
    conditions = ["published_at >= datetime('now', ?)"]
    params: list = [modifier]

    if pipeline_run_id is not None:
        conditions.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)
    if region:
        conditions.append("source_region = ?")
        params.append(region)
    if category:
        conditions.append("niche = ?")
        params.append(category)
    if content_type and content_type != "all":
        conditions.append("content_type = ?")
        params.append(content_type)

    where = " AND ".join(conditions)
    query = f"""
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            target_audience, strategic_advice, content_gap,
            source_region, content_type
        FROM videos
        WHERE {where}
        ORDER BY (engagement_rate * score) DESC
        LIMIT ?;
    """
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = [dict(r) for r in rows]
    logger.info("get_fastest_growing_videos(days=%d, run_id=%s): %d results", days, pipeline_run_id, len(results))
    return results


def get_top_creators(
    limit: int = 20,
    min_videos: int = 2,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregate creators by total score, average engagement, and video count.
    Only includes creators with at least *min_videos* in the database.
    """
    run_filter = "AND pipeline_run_id = ?" if pipeline_run_id is not None else ""
    query = f"""
        SELECT
            channel,
            COUNT(*)            AS video_count,
            SUM(views)          AS total_views,
            ROUND(AVG(engagement_rate), 6) AS avg_engagement_rate,
            ROUND(AVG(score), 6)           AS avg_score,
            ROUND(SUM(score), 6)           AS total_score
        FROM videos
        WHERE channel != '' {run_filter}
        GROUP BY channel
        HAVING COUNT(*) >= ?
        ORDER BY total_score DESC
        LIMIT ?;
    """
    params = (pipeline_run_id, min_videos, limit) if pipeline_run_id is not None else (min_videos, limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = [dict(r) for r in rows]
    logger.info("get_top_creators(limit=%d, run_id=%s): %d results", limit, pipeline_run_id, len(results))
    return results


def get_creator_intelligence(
    days: int = 365,
    limit: int = 30,
    min_videos: int = 1,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Compute full intelligence metrics for each creator:
    trend_dominance_score, top_topics, recent_velocity, opportunity_alignment.
    """
    import json as _json
    modifier = f"-{days} days"
    run_filter = "AND pipeline_run_id = ?" if pipeline_run_id is not None else ""

    # 1. Get base creator aggregates
    base_query = f"""
        SELECT
            channel,
            COUNT(*)                        AS video_count,
            SUM(views)                      AS total_views,
            ROUND(AVG(engagement_rate), 6)  AS avg_engagement,
            ROUND(AVG(score), 6)            AS avg_score,
            ROUND(SUM(score), 6)            AS total_score,
            MAX(published_at)               AS latest_video
        FROM videos
        WHERE channel != ''
          AND published_at >= datetime('now', ?) {run_filter}
        GROUP BY channel
        HAVING COUNT(*) >= ?
        ORDER BY total_score DESC
        LIMIT ?;
    """
    base_params = [modifier]
    if pipeline_run_id is not None:
        base_params.append(pipeline_run_id)
    base_params.extend([min_videos, limit])
    with get_connection() as conn:
        creators = [dict(r) for r in conn.execute(base_query, base_params).fetchall()]

        if not creators:
            return []

        channel_names = [c["channel"] for c in creators]
        placeholders = ",".join("?" * len(channel_names))

        # 2. Get topics per creator for top_topics
        topics_query = f"""
            SELECT channel, topics
            FROM videos
            WHERE channel IN ({placeholders})
              AND topics IS NOT NULL AND topics != ''
              AND published_at >= datetime('now', ?);
        """
        topic_rows = conn.execute(topics_query, (*channel_names, modifier)).fetchall()

        # 3. Get recent velocity (7-day avg vs 30-day avg)
        velocity_query = f"""
            SELECT channel,
                   ROUND(AVG(CASE WHEN published_at >= datetime('now', '-7 days') THEN score END), 6) AS avg_7d,
                   ROUND(AVG(CASE WHEN published_at >= datetime('now', '-30 days') THEN score END), 6) AS avg_30d
            FROM videos
            WHERE channel IN ({placeholders})
            GROUP BY channel;
        """
        velocity_rows = conn.execute(velocity_query, channel_names).fetchall()

        # 4. Get top-scoring videos globally (for trend dominance)
        top_filter = "AND pipeline_run_id = ?" if pipeline_run_id is not None else ""
        top_params = [modifier]
        if pipeline_run_id is not None:
            top_params.append(pipeline_run_id)
        top_global = conn.execute(f"""
            SELECT video_id, channel, score
            FROM videos
            WHERE published_at >= datetime('now', ?) {top_filter}
            ORDER BY score DESC
            LIMIT 100;
        """, top_params).fetchall()

    # Build topic frequency per creator
    from collections import Counter
    creator_topics: Dict[str, Counter] = {c["channel"]: Counter() for c in creators}
    for row in topic_rows:
        ch = row["channel"]
        if ch not in creator_topics:
            continue
        try:
            parsed = _json.loads(row["topics"])
            if isinstance(parsed, list):
                for t in parsed:
                    if isinstance(t, str) and t.strip():
                        creator_topics[ch][t.strip().lower()] += 1
        except (ValueError, TypeError):
            pass

    # Build velocity map
    velocity_map: Dict[str, float] = {}
    for row in velocity_rows:
        avg_7 = row["avg_7d"] or 0
        avg_30 = row["avg_30d"] or 0
        velocity_map[row["channel"]] = round(avg_7 - avg_30, 4)

    # Build trend dominance (% of top 100 global videos that belong to this creator)
    top100_channels = [r["channel"] for r in top_global]
    total_top = max(len(top100_channels), 1)
    dominance_map: Dict[str, float] = {}
    for ch in channel_names:
        count_in_top = sum(1 for c in top100_channels if c == ch)
        dominance_map[ch] = round(count_in_top / total_top, 4)

    # Build opportunity alignment (how many of their topics overlap with high-scoring topics)
    # Get global high-score topics
    global_top_topics: Counter = Counter()
    for row in topic_rows:
        try:
            parsed = _json.loads(row["topics"])
            if isinstance(parsed, list):
                for t in parsed:
                    if isinstance(t, str) and t.strip():
                        global_top_topics[t.strip().lower()] += 1
        except (ValueError, TypeError):
            pass
    top_trending_topics = set(t for t, _ in global_top_topics.most_common(20))

    # Enrich creators
    for c in creators:
        ch = c["channel"]
        topics_counter = creator_topics.get(ch, Counter())
        c["top_topics"] = [t for t, _ in topics_counter.most_common(5)]
        c["recent_velocity"] = velocity_map.get(ch, 0.0)
        c["trend_dominance_score"] = dominance_map.get(ch, 0.0)

        # Opportunity alignment: overlap of creator topics with trending topics
        if topics_counter and top_trending_topics:
            creator_top = set(t for t, _ in topics_counter.most_common(10))
            overlap = len(creator_top & top_trending_topics)
            c["opportunity_alignment"] = round(overlap / max(len(creator_top), 1), 4)
        else:
            c["opportunity_alignment"] = 0.0

    logger.info("get_creator_intelligence(days=%d): %d creators", days, len(creators))
    return creators


def get_rising_creators(
    days: int = 30,
    limit: int = 10,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Find rising creators: high recent velocity, good engagement, relatively few videos.
    """
    run_filter = "AND pipeline_run_id = ?" if pipeline_run_id is not None else ""
    query = f"""
        SELECT
            channel,
            COUNT(*) AS video_count,
            SUM(views) AS total_views,
            ROUND(AVG(engagement_rate), 6) AS avg_engagement,
            ROUND(AVG(score), 6) AS avg_score,
            ROUND(AVG(CASE WHEN published_at >= datetime('now', '-7 days') THEN score END), 6) AS avg_7d,
            ROUND(AVG(CASE WHEN published_at >= datetime('now', '-30 days') THEN score END), 6) AS avg_30d
        FROM videos
        WHERE channel != ''
          AND published_at >= datetime('now', ?) {run_filter}
        GROUP BY channel
        HAVING COUNT(*) >= 1
        ORDER BY (COALESCE(avg_7d, 0) - COALESCE(avg_30d, 0)) DESC
        LIMIT ?;
    """
    modifier = f"-{days} days"
    params = [modifier]
    if pipeline_run_id is not None:
        params.append(pipeline_run_id)
    params.append(limit * 3)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        avg_7 = d.get("avg_7d") or 0
        avg_30 = d.get("avg_30d") or 0
        d["recent_velocity"] = round(avg_7 - avg_30, 4)
        results.append(d)

    # Sort by velocity descending, take top
    results.sort(key=lambda x: x["recent_velocity"], reverse=True)
    results = results[:limit]
    logger.info("get_rising_creators(days=%d): %d results", days, len(results))
    return results


def get_creators_by_trend(
    trend: str,
    days: int = 365,
    limit: int = 20,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Find creators whose video topics match a given trend keyword.
    """
    modifier = f"-{days} days"
    pattern = f"%{trend.lower()}%"
    run_filter = "AND pipeline_run_id = ?" if pipeline_run_id is not None else ""

    query = f"""
        SELECT
            channel,
            COUNT(*) AS video_count,
            SUM(views) AS total_views,
            ROUND(AVG(engagement_rate), 6) AS avg_engagement,
            ROUND(AVG(score), 6) AS avg_score,
            ROUND(SUM(score), 6) AS total_score
        FROM videos
        WHERE channel != ''
          AND published_at >= datetime('now', ?)
          AND (LOWER(topics) LIKE ? OR LOWER(niche) LIKE ? OR LOWER(title) LIKE ?) {run_filter}
        GROUP BY channel
        ORDER BY total_score DESC
        LIMIT ?;
    """
    params = [modifier, pattern, pattern, pattern]
    if pipeline_run_id is not None:
        params.append(pipeline_run_id)
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = [dict(r) for r in rows]
    logger.info("get_creators_by_trend(trend=%s, run_id=%s): %d results", trend, pipeline_run_id, len(results))
    return results


def get_creator_videos(
    channel: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Return top videos for a specific creator/channel."""
    query = """
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            target_audience, strategic_advice, content_gap
        FROM videos
        WHERE channel = ?
        ORDER BY score DESC
        LIMIT ?;
    """
    with get_connection() as conn:
        rows = conn.execute(query, (channel, limit)).fetchall()

    results = [dict(r) for r in rows]
    logger.info("get_creator_videos(channel=%s): %d results", channel, len(results))
    return results


def get_video_stats(
    pipeline_run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Return aggregate statistics. When pipeline_run_id is set, scopes to that dataset.
    """
    run_filter = "WHERE pipeline_run_id = ?" if pipeline_run_id is not None else ""
    run_filter_and = "AND pipeline_run_id = ?" if pipeline_run_id is not None else ""
    base_params = (pipeline_run_id,) if pipeline_run_id is not None else ()

    query = f"""
        SELECT
            COUNT(*)                        AS total_videos,
            COUNT(DISTINCT niche)           AS total_niches,
            COUNT(DISTINCT channel)         AS total_channels,
            ROUND(AVG(score), 4)            AS avg_score,
            ROUND(AVG(engagement_rate), 6)  AS avg_engagement_rate,
            MAX(score)                      AS max_score,
            MIN(published_at)              AS earliest_video,
            MAX(published_at)              AS latest_video
        FROM videos
        {run_filter};
    """
    niche_query = f"""
        SELECT niche,
               COUNT(*) AS count,
               ROUND(AVG(score), 4) AS avg_score,
               ROUND(AVG(engagement_rate), 6) AS avg_engagement
        FROM videos
        {'WHERE pipeline_run_id = ?' if pipeline_run_id is not None else ''}
        GROUP BY niche
        ORDER BY count DESC;
    """
    platform_query = f"""
        SELECT platform, COUNT(*) AS count
        FROM videos
        {'WHERE pipeline_run_id = ?' if pipeline_run_id is not None else ''}
        GROUP BY platform
        ORDER BY count DESC;
    """
    with get_connection() as conn:
        row = conn.execute(query, base_params).fetchone()
        niche_rows = conn.execute(niche_query, base_params).fetchall()
        platform_rows = conn.execute(platform_query, base_params).fetchall()

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


def get_transcript_by_video_id(video_id: str) -> Optional[str]:
    """
    Return the transcript text for a video, or None if the video is not found.
    Returns empty string if the video exists but has no transcript.
    """
    query = "SELECT transcript FROM videos WHERE video_id = ?;"
    with get_connection() as conn:
        row = conn.execute(query, (video_id,)).fetchone()
    if row is None:
        return None
    return row["transcript"] or ""


def update_transcript(video_id: str, transcript: str) -> bool:
    """
    Update the transcript for a video. Returns True if the video was found and updated.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE videos SET transcript = ?, updated_at = ? WHERE video_id = ?;",
            (transcript, now, video_id),
        )
    updated = cursor.rowcount > 0
    if updated:
        logger.info("Transcript updated for video '%s' (%d chars).", video_id, len(transcript))
    return updated


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


def get_videos_with_topics(
    days: int = 30,
    limit: int = 500,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return videos with topic data for trend analysis.
    When pipeline_run_id is set, scopes to that dataset.
    """
    conditions = ["published_at >= datetime('now', ?)"]
    params: list = [f"-{days} days"]

    if pipeline_run_id is not None:
        conditions.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)

    where = " AND ".join(conditions)
    query = f"""
        SELECT
            video_id, platform, niche, title, views, likes, comments,
            engagement_rate, score, published_at, channel, thumbnail_url,
            target_audience, strategic_advice, content_gap, topics
        FROM videos
        WHERE {where}
        ORDER BY score DESC
        LIMIT ?;
    """
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    results = [dict(r) for r in rows]
    logger.info(
        "get_videos_with_topics(days=%d, run_id=%s): %d results", days, pipeline_run_id, len(results)
    )
    return results

