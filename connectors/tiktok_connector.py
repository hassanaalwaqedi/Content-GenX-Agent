"""
TikTok Connector for the Content Intelligence Platform.

Uses the RapidAPI "TikTok Scraper" (tiktok-scraper7) API to fetch
trending videos, search by keywords, and discover hashtag content.

Strategy:
    Lightweight REST API calls via httpx — same architecture as the
    Instagram connector. No browser automation, no Playwright, no
    Chromium binary required.

Dependencies:
    pip install httpx  (already in requirements)

Environment:
    RAPIDAPI_KEY=<your-key>
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

# ── RapidAPI config ──────────────────────────────────────────────────────────
_RAPIDAPI_HOST = "tiktok-scraper7.p.rapidapi.com"
_RAPIDAPI_BASE_URL = f"https://{_RAPIDAPI_HOST}"


class TikTokConnector(BaseConnector):
    """
    TikTok connector using RapidAPI (tiktok-scraper7).

    Fetches trending videos, keyword search results, and hashtag
    content via simple REST calls. No login or browser required.
    """

    platform_id = "tiktok"
    platform_name = "TikTok"

    def __init__(self) -> None:
        from config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=getattr(settings, "tiktok_request_delay", 2.0),
            request_timeout=getattr(settings, "tiktok_request_timeout", 30),
            max_retries=3,
        )
        self._max_results = getattr(settings, "tiktok_max_results", 30)
        self._api_key = getattr(settings, "rapidapi_key", "")
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Lazily initialize the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self._request_timeout,
                headers={
                    "x-rapidapi-host": _RAPIDAPI_HOST,
                    "x-rapidapi-key": self._api_key,
                },
            )
        return self._client

    # ── Raw API calls ────────────────────────────────────────────────────────

    def _fetch_feed(
        self, region: str = "US", count: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch the TikTok trending/recommended feed.

        Endpoint: GET /feed/list
        Params: region, count
        """
        client = self._get_client()
        try:
            resp = client.get(
                f"{_RAPIDAPI_BASE_URL}/feed/list",
                params={"region": region, "count": min(count, 30)},
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                return data if isinstance(data, list) else []

            # Primary format: data.videos or data.itemList or data.items
            videos = (
                data.get("data", {}).get("videos", [])
                if isinstance(data.get("data"), dict)
                else []
            )
            if not videos:
                videos = data.get("itemList", []) or data.get("items", []) or []

            # Fallback: if data itself is the list
            if not videos and isinstance(data.get("data"), list):
                videos = data["data"]

            return videos

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._logger.warning("TikTok RapidAPI rate limit hit")
                self._metrics.record_rate_limit()
            else:
                self._logger.warning(
                    "TikTok feed API error: %s %s",
                    exc.response.status_code,
                    exc.response.text[:200],
                )
            self._metrics.record_request(success=False)
            return []

        except Exception as exc:
            self._logger.warning("TikTok feed request failed: %s", exc)
            self._metrics.record_request(success=False)
            return []

    def _search_videos(
        self, keyword: str, count: int = 20, cursor: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search TikTok videos by keyword.

        Endpoint: GET /feed/search
        Params: keywords, count, cursor
        """
        client = self._get_client()
        try:
            resp = client.get(
                f"{_RAPIDAPI_BASE_URL}/feed/search",
                params={
                    "keywords": keyword,
                    "count": min(count, 30),
                    "cursor": cursor,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                return data if isinstance(data, list) else []

            videos = (
                data.get("data", {}).get("videos", [])
                if isinstance(data.get("data"), dict)
                else []
            )
            if not videos:
                videos = data.get("itemList", []) or data.get("items", []) or []

            if not videos and isinstance(data.get("data"), list):
                videos = data["data"]

            return videos

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._logger.warning(
                    "TikTok RapidAPI rate limit hit for keyword '%s'", keyword
                )
                self._metrics.record_rate_limit()
            else:
                self._logger.warning(
                    "TikTok search API error for '%s': %s %s",
                    keyword,
                    exc.response.status_code,
                    exc.response.text[:200],
                )
            self._metrics.record_request(success=False)
            return []

        except Exception as exc:
            self._logger.warning(
                "TikTok search request failed for '%s': %s", keyword, exc
            )
            self._metrics.record_request(success=False)
            return []

    def _fetch_hashtag_videos(
        self, hashtag: str, count: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch TikTok videos by hashtag/challenge name.

        Endpoint: GET /challenge/posts
        Params: challenge_name, count
        """
        client = self._get_client()
        try:
            resp = client.get(
                f"{_RAPIDAPI_BASE_URL}/challenge/posts",
                params={
                    "challenge_name": hashtag,
                    "count": min(count, 30),
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                return data if isinstance(data, list) else []

            videos = (
                data.get("data", {}).get("videos", [])
                if isinstance(data.get("data"), dict)
                else []
            )
            if not videos:
                videos = data.get("itemList", []) or data.get("items", []) or []

            if not videos and isinstance(data.get("data"), list):
                videos = data["data"]

            return videos

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._logger.warning(
                    "TikTok RapidAPI rate limit hit for hashtag '#%s'", hashtag
                )
                self._metrics.record_rate_limit()
            else:
                self._logger.warning(
                    "TikTok hashtag API error for '#%s': %s %s",
                    hashtag,
                    exc.response.status_code,
                    exc.response.text[:200],
                )
            self._metrics.record_request(success=False)
            return []

        except Exception as exc:
            self._logger.warning(
                "TikTok hashtag request failed for '#%s': %s", hashtag, exc
            )
            self._metrics.record_request(success=False)
            return []

    # ── BaseConnector implementation ─────────────────────────────────────────

    def fetch_trending(
        self,
        *,
        limit: int = 30,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """Fetch trending TikTok videos via the feed API."""
        effective_limit = min(limit, self._max_results)
        results: List[NormalizedContent] = []

        raw_videos = self._fetch_feed(region=region, count=effective_limit)
        self._metrics.record_request(success=bool(raw_videos))

        for raw in raw_videos:
            if len(results) >= effective_limit:
                break
            try:
                normalized = self.normalize_content(raw)
                if normalized and normalized.id:
                    results.append(normalized)
            except Exception as exc:
                self._logger.debug("TikTok normalize failed: %s", exc)

        self._logger.info(
            "TikTok: fetched %d trending videos (region=%s)",
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
        Search TikTok by keywords using intelligent multi-source retrieval.

        Priority Order:
            1. keyword search (via /feed/search) — highest relevance
            2. hashtag search (via /challenge/posts) — good relevance
            3. trending fallback — ONLY if steps 1+2 return zero results

        Uses QueryIntelligenceEngine to expand keywords into platform-
        optimized search variants for maximum coverage.
        """
        effective_limit = min(limit, self._max_results)
        results: List[NormalizedContent] = []
        seen_ids: set = set()

        # ── Step 0: Expand keywords via Query Intelligence ──
        try:
            from services.query_intelligence import QueryIntelligenceEngine
            qi = QueryIntelligenceEngine()
        except Exception as exc:
            self._logger.warning("QueryIntelligence unavailable: %s — using raw keywords", exc)
            qi = None

        for kw in keywords:
            if len(results) >= effective_limit:
                break

            # Expand keyword into variants
            if qi:
                ctx = qi.expand(kw)
                search_terms = [kw] + [t for t in ctx.normalized_terms if t != kw]
                hashtag_terms = [
                    v.lstrip("#") for v in ctx.tiktok_variants
                    if v.replace(" ", "") != kw  # avoid duplicating the keyword search
                ]
            else:
                search_terms = [kw]
                hashtag_terms = [kw.replace(" ", "")]

            self._logger.info(
                "[RETRIEVAL] platform=tiktok keyword=%r search_terms=%s hashtag_terms=%d",
                kw, search_terms[:4], len(hashtag_terms),
            )

            # ── Priority 1: Keyword search ──
            for term in search_terms[:4]:  # Cap to avoid excessive API calls
                if len(results) >= effective_limit:
                    break

                self._logger.info("TikTok: keyword search '%s'", term)
                raw_videos = self._search_videos(term, count=effective_limit)
                self._metrics.record_request(success=bool(raw_videos))

                for raw in raw_videos:
                    if len(results) >= effective_limit:
                        break
                    try:
                        normalized = self.normalize_content(raw)
                        if normalized and normalized.id not in seen_ids:
                            seen_ids.add(normalized.id)
                            results.append(normalized)
                    except Exception as exc:
                        self._logger.debug("TikTok normalize failed: %s", exc)

                self._throttle()

            self._logger.info(
                "[RETRIEVAL] platform=tiktok source=keyword_search results=%d",
                len(results),
            )

            # ── Priority 2: Hashtag search ──
            hashtag_results_start = len(results)
            for tag in hashtag_terms[:6]:  # Cap hashtag queries
                if len(results) >= effective_limit:
                    break

                clean_tag = tag.lstrip("#").replace(" ", "").strip()
                if not clean_tag or len(clean_tag) < 2:
                    continue

                self._logger.info("TikTok: hashtag search '#%s'", clean_tag)
                raw_videos = self._fetch_hashtag_videos(clean_tag, count=min(15, effective_limit))
                self._metrics.record_request(success=bool(raw_videos))

                for raw in raw_videos:
                    if len(results) >= effective_limit:
                        break
                    try:
                        normalized = self.normalize_content(raw)
                        if normalized and normalized.id not in seen_ids:
                            seen_ids.add(normalized.id)
                            results.append(normalized)
                    except Exception as exc:
                        self._logger.debug("TikTok normalize failed: %s", exc)

                self._throttle()

            self._logger.info(
                "[RETRIEVAL] platform=tiktok source=hashtag results=%d",
                len(results) - hashtag_results_start,
            )

        # ── Priority 3: Trending fallback — ONLY if no results ──
        if not results:
            self._logger.warning(
                "TikTok: zero results from keyword+hashtag search — falling back to trending"
            )
            trending = self._fetch_feed(count=min(effective_limit, 15))
            self._metrics.record_request(success=bool(trending))
            for raw in trending:
                if len(results) >= effective_limit:
                    break
                try:
                    normalized = self.normalize_content(raw)
                    if normalized and normalized.id not in seen_ids:
                        seen_ids.add(normalized.id)
                        results.append(normalized)
                except Exception as exc:
                    self._logger.debug("TikTok normalize failed: %s", exc)

            self._logger.info(
                "[RETRIEVAL] platform=tiktok source=trending_fallback results=%d",
                len(results),
            )

        self._logger.info(
            "TikTok: fetched %d total videos for keywords %s",
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
        """Fetch TikTok videos by hashtag."""
        effective_limit = min(limit, self._max_results)
        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for tag in hashtags:
            if len(results) >= effective_limit:
                break

            clean_tag = tag.lstrip("#").strip()
            if not clean_tag:
                continue

            self._logger.info("TikTok: fetching hashtag '#%s'", clean_tag)
            raw_videos = self._fetch_hashtag_videos(clean_tag, count=effective_limit)
            self._metrics.record_request(success=bool(raw_videos))

            for raw in raw_videos:
                if len(results) >= effective_limit:
                    break
                try:
                    normalized = self.normalize_content(raw)
                    if normalized and normalized.id not in seen_ids:
                        seen_ids.add(normalized.id)
                        results.append(normalized)
                except Exception as exc:
                    self._logger.debug("TikTok normalize failed: %s", exc)

            self._throttle()

        self._logger.info(
            "TikTok: fetched %d videos for hashtags %s",
            len(results), hashtags,
        )
        return results

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """Transform a TikTok video dict into NormalizedContent."""
        if not raw_payload or not isinstance(raw_payload, dict):
            return NormalizedContent(
                id="tiktok_unknown",
                platform="tiktok",
                content_type="video",
                title="Unknown TikTok Video",
            )

        video_id = str(
            raw_payload.get("video_id", "")
            or raw_payload.get("id", "")
            or raw_payload.get("aweme_id", "")
        )

        # Author info — guard against non-dict values
        author_raw = raw_payload.get("author") or raw_payload.get("author_info") or {}
        author = author_raw if isinstance(author_raw, dict) else {}
        author_name = (
            author.get("nickname", "")
            or author.get("uniqueId", "")
            or author.get("unique_id", "")
            or raw_payload.get("author_name", "")
            or (str(author_raw) if isinstance(author_raw, str) else "")
        )
        author_id = (
            author.get("uniqueId", "")
            or author.get("unique_id", "")
            or author.get("id", "")
        )
        author_followers = int(
            author.get("followerCount", 0)
            or author.get("follower_count", 0)
            or author.get("fans", 0)
            or 0
        )

        # Content — handle content_desc (list) alongside desc/title
        desc = raw_payload.get("desc", "") or raw_payload.get("description", "")
        if not desc:
            content_desc = raw_payload.get("content_desc")
            if isinstance(content_desc, list):
                desc = " ".join(str(s) for s in content_desc if s).strip()
            elif isinstance(content_desc, str):
                desc = content_desc
        if not desc:
            desc = raw_payload.get("title", "") or ""
        title = desc[:150] if desc else f"TikTok #{video_id}"

        # Hashtags from textExtra or description
        hashtags = []
        text_extra = raw_payload.get("textExtra", []) or raw_payload.get("text_extra", []) or []
        for te in text_extra:
            if isinstance(te, dict):
                ht = te.get("hashtagName", "") or te.get("hashtag_name", "")
                if ht:
                    hashtags.append(ht.lower())

        # Fallback: extract from desc or title
        if not hashtags:
            hashtag_source = desc or raw_payload.get("title", "") or ""
            if hashtag_source:
                hashtags = re.findall(r"#(\w+)", hashtag_source)[:20]

        # Audio — guard against music being a string instead of a dict
        music_raw = raw_payload.get("music") or raw_payload.get("music_info") or {}
        music = music_raw if isinstance(music_raw, dict) else {}
        audio_name = (
            music.get("title", "")
            or music.get("name", "")
            or (str(music_raw) if isinstance(music_raw, str) else "")
        )

        # Thumbnail — guard against video being a non-dict
        video_data_raw = raw_payload.get("video") or {}
        video_data = video_data_raw if isinstance(video_data_raw, dict) else {}
        thumbnail_url = (
            video_data.get("cover", "")
            or video_data.get("originCover", "")
            or video_data.get("dynamicCover", "")
            or raw_payload.get("cover", "")
            or raw_payload.get("origin_cover", "")
            or ""
        )

        # Timestamp
        create_time = raw_payload.get("createTime", 0) or raw_payload.get("create_time", 0)
        published_at = ""
        if create_time:
            try:
                published_at = datetime.fromtimestamp(
                    int(create_time), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                pass

        # Stats — handle both nested and flat formats
        stats = raw_payload.get("stats", {}) or raw_payload.get("statistics", {}) or {}
        views = int(
            stats.get("playCount", 0)
            or stats.get("play_count", 0)
            or raw_payload.get("play_count", 0)
            or raw_payload.get("playCount", 0)
            or 0
        )
        likes = int(
            stats.get("diggCount", 0)
            or stats.get("digg_count", 0)
            or raw_payload.get("digg_count", 0)
            or raw_payload.get("likes", 0)
            or 0
        )
        comments = int(
            stats.get("commentCount", 0)
            or stats.get("comment_count", 0)
            or raw_payload.get("comment_count", 0)
            or raw_payload.get("comments", 0)
            or 0
        )
        shares = int(
            stats.get("shareCount", 0)
            or stats.get("share_count", 0)
            or raw_payload.get("share_count", 0)
            or raw_payload.get("shares", 0)
            or 0
        )

        # Hook: first sentence of description
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
            source_url=f"https://www.tiktok.com/@{author_id}/video/{video_id}",
            raw_payload=raw_payload,
        )

    def health_check(self) -> ConnectorHealth:
        """Check TikTok connector health via a quick API ping."""
        start = time.time()

        if not self._api_key:
            return ConnectorHealth(
                platform="tiktok",
                status="unavailable",
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message="RAPIDAPI_KEY not configured in .env",
                credentials_configured=False,
            )

        try:
            client = self._get_client()
            # Light health probe — fetch 1 item from the feed
            resp = client.get(
                f"{_RAPIDAPI_BASE_URL}/feed/list",
                params={"region": "US", "count": 1},
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
            elif resp.status_code == 429:
                return ConnectorHealth(
                    platform="tiktok",
                    status="degraded",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message="Rate limit — free tier quota may be exhausted",
                    credentials_configured=True,
                )
            else:
                return ConnectorHealth(
                    platform="tiktok",
                    status="degraded",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message=f"HTTP {resp.status_code}",
                    credentials_configured=True,
                )

        except Exception as exc:
            return ConnectorHealth(
                platform="tiktok",
                status="unavailable",
                latency_ms=round((time.time() - start) * 1000, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc)[:200],
                credentials_configured=bool(self._api_key),
            )
