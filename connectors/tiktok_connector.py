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
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from connectors.base import BaseConnector
from connectors.models import ConnectorHealth, NormalizedContent

logger = logging.getLogger(__name__)

# ── Apify API config ─────────────────────────────────────────────────────────
_APIFY_BASE_URL = "https://api.apify.com/v2"


class TikTokConnector(BaseConnector):
    """
    TikTok connector using Apify (clockworks/tiktok-scraper).

    Fetches trending videos, keyword search results, and hashtag
    content via Apify actor runs. No login or browser required.
    """

    platform_id = "tiktok"
    platform_name = "TikTok"

    def __init__(self) -> None:
        from config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=getattr(settings, "tiktok_request_delay", 2.0),
            request_timeout=60,  # Apify runs can take longer
            max_retries=3,
        )
        self._max_results = getattr(settings, "tiktok_max_results", 30)
        self._api_token = getattr(settings, "apify_api_token", "")
        self._actor_id = getattr(settings, "apify_tiktok_actor_id", "clockworks~tiktok-scraper")
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Lazily initialize the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=15.0,
                    read=310.0,  # Apify sync endpoint waits up to 300s
                    write=15.0,
                    pool=15.0,
                ),
                headers={
                    "Content-Type": "application/json",
                },
            )
        return self._client

    # ── Apify API methods ────────────────────────────────────────────────────

    def _run_actor_sync(
        self,
        actor_input: Dict[str, Any],
        *,
        timeout_secs: int = 120,
        memory_mb: int = 512,
    ) -> List[Dict[str, Any]]:
        """
        Run the TikTok Scraper actor synchronously.

        Uses the run-sync-get-dataset-items endpoint which starts the
        actor, waits for completion, and returns dataset items directly.
        Max wait time is 300 seconds.
        """
        client = self._get_client()
        url = f"{_APIFY_BASE_URL}/acts/{self._actor_id}/run-sync-get-dataset-items"

        try:
            resp = client.post(
                url,
                params={
                    "token": self._api_token,
                    "timeout": timeout_secs,
                    "memory": memory_mb,
                    "format": "json",
                },
                json=actor_input,
            )

            if resp.status_code == 408:
                self._logger.warning(
                    "Apify sync run timed out after %ds — trying async fallback",
                    timeout_secs,
                )
                return self._run_actor_async(actor_input, memory_mb=memory_mb)

            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("items", [data])
            return []

        except httpx.HTTPStatusError as exc:
            self._logger.warning(
                "Apify API error: %s %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
            self._metrics.record_request(success=False)
            return []

        except Exception as exc:
            self._logger.warning("Apify request failed: %s", exc)
            self._metrics.record_request(success=False)
            return []

    def _run_actor_async(
        self,
        actor_input: Dict[str, Any],
        *,
        memory_mb: int = 512,
        max_wait_secs: int = 180,
        poll_interval: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Run the actor asynchronously with polling.

        Fallback for when sync endpoint times out.
        """
        client = self._get_client()

        # Step 1: Start the run
        try:
            resp = client.post(
                f"{_APIFY_BASE_URL}/acts/{self._actor_id}/runs",
                params={"token": self._api_token, "memory": memory_mb},
                json=actor_input,
            )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
            run_id = run_data.get("id")
            if not run_id:
                self._logger.error("Apify async run: no run ID returned")
                return []
        except Exception as exc:
            self._logger.error("Apify async run start failed: %s", exc)
            return []

        # Step 2: Poll for completion
        terminal_statuses = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
        start_time = time.time()
        run_info = {}

        while time.time() - start_time < max_wait_secs:
            try:
                status_resp = client.get(
                    f"{_APIFY_BASE_URL}/actor-runs/{run_id}",
                    params={"token": self._api_token},
                )
                status_resp.raise_for_status()
                run_info = status_resp.json().get("data", {})
                status = run_info.get("status", "")

                if status in terminal_statuses:
                    if status != "SUCCEEDED":
                        self._logger.warning(
                            "Apify async run ended with status: %s", status
                        )
                        return []
                    break
            except Exception as exc:
                self._logger.warning("Apify status poll failed: %s", exc)

            time.sleep(poll_interval)
        else:
            self._logger.warning(
                "Apify async run did not complete within %ds", max_wait_secs
            )
            return []

        # Step 3: Fetch dataset items
        dataset_id = run_info.get("defaultDatasetId", "")
        if not dataset_id:
            self._logger.error("Apify async run: no dataset ID")
            return []

        try:
            items_resp = client.get(
                f"{_APIFY_BASE_URL}/datasets/{dataset_id}/items",
                params={"token": self._api_token, "format": "json"},
            )
            items_resp.raise_for_status()
            data = items_resp.json()
            return data if isinstance(data, list) else []
        except Exception as exc:
            self._logger.error("Apify dataset fetch failed: %s", exc)
            return []

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
        raw_items = self._run_actor_sync(actor_input)
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
        raw_items = self._run_actor_sync(actor_input)
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
        raw_items = self._run_actor_sync(actor_input)
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
        start = time.time()

        if not self._api_token:
            return ConnectorHealth(
                platform="tiktok",
                status="unavailable",
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message="APIFY_API_TOKEN not configured in .env",
                credentials_configured=False,
            )

        try:
            client = self._get_client()
            resp = client.get(
                f"{_APIFY_BASE_URL}/acts/{self._actor_id}",
                params={"token": self._api_token},
            )
            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                return ConnectorHealth(
                    platform="tiktok",
                    status="healthy",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message="",
                    credentials_configured=True,
                )
            elif resp.status_code == 401:
                return ConnectorHealth(
                    platform="tiktok",
                    status="unavailable",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message="Invalid APIFY_API_TOKEN",
                    credentials_configured=True,
                )
            else:
                return ConnectorHealth(
                    platform="tiktok",
                    status="degraded",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message=f"Apify API returned HTTP {resp.status_code}",
                    credentials_configured=True,
                )

        except Exception as exc:
            return ConnectorHealth(
                platform="tiktok",
                status="unavailable",
                latency_ms=round((time.time() - start) * 1000, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc)[:200],
                credentials_configured=bool(self._api_token),
            )
