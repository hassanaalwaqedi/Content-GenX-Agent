"""
TikTok Connector for the Content Intelligence Platform.

Uses the Apify TikTok Scraper (clockworks/tiktok-scraper) to fetch
trending videos, search by keywords, and discover hashtag content.

Strategy:
    Lightweight REST API calls via httpx to Apify's actor run endpoints.
    No browser automation, no Playwright, no Chromium binary required.

Apify Flow:
    1. POST /v2/acts/{actorId}/run-sync-get-dataset-items  (sync, ≤300s)
    2. If timeout → async: POST /runs → poll → GET /datasets/{id}/items

Dependencies:
    pip install httpx  (already in requirements)

Environment:
    APIFY_API_TOKEN=<your-token>
    APIFY_TIKTOK_ACTOR_ID=clockworks~tiktok-scraper  (default)
    TIKTOK_ENABLED=true
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

class TikTokConnector(BaseConnector, ApifyMixin):
    """
    TikTok connector using Apify (clockworks/tiktok-scraper).

    Fetches trending videos, keyword search results, and hashtag
    content via Apify actor runs. No login or browser required.
    """

    platform_id = "tiktok"
    platform_name = "TikTok"

    def __init__(self) -> None:
        from core.config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=getattr(settings, "tiktok_request_delay", 2.0),
            request_timeout=60,
            max_retries=3,
        )
        self._max_results = getattr(settings, "tiktok_max_results", 30)
        self._api_token = getattr(settings, "apify_api_token", "")
        self._actor_id = getattr(settings, "apify_tiktok_actor_id", "clockworks~tiktok-scraper")

    # ── BaseConnector implementation ─────────────────────────────────────────

    def fetch_trending(
        self,
        *,
        limit: int = 30,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Fetch trending TikTok videos via Apify."""
        effective_limit = min(limit, self._max_results)

        # Use search for trending content
        actor_input = {
            "searchQueries": ["trending"],
            "resultsPerPage": effective_limit,
            "proxyCountryCode": region if region != "US" else "None",
        }

        self._logger.info(
            "TikTok (Apify): fetching trending videos (limit=%d, region=%s)",
            effective_limit, region,
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
                if normalized and normalized.id and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("TikTok normalize failed: %s", exc)

        self._logger.info(
            "TikTok (Apify): fetched %d trending videos (region=%s)",
            len(results), region,
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
        Search TikTok by keywords using Apify.

        Uses QueryIntelligenceEngine to expand keywords into
        platform-optimized search variants for maximum coverage.
        """
        effective_limit = min(limit, self._max_results)
        results: List[NormalizedContent] = []
        seen_ids: set = set()

        # ── Expand keywords via Query Intelligence ──
        search_terms: List[str] = list(keywords)
        hashtag_terms: List[str] = []

        try:
            from services.query_intelligence import QueryIntelligenceEngine
            qi = QueryIntelligenceEngine()

            for kw in keywords:
                ctx = qi.expand(kw)
                # Add normalized search terms
                for term in ctx.normalized_terms:
                    if term not in search_terms:
                        search_terms.append(term)
                # Collect hashtag variants
                hashtag_terms.extend([
                    v.lstrip("#").replace(" ", "")
                    for v in ctx.tiktok_variants
                    if v.lstrip("#").replace(" ", "") not in hashtag_terms
                ])

            self._logger.info(
                "[RETRIEVAL] platform=tiktok search_terms=%s hashtag_terms=%d",
                search_terms[:6], len(hashtag_terms),
            )
        except Exception as exc:
            self._logger.warning(
                "QueryIntelligence unavailable: %s — using raw keywords", exc
            )
            hashtag_terms = [kw.replace(" ", "") for kw in keywords]

        # ── Build Apify actor input ──
        actor_input: Dict[str, Any] = {
            "resultsPerPage": max(effective_limit // max(len(search_terms), 1), 5),
        }

        # Primary: keyword search
        if search_terms:
            actor_input["searchQueries"] = search_terms[:6]

        # Secondary: hashtag search
        if hashtag_terms:
            actor_input["hashtags"] = hashtag_terms[:8]

        self._logger.info(
            "TikTok (Apify): running actor with %d search queries, %d hashtags",
            len(actor_input.get("searchQueries", [])),
            len(actor_input.get("hashtags", [])),
        )
        raw_items = self.run_actor_sync(actor_input)
        self._metrics.record_request(success=bool(raw_items))

        for raw in raw_items:
            if len(results) >= effective_limit:
                break
            try:
                normalized = self.normalize_content(raw)
                if normalized and normalized.id and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("TikTok normalize failed: %s", exc)

        self._logger.info(
            "TikTok (Apify): fetched %d total videos for keywords %s",
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
        """Fetch TikTok videos by hashtag via Apify."""
        effective_limit = min(limit, self._max_results)

        clean_tags = []
        for tag in hashtags:
            clean = tag.lstrip("#").strip()
            if clean:
                clean_tags.append(clean)

        if not clean_tags:
            return []

        actor_input = {
            "hashtags": clean_tags,
            "resultsPerPage": max(effective_limit // len(clean_tags), 5),
        }

        self._logger.info(
            "TikTok (Apify): fetching %d hashtags", len(clean_tags)
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
                if normalized and normalized.id and normalized.id not in seen_ids:
                    seen_ids.add(normalized.id)
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("TikTok normalize failed: %s", exc)

        self._logger.info(
            "TikTok (Apify): fetched %d videos for hashtags %s",
            len(results), hashtags,
        )
        return results

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """
        Transform an Apify TikTok Scraper result into NormalizedContent.

        Apify clockworks/tiktok-scraper returns:
            id, text, playCount, diggCount, shareCount, commentCount,
            createTime, authorMeta (name, nickname, followers),
            videoMeta (duration, cover), hashtags, musicMeta, webVideoUrl
        """
        if not raw_payload or not isinstance(raw_payload, dict):
            return NormalizedContent(
                id="tiktok_unknown",
                platform="tiktok",
                content_type="video",
                title="Unknown TikTok Video",
            )

        # ── Video ID ──
        video_id = str(
            raw_payload.get("id", "")
            or raw_payload.get("video_id", "")
            or raw_payload.get("aweme_id", "")
        )

        # ── Author info ──
        author_meta = raw_payload.get("authorMeta", {}) or {}
        if not isinstance(author_meta, dict):
            author_meta = {}

        author_name = (
            author_meta.get("nickname", "")
            or author_meta.get("name", "")
            or raw_payload.get("author_name", "")
            or ""
        )
        author_id = (
            author_meta.get("name", "")
            or author_meta.get("id", "")
            or ""
        )
        author_followers = int(
            author_meta.get("fans", 0)
            or author_meta.get("followers", 0)
            or author_meta.get("followerCount", 0)
            or 0
        )

        # ── Description / Title ──
        desc = (
            raw_payload.get("text", "")
            or raw_payload.get("desc", "")
            or raw_payload.get("description", "")
            or ""
        )
        title = desc[:150] if desc else f"TikTok #{video_id}"

        # ── Hashtags ──
        hashtags: List[str] = []
        raw_hashtags = raw_payload.get("hashtags", [])
        if isinstance(raw_hashtags, list):
            for ht in raw_hashtags:
                if isinstance(ht, dict):
                    name = ht.get("name", "") or ht.get("title", "")
                    if name:
                        hashtags.append(name.lower())
                elif isinstance(ht, str):
                    hashtags.append(ht.lstrip("#").lower())

        if not hashtags:
            hashtags = re.findall(r"#(\w+)", desc)[:20]

        # ── Audio ──
        music_meta = raw_payload.get("musicMeta", {}) or {}
        if not isinstance(music_meta, dict):
            music_meta = {}
        audio_name = (
            music_meta.get("musicName", "")
            or music_meta.get("title", "")
            or music_meta.get("name", "")
            or ""
        )

        # ── Video metadata & thumbnail ──
        video_meta = raw_payload.get("videoMeta", {}) or {}
        if not isinstance(video_meta, dict):
            video_meta = {}

        thumbnail_url = (
            raw_payload.get("covers", {}).get("default", "")
            if isinstance(raw_payload.get("covers"), dict) else ""
        ) or (
            video_meta.get("cover", "")
            or video_meta.get("originCover", "")
            or raw_payload.get("cover", "")
            or raw_payload.get("origin_cover", "")
            or ""
        )

        # ── Timestamp ──
        create_time = raw_payload.get("createTime", 0) or raw_payload.get("createTimeISO", "")
        published_at = ""
        if isinstance(create_time, str) and create_time:
            published_at = create_time
        elif isinstance(create_time, (int, float)) and create_time:
            try:
                published_at = datetime.fromtimestamp(
                    int(create_time), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                pass

        # ── Engagement Stats ──
        views = int(raw_payload.get("playCount", 0) or raw_payload.get("play_count", 0) or 0)
        likes = int(raw_payload.get("diggCount", 0) or raw_payload.get("digg_count", 0) or 0)
        comments = int(raw_payload.get("commentCount", 0) or raw_payload.get("comment_count", 0) or 0)
        shares = int(raw_payload.get("shareCount", 0) or raw_payload.get("share_count", 0) or 0)

        # ── Source URL ──
        source_url = (
            raw_payload.get("webVideoUrl", "")
            or raw_payload.get("url", "")
            or f"https://www.tiktok.com/@{author_id}/video/{video_id}"
        )

        # ── Hook text ──
        hook_text = ""
        if desc:
            sentences = re.split(r"[.!?\n]", desc)
            hook_text = sentences[0].strip()[:200] if sentences else ""

        return NormalizedContent(
            id=f"tiktok_{video_id}",
            platform="tiktok",
            content_type="video",
            author_name=author_name,
            author_followers=author_followers,
            title=title,
            description=desc,
            hashtags=hashtags,
            audio_name=audio_name,
            thumbnail_url=thumbnail_url,
            published_at=published_at,
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            hook_text=hook_text,
            source_url=source_url,
            raw_payload=raw_payload,
        )

    def health_check(self) -> ConnectorHealth:
        """Check TikTok connector health by verifying Apify token and actor access."""
        return self._apify_health_check("tiktok")
