"""
YouTube Connector for the Content Intelligence Platform.

Adapter that wraps the existing YouTubeClient from ingestion.py
into the BaseConnector interface. Does NOT rewrite the YouTube
logic — it delegates to the proven implementation.

This connector:
    - fetch_trending() → YouTubeClient.fetch_trending() per region
    - fetch_by_keywords() → YouTubeClient.fetch_by_keyword()
    - fetch_by_hashtags() → maps to keyword search (YT has no hashtag API)
    - normalize_content() → maps YouTube API item → NormalizedContent
    - health_check() → quick API connectivity test
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector
from connectors.models import ConnectorHealth, NormalizedContent

logger = logging.getLogger(__name__)

# YouTube category mapping (reused from ingestion.py)
_YOUTUBE_CATEGORY_MAP = {
    "1": "film & animation", "2": "autos & vehicles", "10": "music",
    "15": "pets & animals", "17": "sports", "18": "short movies",
    "19": "travel & events", "20": "gaming", "21": "videoblogging",
    "22": "people & blogs", "23": "comedy", "24": "entertainment",
    "25": "news & politics", "26": "howto & style", "27": "education",
    "28": "science & technology", "29": "nonprofits & activism",
    "30": "movies", "43": "shows",
}


class YouTubeConnector(BaseConnector):
    """
    YouTube connector wrapping the existing YouTubeClient.

    Delegates all API calls to the proven ingestion.py implementation
    and normalizes results into NormalizedContent.
    """

    platform_id = "youtube"
    platform_name = "YouTube"

    def __init__(self) -> None:
        from config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=0.5,
            request_timeout=15,
            max_retries=settings.youtube_retry_attempts,
        )
        # Lazy init — client created on first use
        self._client = None

    def _get_client(self):
        """Lazily initialize the YouTube client."""
        if self._client is None:
            from ingestion import YouTubeClient
            self._client = YouTubeClient()
        return self._client

    # ---- BaseConnector implementation --------------------------------------

    def fetch_trending(
        self,
        *,
        limit: int = 50,
        region: str = "US",
        regions: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch trending videos from YouTube.

        Args:
            limit: Max results per region.
            region: Single region code (used if regions not provided).
            regions: Multiple region codes to scan.
        """
        client = self._get_client()
        target_regions = regions or [region]
        all_results: List[NormalizedContent] = []

        for idx, reg in enumerate(target_regions):
            try:
                items = client.fetch_trending(region_code=reg, max_results=limit)
                for item in items:
                    item["_source_region"] = reg
                    try:
                        normalized = self.normalize_content(item)
                        all_results.append(normalized)
                    except Exception as exc:
                        self._logger.warning("Failed to normalize YT item: %s", exc)

                self._metrics.record_request(success=True)

                if idx < len(target_regions) - 1:
                    self._throttle()

            except Exception as exc:
                self._metrics.record_request(success=False)
                self._logger.warning(
                    "YouTube trending fetch failed for region=%s: %s", reg, exc
                )

        return all_results

    def fetch_by_keywords(
        self,
        keywords: List[str],
        *,
        limit: int = 25,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Search YouTube by keywords using the existing keyword search."""
        client = self._get_client()
        results: List[NormalizedContent] = []

        for kw in keywords:
            try:
                items = client.fetch_by_keyword(
                    kw, region_code=region, max_results=limit
                )
                for item in items:
                    item["_source_region"] = region
                    try:
                        normalized = self.normalize_content(item)
                        results.append(normalized)
                    except Exception as exc:
                        self._logger.warning("Failed to normalize YT keyword item: %s", exc)

                self._metrics.record_request(success=True)
                self._throttle()

            except Exception as exc:
                self._metrics.record_request(success=False)
                self._logger.warning(
                    "YouTube keyword search failed for '%s': %s", kw, exc
                )

        return results

    def fetch_by_hashtags(
        self,
        hashtags: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """YouTube has no hashtag API — maps to keyword search."""
        self._logger.info(
            "YouTube: hashtag search mapped to keyword search for: %s", hashtags
        )
        return self.fetch_by_keywords(hashtags, limit=limit)

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """Transform a YouTube API video item into NormalizedContent."""
        snippet = raw_payload.get("snippet", {})
        stats = raw_payload.get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})

        # Video ID
        video_id = raw_payload.get("id", "")
        if isinstance(video_id, dict):
            video_id = video_id.get("videoId", "")

        # Thumbnail
        thumb_url = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url", "")
        )

        # Category
        category_id = snippet.get("categoryId", "")
        category = _YOUTUBE_CATEGORY_MAP.get(category_id, "trending")

        # Content type detection from duration
        content_type = "video"
        duration = raw_payload.get("contentDetails", {}).get("duration", "")
        if duration:
            import re
            match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
            if match:
                total_sec = (
                    int(match.group(1) or 0) * 3600
                    + int(match.group(2) or 0) * 60
                    + int(match.group(3) or 0)
                )
                if 0 < total_sec < 60:
                    content_type = "short"

        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))

        # Extract hashtags from description
        desc = snippet.get("description", "")
        hashtags = self._extract_hashtags(desc)

        return NormalizedContent(
            id=video_id,
            platform="youtube",
            content_type=content_type,
            author_name=snippet.get("channelTitle", ""),
            author_followers=0,  # Not available from video endpoint
            title=snippet.get("title", ""),
            description=desc,
            hashtags=hashtags,
            thumbnail_url=thumb_url,
            published_at=snippet.get("publishedAt", ""),
            language=snippet.get("defaultLanguage", ""),
            views=views,
            likes=likes,
            comments=comments,
            shares=0,  # YouTube doesn't expose shares
            saves=0,
            source_url=f"https://www.youtube.com/watch?v={video_id}",
            raw_payload=raw_payload,
        )

    def health_check(self) -> ConnectorHealth:
        """Check YouTube API connectivity."""
        start = time.time()
        try:
            client = self._get_client()
            # Quick test: fetch 1 trending video
            items = client.fetch_trending(region_code="US", max_results=1)
            latency = (time.time() - start) * 1000
            return ConnectorHealth(
                platform="youtube",
                status="healthy" if items else "degraded",
                latency_ms=round(latency, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                credentials_configured=True,
            )
        except Exception as exc:
            return ConnectorHealth(
                platform="youtube",
                status="unavailable",
                latency_ms=round((time.time() - start) * 1000, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc),
                credentials_configured=True,
            )

    @staticmethod
    def _extract_hashtags(text: str) -> List[str]:
        """Extract #hashtags from text."""
        import re
        return re.findall(r"#(\w+)", text)[:20]
