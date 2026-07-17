"""
Ingestion module for Content Intelligence Platform.

Fetches **globally trending** videos from YouTube Data API v3 using
the `videos.list(chart=mostPopular)` endpoint across curated regions
— eliminating ALL niche-based query bias.

Features:
  - Multi-region trending video ingestion (India excluded)
  - User-configurable pipeline configs (regions, categories, keywords, content_type)
  - Hybrid mode: trending + keyword search combined
  - Content type filtering (shorts < 60s, long > 60s, all)
  - Category filtering by YouTube categoryId
  - Automatic deduplication (keeps highest-view version)
  - Failsafe retry with exponential back-off
  - Structured return objects (dataclasses)
  - Auto-categorization from YouTube categoryId
  - Stale data cleanup before ingestion
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Curated regions — India (IN) excluded to reduce noise/irrelevant content
ALLOWED_REGIONS = ["US", "GB", "CA", "DE", "FR", "AU", "AE"]

# YouTube video category ID → readable label
YOUTUBE_CATEGORY_MAP = {
    "1": "film & animation",
    "2": "autos & vehicles",
    "10": "music",
    "15": "pets & animals",
    "17": "sports",
    "18": "short movies",
    "19": "travel & events",
    "20": "gaming",
    "21": "videoblogging",
    "22": "people & blogs",
    "23": "comedy",
    "24": "entertainment",
    "25": "news & politics",
    "26": "howto & style",
    "27": "education",
    "28": "science & technology",
    "29": "nonprofits & activism",
    "30": "movies",
    "43": "shows",
}

# Max retry attempts for transient YouTube API failures
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2

# Reverse map: readable label → YouTube category ID (for filtering)
CATEGORY_LABEL_TO_ID = {v: k for k, v in YOUTUBE_CATEGORY_MAP.items()}


# ---------------------------------------------------------------------------
# Pipeline Config (user-configurable)
# ---------------------------------------------------------------------------
@dataclass
class PipelineConfig:
    """User-defined pipeline configuration passed through the ingestion layer."""
    regions: List[str] = field(default_factory=lambda: list(ALLOWED_REGIONS))
    platforms: List[str] = field(default_factory=lambda: ["youtube"])
    categories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    content_type: str = "all"  # "shorts", "long", "all"

    @staticmethod
    def from_dict(d: Optional[Dict[str, Any]]) -> "PipelineConfig":
        if not d:
            return PipelineConfig()
        return PipelineConfig(
            regions=d.get("regions") or list(ALLOWED_REGIONS),
            platforms=d.get("platforms") or ["youtube"],
            categories=[c.lower().strip() for c in (d.get("categories") or [])],
            keywords=[k.strip() for k in (d.get("keywords") or []) if k.strip()],
            content_type=d.get("content_type", "all"),
        )


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class RawVideo:
    """Represents a single video as returned by the ingestion layer."""

    video_id: str
    title: str
    channel: str
    description: str
    published_at: str
    thumbnail_url: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    niche: str = ""
    platform: str = "youtube"
    source_region: str = ""
    content_type: str = "all"
    source_url: str = ""
    platform_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# YouTube API client
# ---------------------------------------------------------------------------
class YouTubeClient:
    """
    Thin abstraction over the YouTube Data API v3.

    Handles:
      - Session management with connection pooling
      - Retry with exponential back-off on transient errors
      - Trending video fetching (mostPopular chart) ONLY
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    # Known placeholder values that should not be treated as valid keys
    _PLACEHOLDER_KEYS = frozenset({
        "your_youtube_api_key_here",
        "your_api_key_here",
        "CHANGE_ME",
        "xxx",
        "",
    })

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.youtube_api_key
        if not self._api_key or self._api_key.strip().lower() in self._PLACEHOLDER_KEYS:
            raise ValueError(
                "YouTube API key is missing or still set to a placeholder. "
                "Set a valid YOUTUBE_API_KEY in your .env file. "
                "Get one at https://console.cloud.google.com/apis/credentials"
            )

        # Persistent session with retry strategy
        self._session = self._build_session()

    # ----- Private helpers -------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRY_ATTEMPTS,
            backoff_factor=RETRY_BACKOFF_SECONDS,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GET request with the API key injected."""
        params["key"] = self._api_key
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug("GET %s?%s", url, urlencode(params))

        response = self._session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    # ----- Fetch trending videos -------------------------------------------

    def fetch_trending(
        self,
        region_code: str = "US",
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch trending (mostPopular) videos for a region.

        Uses the videos.list endpoint with chart=mostPopular which does
        NOT require a search query — returns truly trending content.
        """
        params: Dict[str, Any] = {
            "part": "snippet,statistics,contentDetails",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": min(max_results, 50),
        }

        # Failsafe retry loop
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                data = self._get("videos", params)
                items = data.get("items", [])
                # Tag each item with region for tracking
                for item in items:
                    item["_region"] = region_code
                logger.info(
                    "Trending %s: %d videos fetched.",
                    region_code, len(items),
                )
                return items
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status == 403:
                    logger.warning(
                        "Quota/access error for region=%s: %s",
                        region_code, exc,
                    )
                    return []  # Don't retry on quota errors
                elif attempt < MAX_RETRY_ATTEMPTS:
                    logger.warning(
                        "YouTube API error (region=%s, attempt %d/%d): %s — retrying...",
                        region_code, attempt, MAX_RETRY_ATTEMPTS, exc,
                    )
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                else:
                    logger.error(
                        "YouTube trending API failed after %d attempts (region=%s): %s",
                        MAX_RETRY_ATTEMPTS, region_code, exc,
                    )
            except Exception as exc:
                if attempt < MAX_RETRY_ATTEMPTS:
                    logger.warning(
                        "Unexpected error fetching trending (region=%s, attempt %d/%d): %s — retrying...",
                        region_code, attempt, MAX_RETRY_ATTEMPTS, exc,
                    )
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                else:
                    logger.error(
                        "Trending fetch failed after %d attempts (region=%s): %s",
                        MAX_RETRY_ATTEMPTS, region_code, exc,
                    )

        return []

    # ----- Keyword search (hybrid mode) ------------------------------------

    def fetch_by_keyword(
        self,
        keyword: str,
        region_code: str = "US",
        max_results: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Search for videos by keyword using search.list, then hydrate
        with full statistics via videos.list.
        """
        search_params: Dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "q": keyword,
            "regionCode": region_code,
            "order": "relevance",
            "maxResults": min(max_results, 25),
        }
        try:
            search_data = self._get("search", search_params)
            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            if not video_ids:
                return []

            # Hydrate with full snippet + statistics + contentDetails
            detail_params: Dict[str, Any] = {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids),
            }
            detail_data = self._get("videos", detail_params)
            items = detail_data.get("items", [])
            for item in items:
                item["_region"] = region_code
                item["_keyword"] = keyword
            logger.info(
                "Keyword search '%s' (region=%s): %d videos.",
                keyword, region_code, len(items),
            )
            return items
        except Exception as exc:
            logger.warning("Keyword search '%s' failed: %s", keyword, exc)
            return []

    # ----- Parse into structured objects -----------------------------------

    @staticmethod
    def parse_video_item(item: Dict[str, Any], category: str = "trending") -> RawVideo:
        """Convert a YouTube API item dict into a ``RawVideo`` dataclass."""
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})
        thumb_url = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url", "")
        )

        return RawVideo(
            video_id=item.get("id", item.get("video_id", "")),
            title=snippet.get("title", ""),
            channel=snippet.get("channelTitle", ""),
            description=snippet.get("description", ""),
            published_at=snippet.get("publishedAt", ""),
            thumbnail_url=thumb_url,
            views=int(stats.get("viewCount", 0)),
            likes=int(stats.get("likeCount", 0)),
            comments=int(stats.get("commentCount", 0)),
            niche=category,
        )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
def _deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate video items by video ID, keeping the version with highest views.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for item in items:
        vid = item.get("id", "")
        if isinstance(vid, dict):
            vid = vid.get("videoId", "")
        if not vid:
            continue

        views = int(item.get("statistics", {}).get("viewCount", 0))
        if vid not in seen or views > int(seen[vid].get("statistics", {}).get("viewCount", 0)):
            seen[vid] = item

    return list(seen.values())


def _categorize_video(item: Dict[str, Any]) -> str:
    """
    Derive a category label from the video's YouTube categoryId.

    This replaces hardcoded niche queries with auto-detected categories.
    """
    snippet = item.get("snippet", {})
    category_id = snippet.get("categoryId", "")

    if category_id in YOUTUBE_CATEGORY_MAP:
        return YOUTUBE_CATEGORY_MAP[category_id]

    return "trending"


# ---------------------------------------------------------------------------
# Stale data cleanup
# ---------------------------------------------------------------------------
def purge_stale_youtube_videos() -> int:
    """
    Delete YouTube videos older than 7 days to ensure data freshness.

    Returns the number of rows deleted.
    """
    from core.database import get_connection

    with get_connection() as conn:
        cursor = conn.execute(
            """DELETE FROM videos
               WHERE platform = 'youtube'
                 AND published_at < datetime('now', '-7 days');"""
        )
        deleted = cursor.rowcount

    if deleted > 0:
        logger.info("Purged %d stale YouTube videos (older than 7 days).", deleted)
    else:
        logger.info("No stale YouTube videos to purge.")

    return deleted


# ---------------------------------------------------------------------------
# Config-aware filtering helpers
# ---------------------------------------------------------------------------
def _parse_duration_seconds(duration_str: str) -> int:
    """Parse ISO 8601 duration (e.g. PT1M30S, PT45S) to seconds."""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str or '')
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _filter_by_content_type(items: List[Dict[str, Any]], content_type: str) -> List[Dict[str, Any]]:
    """Filter videos by duration: shorts (<60s), long (>=60s), or all."""
    if content_type == "all":
        return items
    result = []
    for item in items:
        dur = item.get("contentDetails", {}).get("duration", "")
        secs = _parse_duration_seconds(dur)
        if content_type == "shorts" and 0 < secs < 60:
            result.append(item)
        elif content_type == "long" and secs >= 60:
            result.append(item)
    return result


def _filter_by_categories(items: List[Dict[str, Any]], categories: List[str]) -> List[Dict[str, Any]]:
    """Filter to only videos whose categoryId maps to one of the given labels."""
    if not categories:
        return items
    allowed_ids = set()
    for cat in categories:
        cat_lower = cat.lower().strip()
        for label, cat_id in CATEGORY_LABEL_TO_ID.items():
            if cat_lower in label:
                allowed_ids.add(cat_id)
    if not allowed_ids:
        return items
    return [
        item for item in items
        if item.get("snippet", {}).get("categoryId", "") in allowed_ids
    ]


def _filter_by_keywords(items: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    """Keep only videos where a keyword appears in the title or description."""
    if not keywords:
        return items
    kw_lower = [k.lower() for k in keywords]
    result = []
    for item in items:
        snippet = item.get("snippet", {})
        text = f"{snippet.get('title', '')} {snippet.get('description', '')}".lower()
        if any(kw in text for kw in kw_lower):
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Public high-level functions
# ---------------------------------------------------------------------------
# Fallback regions used when primary ingestion yields too few results
FALLBACK_REGIONS = ["US", "GB", "CA"]
MIN_RESULTS_THRESHOLD = 20


def ingest_trending_videos(
    regions: Optional[List[str]] = None,
    config: Optional[PipelineConfig] = None,
) -> List[RawVideo]:
    """
    Ingest globally trending videos across multiple regions.

    Implements multi-region fallback: if primary regions yield < 20 videos,
    automatically fetches from US/GB/CA to ensure sufficient data.

    Returns a deduplicated list of ``RawVideo`` objects ready for processing.
    """
    cfg = config or PipelineConfig()
    regions = regions or cfg.regions

    client = YouTubeClient()
    all_items: List[Dict[str, Any]] = []

    # ---- Trending (mostPopular) from configured regions ----
    total_calls = len(regions)
    for idx, region in enumerate(regions, 1):
        logger.info("▶ Fetching trending [%d/%d] region=%s", idx, total_calls, region)
        items = client.fetch_trending(region_code=region)
        # Tag each item with source region
        for item in items:
            item["_source_region"] = region
        all_items.extend(items)
        if idx < total_calls:
            time.sleep(0.5)

    # ---- Multi-region fallback (Part 1) ----
    if len(all_items) < MIN_RESULTS_THRESHOLD:
        fallback_used = []
        for fb_region in FALLBACK_REGIONS:
            if fb_region not in regions and len(all_items) < MIN_RESULTS_THRESHOLD:
                logger.info(
                    "▶ Fallback: fetching from %s (only %d items so far)",
                    fb_region, len(all_items),
                )
                fb_items = client.fetch_trending(region_code=fb_region)
                for item in fb_items:
                    item["_source_region"] = fb_region
                    item["_is_fallback"] = True
                all_items.extend(fb_items)
                fallback_used.append(fb_region)
                time.sleep(0.5)
        if fallback_used:
            logger.info("Fallback regions used: %s → now %d items.", fallback_used, len(all_items))

    # ---- Hybrid: keyword search ----
    if cfg.keywords:
        primary_region = regions[0] if regions else "US"
        for kw in cfg.keywords:
            logger.info("▶ Hybrid keyword search: '%s' (region=%s)", kw, primary_region)
            kw_items = client.fetch_by_keyword(kw, region_code=primary_region)
            for item in kw_items:
                item["_source_region"] = primary_region
            all_items.extend(kw_items)
            time.sleep(0.5)

    logger.info(
        "Total raw items fetched: %d (before filters) from %d regions.",
        len(all_items), len(regions),
    )

    # ---- Apply config filters ----
    filtered = _filter_by_content_type(all_items, cfg.content_type)
    if len(filtered) != len(all_items):
        logger.info("Content type filter (%s): %d → %d", cfg.content_type, len(all_items), len(filtered))

    filtered = _filter_by_categories(filtered, cfg.categories)
    filtered = _filter_by_keywords(filtered, cfg.keywords)

    # ---- Deduplicate ----
    unique_items = _deduplicate_items(filtered)
    logger.info(
        "Deduplication: %d → %d unique videos.",
        len(filtered), len(unique_items),
    )

    # ---- Parse into RawVideo objects with region + content_type tags ----
    videos = []
    for item in unique_items:
        category = _categorize_video(item)
        try:
            video = YouTubeClient.parse_video_item(item, category)
            video.source_region = item.get("_source_region", "")
            video.content_type = cfg.content_type
            videos.append(video)
        except Exception as exc:
            logger.warning("Failed to parse video item: %s", exc)

    logger.info("✔ Ingestion complete: %d videos.", len(videos))
    return videos


def ingest_videos(config: Optional[PipelineConfig] = None) -> List[RawVideo]:
    """
    Primary ingestion entry point.

    Accepts optional PipelineConfig for user-defined filtering.
    Falls back to default (all regions, no filters) when config is None.
    """
    return ingest_trending_videos(config=config)

