"""
Reddit Connector for the Content Intelligence Platform.

Adapter that wraps the existing RedditClient from reddit_ingestion.py
into the BaseConnector interface. Delegates all API calls to the
proven implementation and normalizes results into NormalizedContent.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector
from connectors.models import ConnectorHealth, NormalizedContent

logger = logging.getLogger(__name__)


class RedditConnector(BaseConnector):
    """
    Reddit connector wrapping the existing RedditClient.

    Delegates all API calls to reddit_ingestion.py and normalizes
    results into the unified NormalizedContent schema.
    """

    platform_id = "reddit"
    platform_name = "Reddit"

    def __init__(self) -> None:
        from config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=1.0,
            request_timeout=15,
            max_retries=3,
        )
        self._max_posts = settings.reddit_max_posts_per_query
        self._client = None

    def _get_client(self):
        """Lazily initialize the Reddit client."""
        if self._client is None:
            from reddit_ingestion import RedditClient
            self._client = RedditClient()
        return self._client

    # ---- BaseConnector implementation --------------------------------------

    def fetch_trending(
        self,
        *,
        limit: int = 30,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch trending Reddit posts.

        Uses 'hot' sort for trending content across default niche keywords.
        """
        from config import get_settings

        client = self._get_client()
        settings = get_settings()
        niches = settings.niche_keywords
        results: List[NormalizedContent] = []

        for niche in niches:
            try:
                posts = client.search_posts(niche, sort="hot", limit=limit)
                for post in posts:
                    try:
                        normalized = self.normalize_content(post)
                        results.append(normalized)
                    except Exception as exc:
                        self._logger.warning("Failed to normalize Reddit post: %s", exc)

                self._metrics.record_request(success=True)
                self._throttle()

            except Exception as exc:
                self._metrics.record_request(success=False)
                self._logger.warning(
                    "Reddit trending fetch failed for niche='%s': %s", niche, exc
                )

        return results

    def fetch_by_keywords(
        self,
        keywords: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Search Reddit by keywords."""
        client = self._get_client()
        results: List[NormalizedContent] = []

        for kw in keywords:
            try:
                posts = client.search_posts(kw, sort="relevance", limit=limit)
                for post in posts:
                    try:
                        normalized = self.normalize_content(post)
                        results.append(normalized)
                    except Exception as exc:
                        self._logger.warning("Failed to normalize Reddit post: %s", exc)

                self._metrics.record_request(success=True)
                self._throttle()

            except Exception as exc:
                self._metrics.record_request(success=False)
                self._logger.warning(
                    "Reddit keyword search failed for '%s': %s", kw, exc
                )

        return results

    def fetch_by_hashtags(
        self,
        hashtags: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Reddit has no hashtag system — maps to keyword search."""
        self._logger.info(
            "Reddit: hashtag search mapped to keyword search for: %s", hashtags
        )
        return self.fetch_by_keywords(hashtags, limit=limit)

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """Transform a Reddit post dict into NormalizedContent."""
        post_id = raw_payload.get("id", "")
        selftext = raw_payload.get("selftext", "") or ""
        title = raw_payload.get("title", "")
        description = selftext[:2000] if selftext else title

        # Thumbnail handling
        thumbnail = raw_payload.get("thumbnail", "")
        if thumbnail in ("self", "default", "nsfw", "spoiler", ""):
            previews = raw_payload.get("preview", {}).get("images", [])
            if previews:
                thumbnail = previews[0].get("source", {}).get("url", "")
            else:
                thumbnail = ""

        # Timestamp
        created_utc = raw_payload.get("created_utc", 0)
        published_at = ""
        if created_utc:
            published_at = datetime.fromtimestamp(
                created_utc, tz=timezone.utc
            ).isoformat()

        # Metrics
        views = max(int(raw_payload.get("score", 0)), 0)
        likes = max(int(raw_payload.get("ups", 0)), 0)
        comments = max(int(raw_payload.get("num_comments", 0)), 0)

        # Subreddit
        subreddit = raw_payload.get("subreddit", "unknown")
        author = raw_payload.get("author", f"r/{subreddit}")

        # Extract hashtag-like flair
        flair = raw_payload.get("link_flair_text", "")
        hashtags = [flair.lower().replace(" ", "_")] if flair else []

        permalink = raw_payload.get("permalink", "")
        source_url = f"https://reddit.com{permalink}" if permalink else ""

        return NormalizedContent(
            id=f"reddit_{post_id}",
            platform="reddit",
            content_type="post",
            author_name=f"r/{subreddit}",
            author_followers=0,
            title=title,
            description=description,
            hashtags=hashtags,
            thumbnail_url=thumbnail,
            published_at=published_at,
            views=views,
            likes=likes,
            comments=comments,
            shares=0,
            saves=0,
            source_url=source_url,
            raw_payload=raw_payload,
        )

    def health_check(self) -> ConnectorHealth:
        """Check Reddit API connectivity."""
        start = time.time()
        try:
            client = self._get_client()
            # Quick test: search 1 post
            posts = client.search_posts("test", limit=1)
            latency = (time.time() - start) * 1000
            return ConnectorHealth(
                platform="reddit",
                status="healthy" if posts else "degraded",
                latency_ms=round(latency, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                credentials_configured=True,
            )
        except Exception as exc:
            return ConnectorHealth(
                platform="reddit",
                status="unavailable",
                latency_ms=round((time.time() - start) * 1000, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc),
                credentials_configured=True,
            )
