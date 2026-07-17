"""
Instagram Connector for the Content Intelligence Platform.

Uses the Apify Instagram Scraper to fetch public Instagram content.
This replaces the previous RapidAPI-based connector with a more
reliable, cost-effective solution (~$1/1000 results, $5 free/month).

Strategy:
    - Profile-based discovery: fetch recent posts from curated creators
    - Hashtag search: fetch posts by hashtag
    - Keyword search: intelligent expansion via QueryIntelligence

Apify Flow:
    1. POST /v2/acts/{actorId}/run-sync-get-dataset-items  (sync, ≤300s)
    2. If timeout → async: POST /runs → poll → GET /datasets/{id}/items

Dependencies:
    pip install httpx  (already in requirements)

Environment:
    APIFY_API_TOKEN=<your-token>
    APIFY_INSTAGRAM_ACTOR_ID=shu8hvrXbJbY3Eb9W  (default)
    INSTAGRAM_ENABLED=true
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from connectors.apify_mixin import ApifyMixin
from connectors.base import BaseConnector
from connectors.models import ConnectorHealth, NormalizedContent

logger = logging.getLogger(__name__)

# ── Default creator accounts to scan when no specific ones are provided ──
# Organized by niche — high-engagement public accounts
_DEFAULT_CREATORS = {
    "tech": [
        "techcrunch", "wired", "mkbhd", "elonmusk",
        "sundarpichai", "satlovelace",
    ],
    "business": [
        "garyvee", "hubspot", "foundrmagazine",
        "shopify", "entrepreneur",
    ],
    "marketing": [
        "hootsuite", "latermedia", "buffer",
        "socialmediaexaminer", "neilpatel",
    ],
    "ai": [
        "openai", "nvidia", "deepmind",
        "artificialintelligence.hub", "ai_machinelearning",
    ],
    "general": [
        "instagram", "natgeo", "bbcnews",
        "time", "bloomberg",
    ],
}

# Flat list of all default creators (deduplicated)
_ALL_DEFAULT_CREATORS = list(
    dict.fromkeys(
        creator
        for creators in _DEFAULT_CREATORS.values()
        for creator in creators
    )
)


class InstagramConnector(BaseConnector, ApifyMixin):
    """
    Instagram connector using Apify Instagram Scraper.

    Fetches posts from public profiles, hashtags, and search queries.
    Free tier includes $5/month credits (~3,000-5,000 posts).
    """

    platform_id = "instagram"
    platform_name = "Instagram"

    def __init__(self) -> None:
        from core.config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=getattr(settings, "instagram_request_delay", 3.0),
            request_timeout=60,
            max_retries=2,
        )
        self._max_results = getattr(settings, "instagram_max_results", 30)
        self._api_token = getattr(settings, "apify_api_token", "")
        self._actor_id = getattr(settings, "apify_instagram_actor_id", "shu8hvrXbJbY3Eb9W")

    # ── BaseConnector implementation ─────────────────────────────────────────

    def fetch_trending(
        self,
        *,
        limit: int = 30,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch trending Instagram content by scanning popular creator profiles.

        Runs the Apify actor with directUrls pointing to popular
        creator profile pages.
        """
        # Use a subset of default creators to stay within budget
        creators = kwargs.get("creators", _ALL_DEFAULT_CREATORS[:6])
        urls = [f"https://www.instagram.com/{username}/" for username in creators]

        actor_input = {
            "directUrls": urls,
            "resultsType": "posts",
            "resultsLimit": max(limit // len(creators), 3),
            "searchType": "user",
            "searchLimit": 1,
        }

        self._logger.info(
            "Instagram (Apify): scanning %d creator profiles", len(creators)
        )
        raw_items = self.run_actor_sync(actor_input)
        self._metrics.record_request(success=bool(raw_items))

        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for item in raw_items:
            if len(results) >= limit:
                break
            try:
                normalized = self._normalize_apify_post(item)
                if normalized and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("Skip IG post: %s", exc)

        self._logger.info(
            "Instagram (Apify): fetched %d posts from %d creators",
            len(results), len(creators),
        )
        return results

    def fetch_by_keywords(
        self,
        keywords: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch Instagram content related to keywords using intelligent
        hashtag-cluster search with local relevance scoring.

        Strategy:
            1. Expand keywords via QueryIntelligenceEngine into Instagram
               hashtag clusters and niche-specific search terms
            2. Build Apify actor input with hashtag URLs
            3. Run actor and collect results
            4. Score every fetched post locally and reject irrelevant content
        """
        self._logger.info(
            "Instagram (Apify): intelligent keyword search for: %s", keywords,
        )

        # ── Step 0: Expand keywords via Query Intelligence ──
        query_context = None
        ig_hashtags: List[str] = []
        creator_keywords: List[str] = []

        try:
            from services.query_intelligence import QueryIntelligenceEngine
            qi = QueryIntelligenceEngine()
            contexts = qi.expand_multi(keywords)
            if contexts:
                query_context = qi.merge_contexts(contexts) if len(contexts) > 1 else contexts[0]
                # Extract hashtag targets (strip # prefix for URLs)
                ig_hashtags = [
                    v.lstrip("#") for v in query_context.instagram_variants
                    if v.startswith("#")
                ]
                # Use normalized terms for creator matching
                creator_keywords = list(query_context.normalized_terms)

            self._logger.info(
                "[RETRIEVAL] platform=instagram hashtag_targets=%d creator_keywords=%s",
                len(ig_hashtags), creator_keywords[:4],
            )
        except Exception as exc:
            self._logger.warning("QueryIntelligence unavailable: %s — using basic strategy", exc)
            creator_keywords = list(keywords)

        # ── Step 1: Build Apify actor input ──
        # Combine hashtag URLs and creator profile URLs
        urls: List[str] = []

        # Add hashtag URLs
        for hashtag in ig_hashtags[:8]:
            clean = hashtag.strip().replace(" ", "")
            if clean:
                urls.append(f"https://www.instagram.com/explore/tags/{clean}/")

        # If no hashtags from QI, generate from raw keywords
        if not urls:
            for kw in keywords:
                clean = re.sub(r"[^a-zA-Z0-9]", "", kw.lower())
                if clean:
                    urls.append(f"https://www.instagram.com/explore/tags/{clean}/")

        # Add niche-matched creator profiles
        kw_lower = [kw.lower() for kw in (creator_keywords or keywords)]
        creators_to_scan: List[str] = []
        for niche, creators in _DEFAULT_CREATORS.items():
            if any(niche in kw or kw in niche for kw in kw_lower):
                creators_to_scan.extend(creators)
        if not creators_to_scan:
            creators_to_scan.extend(_DEFAULT_CREATORS.get("general", [])[:3])

        for username in list(dict.fromkeys(creators_to_scan))[:5]:
            urls.append(f"https://www.instagram.com/{username}/")

        # Deduplicate
        urls = list(dict.fromkeys(urls))

        actor_input = {
            "directUrls": urls,
            "resultsType": "posts",
            "resultsLimit": max(limit // max(len(urls), 1), 3),
            "searchType": "hashtag",
            "searchLimit": 1,
        }

        self._logger.info(
            "Instagram (Apify): running actor with %d URLs", len(urls)
        )
        raw_items = self.run_actor_sync(actor_input)
        self._metrics.record_request(success=bool(raw_items))

        # ── Step 2: Normalize results ──
        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for item in raw_items:
            if len(results) >= limit:
                break
            try:
                normalized = self._normalize_apify_post(item)
                if normalized and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("Skip IG post: %s", exc)

        # ── Step 3: Local relevance scoring ──
        if query_context and results:
            try:
                from analytics.relevance_engine import ContentRelevanceEngine
                relevance = ContentRelevanceEngine()
                scored_results: List[NormalizedContent] = []

                for item in results:
                    content_dict = item.to_raw_video()
                    result = relevance.score(content_dict, query_context)

                    if result.passed:
                        scored_results.append(item)
                    else:
                        self._logger.debug(
                            "[FILTERED] ig_post=%s reason=%r score=%d",
                            item.id, result.match_reason, result.score,
                        )

                pre_filter = len(results)
                results = scored_results
                self._logger.info(
                    "[RELEVANCE] platform=instagram scored=%d passed=%d rejected=%d",
                    pre_filter, len(results), pre_filter - len(results),
                )
            except Exception as exc:
                self._logger.warning(
                    "Relevance scoring unavailable: %s — returning unfiltered results", exc
                )

        self._logger.info(
            "Instagram (Apify): fetched %d relevant posts for keywords %s",
            len(results), keywords,
        )
        return results

    def fetch_by_hashtags(
        self,
        hashtags: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch Instagram posts by hashtag using Apify.

        Builds hashtag explore URLs and runs the actor.
        """
        urls = []
        for tag in hashtags:
            clean = tag.lstrip("#").strip().replace(" ", "")
            if clean:
                urls.append(f"https://www.instagram.com/explore/tags/{clean}/")

        if not urls:
            return []

        actor_input = {
            "directUrls": urls,
            "resultsType": "posts",
            "resultsLimit": max(limit // len(urls), 3),
            "searchType": "hashtag",
            "searchLimit": 1,
        }

        self._logger.info(
            "Instagram (Apify): fetching %d hashtags", len(urls)
        )
        raw_items = self.run_actor_sync(actor_input)
        self._metrics.record_request(success=bool(raw_items))

        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for item in raw_items:
            if len(results) >= limit:
                break
            try:
                normalized = self._normalize_apify_post(item)
                if normalized and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("Skip IG post: %s", exc)

        self._logger.info(
            "Instagram (Apify): fetched %d posts for hashtags %s",
            len(results), hashtags,
        )
        return results

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """
        Transform a raw Apify post dict into NormalizedContent.

        Required by BaseConnector abstract contract.
        """
        result = self._normalize_apify_post(raw_payload)
        if result is None:
            return NormalizedContent(
                id=f"ig_{raw_payload.get('shortCode', 'unknown')}",
                platform="instagram",
                content_type="post",
                author_name="",
                author_followers=0,
                title="Instagram Post",
                description="",
                hashtags=[],
                thumbnail_url="",
                published_at="",
                views=0,
                likes=0,
                comments=0,
                shares=0,
                saves=0,
                hook_text="",
                source_url="",
                raw_payload=raw_payload,
            )
        return result

    def _normalize_apify_post(
        self, raw: Dict[str, Any],
    ) -> Optional[NormalizedContent]:
        """
        Transform a raw Apify Instagram Scraper result into NormalizedContent.

        Apify Instagram Scraper returns fields like:
            shortCode, ownerUsername, ownerFullName, caption, likesCount,
            commentsCount, videoViewCount, timestamp, displayUrl, type, url, etc.
        """
        if not raw or not isinstance(raw, dict):
            return None

        # ── Extract post ID ──
        shortcode = str(
            raw.get("shortCode", "")
            or raw.get("shortcode", "")
            or raw.get("code", "")
            or raw.get("id", "")
        )
        if not shortcode:
            return None

        # ── Caption / Title ──
        caption_text = raw.get("caption", "") or ""
        if isinstance(caption_text, dict):
            # Some formats nest caption as an object
            caption_text = caption_text.get("text", "") or ""

        title_lines = caption_text.split("\n")
        title = title_lines[0][:150] if title_lines and title_lines[0] else f"IG Post {shortcode}"

        # ── Author ──
        author = (
            raw.get("ownerUsername", "")
            or raw.get("owner_username", "")
            or raw.get("username", "")
            or ""
        )
        author_full_name = raw.get("ownerFullName", "") or raw.get("full_name", "") or ""
        if not author and author_full_name:
            author = author_full_name

        # Follower count (may not always be present in post-level data)
        author_followers = int(
            raw.get("ownerFollowerCount", 0)
            or raw.get("follower_count", 0)
            or 0
        )

        # ── Content type ──
        media_type = raw.get("type", "") or raw.get("mediaType", "") or ""
        if isinstance(media_type, str):
            media_type_lower = media_type.lower()
        else:
            media_type_lower = ""

        is_video = raw.get("isVideo", False) or media_type_lower in ("video", "reel")
        video_duration = raw.get("videoDuration", 0) or raw.get("video_duration", 0) or 0

        if is_video:
            content_type = "reel" if 0 < video_duration <= 90 else "video"
        elif media_type_lower == "sidecar":
            content_type = "carousel"
        elif media_type_lower == "image":
            content_type = "post"
        else:
            content_type = "post"

        # ── Metrics ──
        likes = int(raw.get("likesCount", 0) or raw.get("likes", 0) or 0)
        comments = int(
            raw.get("commentsCount", 0) or raw.get("comments", 0) or 0
        )
        views = int(
            raw.get("videoViewCount", 0)
            or raw.get("videoPlayCount", 0)
            or raw.get("video_view_count", 0)
            or raw.get("views", 0)
            or 0
        )

        # For non-video posts, estimate views from likes
        if not is_video and views == 0:
            views = likes * 10

        # ── Hashtags ──
        # Apify may return hashtags as a list, or we extract from caption
        hashtags = raw.get("hashtags", [])
        if not hashtags and isinstance(hashtags, list):
            hashtags = re.findall(r"#(\w+)", caption_text)[:20]
        elif isinstance(hashtags, list):
            hashtags = [h.lstrip("#") for h in hashtags][:20]
        else:
            hashtags = re.findall(r"#(\w+)", caption_text)[:20]

        # ── Published date ──
        timestamp = raw.get("timestamp", "") or raw.get("taken_at", "")
        published_at = ""
        if timestamp:
            if isinstance(timestamp, str):
                # ISO format from Apify
                published_at = timestamp
            elif isinstance(timestamp, (int, float)):
                try:
                    published_at = datetime.fromtimestamp(
                        int(timestamp), tz=timezone.utc
                    ).isoformat()
                except (ValueError, OSError):
                    pass

        # ── Thumbnail ──
        thumbnail_url = (
            raw.get("displayUrl", "")
            or raw.get("thumbnailUrl", "")
            or raw.get("display_url", "")
            or raw.get("thumbnail_url", "")
            or ""
        )

        # ── Source URL ──
        source_url = (
            raw.get("url", "")
            or raw.get("postUrl", "")
            or f"https://www.instagram.com/p/{shortcode}/"
        )

        # ── Hook text ──
        hook_text = ""
        if caption_text:
            sentences = re.split(r"[.!?\n]", caption_text)
            hook_text = sentences[0].strip()[:200] if sentences else ""

        return NormalizedContent(
            id=f"ig_{shortcode}",
            platform="instagram",
            content_type=content_type,
            author_name=author,
            author_followers=author_followers,
            title=title,
            description=caption_text[:2000],
            hashtags=hashtags,
            thumbnail_url=thumbnail_url,
            published_at=published_at,
            views=views,
            likes=likes,
            comments=comments,
            shares=0,
            saves=0,
            hook_text=hook_text,
            source_url=source_url,
            raw_payload=raw,
        )

    def health_check(self) -> ConnectorHealth:
        """Check Instagram connector health by verifying Apify token and actor access."""
        return self._apify_health_check("instagram")
