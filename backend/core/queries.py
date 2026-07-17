"""
Query module for Content Intelligence Platform.

Provides high-level, typed query functions against the videos database.
Each function returns a list of dicts suitable for API serialization.
"""

from __future__ import annotations

import logging
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
    platform: Optional[str] = None,
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
    if platform:
        conditions.append("LOWER(platform) = ?")
        params.append(platform.lower())

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


# ---------------------------------------------------------------------------
# Reddit intelligence queries
# ---------------------------------------------------------------------------
_REDDIT_SENTIMENTS = {"positive", "neutral", "negative", "mixed"}


def _json_object(value: Any) -> Dict[str, Any]:
    """Parse persisted JSON defensively; historical rows may not have it."""
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item).strip() for item in parsed if str(item).strip()] if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _reddit_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _reddit_record(row: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _json_object(row.get("platform_metadata"))
    insights = _json_object(row.get("reddit_insights"))
    created = _reddit_datetime(row.get("published_at"))
    age_hours = max((datetime.now(timezone.utc) - created).total_seconds() / 3600, 1.0) if created else None
    upvotes = int(metadata.get("upvotes", row.get("likes", 0)) or 0)
    comments = int(row.get("comments", 0) or 0)
    ratio = metadata.get("upvote_ratio")
    try:
        upvote_ratio = min(max(float(ratio), 0.0), 1.0) if ratio is not None else None
    except (TypeError, ValueError):
        upvote_ratio = None
    sentiment = insights.get("sentiment")
    sentiment = sentiment if sentiment in _REDDIT_SENTIMENTS else None
    raw_opportunity = insights.get("opportunity_score")
    try:
        opportunity_score = max(0, min(100, int(raw_opportunity))) if raw_opportunity is not None else round(float(row.get("score", 0)) * 100)
    except (TypeError, ValueError):
        opportunity_score = None
    topics = _json_list(row.get("topics"))
    cluster = insights.get("cluster") or (topics[0] if topics else None)
    subreddit = str(metadata.get("subreddit", "")).removeprefix("r/").strip() or None
    author = str(metadata.get("author", row.get("channel", ""))).strip() or None
    return {
        "id": row.get("video_id", ""),
        "title": row.get("title", ""),
        "body": row.get("description", ""),
        "subreddit": subreddit,
        "author": author,
        "upvotes": upvotes,
        "comments": comments,
        "upvote_ratio": upvote_ratio,
        "flair": metadata.get("flair") or None,
        "created_at": row.get("published_at") or None,
        "source_url": row.get("source_url") or metadata.get("permalink") or None,
        "thumbnail_url": row.get("thumbnail_url") or None,
        "score": float(row.get("score", 0) or 0),
        "velocity": round((upvotes + comments) / age_hours, 2) if age_hours else None,
        "sentiment": sentiment,
        "analysis_status": insights.get("analysis_status", "pending"),
        "pain_points": [str(item) for item in insights.get("pain_points", []) if str(item).strip()][:3],
        "cluster": str(cluster).strip() if cluster else None,
        "topics": topics,
        "opportunity_score": opportunity_score,
        "opportunity_source": "enrichment" if raw_opportunity is not None else "engagement_model",
        "updated_at": row.get("updated_at") or None,
    }


def _reddit_rows(
    days: int = 30,
    pipeline_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    conditions = ["platform = 'reddit'"]
    params: list[Any] = []
    if pipeline_run_id is not None:
        conditions.append("pipeline_run_id = ?")
        params.append(pipeline_run_id)
    if days:
        conditions.append("(published_at IS NULL OR published_at = '' OR published_at >= datetime('now', ?))")
        params.append(f"-{days} days")
    query = f"""
        SELECT video_id, title, description, channel, likes, comments, score,
               published_at, thumbnail_url, topics, source_url,
               platform_metadata, reddit_insights, updated_at
        FROM videos
        WHERE {' AND '.join(conditions)}
        ORDER BY published_at DESC, score DESC
        LIMIT 3000;
    """
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_reddit_record(dict(row)) for row in rows]


def get_reddit_discussions(
    *, days: int = 30, limit: int = 50, pipeline_run_id: Optional[int] = None,
    search: Optional[str] = None, subreddit: Optional[str] = None,
    sentiment: Optional[str] = None, min_upvotes: int = 0, min_comments: int = 0,
    min_opportunity: int = 0, sort_by: str = "velocity",
) -> List[Dict[str, Any]]:
    records = _reddit_rows(days, pipeline_run_id)
    term = (search or "").strip().lower()
    requested_subreddit = (subreddit or "").removeprefix("r/").strip().lower()
    requested_sentiment = (sentiment or "").strip().lower()
    filtered = []
    for record in records:
        haystack = " ".join([
            record.get("title") or "", record.get("body") or "", record.get("author") or "",
            record.get("subreddit") or "", " ".join(record.get("topics") or []), record.get("cluster") or "",
        ]).lower()
        if term and term not in haystack:
            continue
        if requested_subreddit and (record.get("subreddit") or "").lower() != requested_subreddit:
            continue
        if requested_sentiment and record.get("sentiment") != requested_sentiment:
            continue
        if record.get("upvotes", 0) < min_upvotes or record.get("comments", 0) < min_comments:
            continue
        if (record.get("opportunity_score") or 0) < min_opportunity:
            continue
        filtered.append(record)
    sorters = {
        "engagement": lambda item: item.get("upvotes", 0) + item.get("comments", 0),
        "recency": lambda item: _reddit_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        "opportunity": lambda item: item.get("opportunity_score") or 0,
        "velocity": lambda item: item.get("velocity") or 0,
    }
    filtered.sort(key=sorters.get(sort_by, sorters["velocity"]), reverse=True)
    return filtered[:max(1, min(limit, 100))]


def get_reddit_overview(days: int = 30, pipeline_run_id: Optional[int] = None) -> Dict[str, Any]:
    records = _reddit_rows(days, pipeline_run_id)
    known_subreddits = {item["subreddit"] for item in records if item.get("subreddit")}
    ratios = [item["upvote_ratio"] for item in records if item.get("upvote_ratio") is not None]
    opportunities = [item["opportunity_score"] for item in records if item.get("opportunity_score") is not None]
    topic_velocity: Dict[str, List[float]] = defaultdict(list)
    for item in records:
        for topic in ([item.get("cluster")] if item.get("cluster") else item.get("topics", [])):
            if topic:
                topic_velocity[topic].append(item.get("velocity") or 0)
    fastest_topic = None
    if topic_velocity:
        topic, velocities = max(topic_velocity.items(), key=lambda pair: sum(pair[1]) / len(pair[1]))
        fastest_topic = {"name": topic, "velocity": round(sum(velocities) / len(velocities), 2)}
    latest = max((item.get("updated_at") for item in records if item.get("updated_at")), default=None)
    analyzed = sum(1 for item in records if item.get("analysis_status") == "complete")
    return {
        "days": days,
        "posts_analyzed": len(records),
        "active_subreddits": len(known_subreddits),
        "total_comments": sum(item.get("comments", 0) for item in records),
        "avg_upvote_ratio": round(sum(ratios) / len(ratios), 4) if ratios else None,
        "fastest_growing_topic": fastest_topic,
        "opportunity_score": round(sum(opportunities) / len(opportunities)) if opportunities else None,
        "analysis_coverage": round((analyzed / len(records)) * 100, 1) if records else 0.0,
        "last_indexed_at": latest,
    }


def get_trending_subreddits(days: int = 30, limit: int = 8, pipeline_run_id: Optional[int] = None) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in _reddit_rows(days, pipeline_run_id):
        if record.get("subreddit"):
            groups[record["subreddit"]].append(record)
    result = []
    for name, records in groups.items():
        topics = Counter(topic for record in records for topic in record.get("topics", [])).most_common(3)
        result.append({
            "name": name,
            "member_count": None,
            "posts": len(records),
            "comments": sum(record.get("comments", 0) for record in records),
            "momentum": round(sum(record.get("velocity") or 0 for record in records), 2),
            "topics": [topic for topic, _ in topics],
            "activity": [sum(1 for record in records if (_reddit_datetime(record.get("created_at")) and (datetime.now(timezone.utc) - _reddit_datetime(record.get("created_at"))).days == offset)) for offset in range(6, -1, -1)],
        })
    result.sort(key=lambda item: item["momentum"], reverse=True)
    return result[:max(1, min(limit, 20))]


def get_reddit_pain_points(days: int = 30, limit: int = 10, pipeline_run_id: Optional[int] = None) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for record in _reddit_rows(days, pipeline_run_id):
        for statement in record.get("pain_points", []):
            key = statement.strip().lower()
            if not key:
                continue
            group = groups.setdefault(key, {"statement": statement.strip(), "mentions": 0, "subreddits": set(), "sentiments": [], "opportunities": [], "post_ids": []})
            group["mentions"] += 1
            if record.get("subreddit"):
                group["subreddits"].add(record["subreddit"])
            if record.get("sentiment"):
                group["sentiments"].append(record["sentiment"])
            if record.get("opportunity_score") is not None:
                group["opportunities"].append(record["opportunity_score"])
            group["post_ids"].append(record["id"])
    result = []
    for group in groups.values():
        result.append({
            "statement": group["statement"], "mentions": group["mentions"],
            "subreddits": sorted(group["subreddits"]),
            "sentiment": Counter(group["sentiments"]).most_common(1)[0][0] if group["sentiments"] else None,
            "opportunity_score": round(sum(group["opportunities"]) / len(group["opportunities"])) if group["opportunities"] else None,
            "post_ids": group["post_ids"][:10],
        })
    result.sort(key=lambda item: (item["mentions"], item["opportunity_score"] or 0), reverse=True)
    return result[:max(1, min(limit, 30))]


def get_reddit_clusters(days: int = 30, limit: int = 10, pipeline_run_id: Optional[int] = None) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in _reddit_rows(days, pipeline_run_id):
        names = [record["cluster"]] if record.get("cluster") else record.get("topics", [])
        for name in names:
            if name:
                groups[str(name)].append(record)
    result = []
    for name, records in groups.items():
        keywords = Counter(topic for record in records for topic in record.get("topics", []) if topic != name).most_common(4)
        result.append({
            "name": name, "post_count": len(records),
            "momentum": round(sum(record.get("velocity") or 0 for record in records), 2),
            "keywords": [keyword for keyword, _ in keywords],
            "subreddits": sorted({record["subreddit"] for record in records if record.get("subreddit")})[:4],
            "sentiment": dict(Counter(record["sentiment"] for record in records if record.get("sentiment"))),
        })
    result.sort(key=lambda item: item["momentum"], reverse=True)
    return result[:max(1, min(limit, 30))]


def get_reddit_sentiment(days: int = 30, pipeline_run_id: Optional[int] = None) -> Dict[str, Any]:
    records = _reddit_rows(days, pipeline_run_id)
    counts = Counter(record["sentiment"] for record in records if record.get("sentiment") in _REDDIT_SENTIMENTS)
    total = sum(counts.values())
    return {
        "total_analyzed": total,
        "coverage": round((total / len(records)) * 100, 1) if records else 0.0,
        "distribution": [{"label": label, "count": counts.get(label, 0), "percent": round((counts.get(label, 0) / total) * 100, 1) if total else 0.0} for label in ("positive", "neutral", "negative", "mixed")],
    }


def get_reddit_opportunities(days: int = 30, limit: int = 10, pipeline_run_id: Optional[int] = None) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in _reddit_rows(days, pipeline_run_id):
        name = record.get("cluster") or (record.get("topics") or [None])[0]
        if name:
            groups[str(name)].append(record)
    result = []
    for name, records in groups.items():
        scores = [record["opportunity_score"] for record in records if record.get("opportunity_score") is not None]
        result.append({
            "niche": name,
            "opportunity_score": round(sum(scores) / len(scores)) if scores else None,
            "momentum": round(sum(record.get("velocity") or 0 for record in records), 2),
            "communities": len({record["subreddit"] for record in records if record.get("subreddit")}),
        })
    result.sort(key=lambda item: ((item["opportunity_score"] or 0), item["momentum"]), reverse=True)
    return result[:max(1, min(limit, 30))]


def get_reddit_contributors(days: int = 30, limit: int = 10, pipeline_run_id: Optional[int] = None) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in _reddit_rows(days, pipeline_run_id):
        author = record.get("author")
        if author and author.lower() not in {"[deleted]", "deleted"}:
            groups[author].append(record)
    result = []
    for author, records in groups.items():
        result.append({
            "username": author, "post_count": len(records),
            "comment_count": sum(record.get("comments", 0) for record in records),
            "momentum": round(sum(record.get("velocity") or 0 for record in records), 2),
            "subreddit": Counter(record.get("subreddit") for record in records if record.get("subreddit")).most_common(1)[0][0] if any(record.get("subreddit") for record in records) else None,
        })
    result.sort(key=lambda item: (item["post_count"], item["momentum"]), reverse=True)
    return result[:max(1, min(limit, 30))]

