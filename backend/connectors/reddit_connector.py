"""
Reddit Connector for the Content Intelligence Platform.

Uses an Apify Reddit Scraper to fetch trending posts, search
by keywords, and discover subreddit content. Replaces the
previous OAuth-based RedditClient with the same Apify pattern
used by TikTok and Instagram connectors.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from connectors.apify_mixin import ApifyMixin
from connectors.base import BaseConnector
from connectors.models import ConnectorHealth, NormalizedContent

logger = logging.getLogger(__name__)


class RedditConnector(BaseConnector, ApifyMixin):
    """
    Reddit connector using Apify Reddit Scraper.

    Fetches trending posts, keyword search results, and subreddit
    content via Apify actor runs. No OAuth or Reddit app required.
    """

    platform_id = "reddit"
    platform_name = "Reddit"

    def __init__(self) -> None:
        from core.config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=getattr(settings, "reddit_request_delay", 2.0),
            request_timeout=60,
            max_retries=3,
        )
        self._max_results = getattr(settings, "reddit_max_results", 30)
        self._api_token = getattr(settings, "apify_api_token", "")
        self._actor_id = getattr(settings, "apify_reddit_actor_id", "vandernorth~reddit-scraper")

    # ---- BaseConnector implementation --------------------------------------

    def fetch_trending(
        self,
        *,
        limit: int = 30,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Fetch trending Reddit posts via Apify."""
        from core.config import get_settings

        effective_limit = min(limit, self._max_results)

        kw_list = kwargs.get("keywords") or []
        if kw_list:
            query = kw_list[0]
        else:
            settings = get_settings()
            niches = settings.niche_keywords
            query = niches[0] if niches else "trending"

        actor_input = {
            "searchQuery": query,
            "sort": "hot",
            "timeFilter": "week",
            "maxPostsPerSource": effective_limit,
        }

        self._logger.info(
            "Reddit (Apify): fetching trending posts (query=%s, limit=%d)",
            query, effective_limit,
        )
        raw_items = self.run_actor_sync(actor_input)
        self._metrics.record_request(success=bool(raw_items))

        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for raw in raw_items:
            if len(results) >= effective_limit:
                break
            try:
                normalized = self.normalize_content(raw)
                if normalized and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("Reddit normalize failed: %s", exc)

        self._logger.info(
            "Reddit (Apify): fetched %d trending posts", len(results),
        )
        return results

    def fetch_by_keywords(
        self,
        keywords: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Search Reddit by keywords via Apify."""
        effective_limit = min(limit, self._max_results)
        search_terms = list(dict.fromkeys(term.strip() for term in keywords if term and term.strip()))[:4]
        if not search_terms:
            search_terms = ["trending"]
        per_query_limit = max(effective_limit // len(search_terms), 5)

        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for query in search_terms:
            actor_input = {
                "searchQuery": query,
                "sort": "relevance",
                "timeFilter": "month",
                "maxPostsPerSource": per_query_limit,
            }
            self._logger.info(
                "Reddit (Apify): searching keyword=%s (limit=%d)",
                query, per_query_limit,
            )
            raw_items = self.run_actor_sync(actor_input)
            self._metrics.record_request(success=bool(raw_items))

            for raw in raw_items:
                if len(results) >= effective_limit:
                    break
                try:
                    normalized = self.normalize_content(raw)
                    if normalized and normalized.id not in seen_ids:
                        seen_ids.add(normalized.id)
                        results.append(normalized)
                except Exception as exc:
                    self._logger.debug("Reddit normalize failed: %s", exc)
            if len(results) >= effective_limit:
                break

        self._logger.info(
            "Reddit (Apify): fetched %d posts for keywords %s",
            len(results), search_terms,
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
            "Reddit: hashtag search mapped to keyword search for: %s", hashtags,
        )
        return self.fetch_by_keywords(hashtags, limit=limit)

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """
        Transform an Apify Reddit Scraper result into NormalizedContent.

        Supports both the ``automation-lab~reddit-scraper`` output format
        (``createdAt``, ``selfText``, ``linkFlairText``) and the
        ``vandernorth~reddit-scraper`` format (``created_utc``, ``selftext``).
        """
        if not raw_payload or not isinstance(raw_payload, dict):
            return NormalizedContent(
                id="reddit_unknown",
                platform="reddit",
                content_type="post",
                title="Unknown Reddit Post",
            )

        post_id = str(raw_payload.get("id", "") or "")
        selftext = (
            raw_payload.get("selfText", "")
            or raw_payload.get("selftext", "")
            or raw_payload.get("text", "")
            or ""
        )
        title = raw_payload.get("title", "") or ""
        description = selftext[:2000] if selftext else title

        # Thumbnail handling
        thumbnail = raw_payload.get("thumbnail", "")
        if thumbnail in ("self", "default", "nsfw", "spoiler", ""):
            previews = raw_payload.get("preview", {}).get("images", [])
            if previews:
                thumbnail = previews[0].get("source", {}).get("url", "")
            elif raw_payload.get("imageUrls"):
                thumbnail = raw_payload["imageUrls"][0]
            else:
                thumbnail = ""

        # Timestamp — accept both ISO string (createdAt) and unix (created_utc)
        created_at = raw_payload.get("createdAt", "")
        created_utc = raw_payload.get("created_utc", 0)
        published_at = ""
        if created_at and isinstance(created_at, str):
            published_at = created_at
        elif created_utc:
            try:
                published_at = datetime.fromtimestamp(
                    int(created_utc), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                pass

        # Metrics
        score = max(int(raw_payload.get("score", 0)), 0)
        ups = max(int(raw_payload.get("ups", 0) or raw_payload.get("score", 0)), 0)
        comments = max(int(raw_payload.get("numComments", 0) or raw_payload.get("num_comments", 0)), 0)

        # Subreddit / Author
        subreddit = raw_payload.get("subreddit", "unknown")
        author = raw_payload.get("author", "") or f"r/{subreddit}"

        # Extract hashtag-like flair
        flair = (
            raw_payload.get("linkFlairText", "")
            or raw_payload.get("link_flair_text", "")
            or raw_payload.get("flair", "")
            or ""
        )
        hashtags = [flair.lower().replace(" ", "_")] if flair else []

        source_url = raw_payload.get("url", raw_payload.get("permalink", "")) or ""
        if source_url.startswith("/"):
            source_url = f"https://reddit.com{source_url}"

        ratio = raw_payload.get("upvote_ratio", raw_payload.get("upvoteRatio"))
        try:
            upvote_ratio = min(max(float(ratio), 0.0), 1.0) if ratio is not None else None
        except (TypeError, ValueError):
            upvote_ratio = None

        platform_metadata = {
            "subreddit": str(subreddit or "").removeprefix("r/"),
            "author": str(author or ""),
            "upvotes": ups,
            "score": score,
            "upvote_ratio": upvote_ratio,
            "flair": str(flair or ""),
            "permalink": source_url,
            "post_type": "self" if raw_payload.get("is_self") else "link",
        }

        return NormalizedContent(
            id=f"reddit_{post_id}",
            platform="reddit",
            content_type="post",
            author_name=author,
            author_followers=0,
            title=title,
            description=description,
            hashtags=hashtags,
            thumbnail_url=thumbnail,
            published_at=published_at,
            views=score,
            likes=ups,
            comments=comments,
            shares=0,
            saves=0,
            source_url=source_url,
            platform_metadata=platform_metadata,
            raw_payload=raw_payload,
        )

    def health_check(self) -> ConnectorHealth:
        """Check Reddit connector health by verifying Apify token and actor access."""
        return self._apify_health_check("reddit")
