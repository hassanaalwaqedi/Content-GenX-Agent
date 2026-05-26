"""
Instagram Connector for the Content Intelligence Platform.

Uses the RapidAPI "Instagram" (instagram120) API to fetch public
Instagram content from creator profiles.

Strategy:
    Instead of hashtag search (which Instagram has locked down), we use
    profile-based discovery — fetching recent posts from curated
    influencer/creator accounts per niche. This is more reliable and
    produces higher-quality intelligence data.

Dependencies:
    pip install httpx  (already in requirements)

Environment:
    RAPIDAPI_KEY=<your-key>
    INSTAGRAM_ENABLED=true
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
_RAPIDAPI_HOST = "instagram120.p.rapidapi.com"
_RAPIDAPI_BASE_URL = f"https://{_RAPIDAPI_HOST}/api/instagram"

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


class InstagramConnector(BaseConnector):
    """
    Instagram connector using RapidAPI (instagram120).

    Fetches posts from public creator profiles — no login required.
    Free tier refreshes monthly (~100-500 requests).
    """

    platform_id = "instagram"
    platform_name = "Instagram"

    def __init__(self) -> None:
        from config import get_settings

        settings = get_settings()
        super().__init__(
            request_delay=getattr(settings, "instagram_request_delay", 3.0),
            request_timeout=30,
            max_retries=2,
        )
        self._max_results = getattr(settings, "instagram_max_results", 30)
        self._api_key = getattr(settings, "rapidapi_key", "")
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """Lazily initialize the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self._request_timeout,
                headers={
                    "Content-Type": "application/json",
                    "x-rapidapi-host": _RAPIDAPI_HOST,
                    "x-rapidapi-key": self._api_key,
                },
            )
        return self._client

    def _fetch_user_posts(
        self, username: str, max_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts from a specific Instagram user profile.

        The instagram120 API returns:
            { result: { edges: [ { node: { ...post } }, ... ] } }
        """
        client = self._get_client()
        try:
            resp = client.post(
                f"{_RAPIDAPI_BASE_URL}/posts",
                json={"username": username, "maxid": max_id},
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                return data if isinstance(data, list) else []

            # Primary format: result.edges[].node
            result = data.get("result", data)
            if isinstance(result, dict):
                edges = result.get("edges", [])
                if edges and isinstance(edges, list):
                    posts = []
                    for edge in edges:
                        node = edge.get("node", edge) if isinstance(edge, dict) else edge
                        if isinstance(node, dict):
                            posts.append(node)
                    if posts:
                        return posts

            # Fallback: try flat list formats
            return (
                data.get("items", [])
                or data.get("posts", [])
                or data.get("data", [])
                or []
            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._logger.warning(
                    "Instagram RapidAPI rate limit hit for @%s", username
                )
                self._metrics.record_rate_limit()
            else:
                self._logger.warning(
                    "Instagram API error for @%s: %s %s",
                    username, exc.response.status_code, exc.response.text[:200],
                )
            self._metrics.record_request(success=False)
            return []

        except Exception as exc:
            self._logger.warning(
                "Instagram API request failed for @%s: %s", username, exc
            )
            self._metrics.record_request(success=False)
            return []

    def _fetch_user_profile(self, username: str) -> Dict[str, Any]:
        """Fetch profile metadata for a user."""
        client = self._get_client()
        try:
            resp = client.post(
                f"{_RAPIDAPI_BASE_URL}/profile",
                json={"username": username},
            )
            resp.raise_for_status()
            return resp.json() or {}
        except Exception as exc:
            self._logger.debug("Profile fetch failed for @%s: %s", username, exc)
            return {}

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

        Since Instagram has no public trending API, we aggregate recent
        posts from curated high-engagement accounts.
        """
        # Use a subset of default creators to stay within rate limits
        creators = kwargs.get("creators", _ALL_DEFAULT_CREATORS[:8])
        per_creator = max(limit // len(creators), 2) if creators else 5

        results: List[NormalizedContent] = []
        seen_ids: set = set()

        for username in creators:
            if len(results) >= limit:
                break

            self._logger.info("Instagram: scanning @%s", username)
            posts = self._fetch_user_posts(username)
            self._metrics.record_request(success=bool(posts))

            for post in posts[:per_creator]:
                try:
                    normalized = self._normalize_post(post, username)
                    if normalized and normalized.id not in seen_ids:
                        seen_ids.add(normalized.id)
                        results.append(normalized)
                except Exception as exc:
                    self._logger.debug("Skip IG post: %s", exc)

            # Throttle between creators
            self._throttle(extra_delay=0.5)

        self._logger.info(
            "Instagram: fetched %d posts from %d creators",
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
            2. Try hashtag-based retrieval for each generated hashtag
            3. Fall back to keyword-matched creator profiles
            4. Score every fetched post locally and reject irrelevant content
        """
        self._logger.info(
            "Instagram: intelligent keyword search for: %s", keywords,
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
                # Extract hashtag targets (strip # prefix for API)
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

        results: List[NormalizedContent] = []
        seen_ids: set = set()

        # ── Step 1: Hashtag-based retrieval ──
        # Try fetching posts by hashtag (if API supports it)
        for hashtag in ig_hashtags[:8]:
            if len(results) >= limit:
                break

            posts = self._fetch_hashtag_posts(hashtag)
            self._metrics.record_request(success=bool(posts))

            for post in posts:
                if len(results) >= limit:
                    break
                try:
                    normalized = self._normalize_post(post)
                    if normalized and normalized.id not in seen_ids:
                        seen_ids.add(normalized.id)
                        results.append(normalized)
                except Exception as exc:
                    self._logger.debug("Skip IG post: %s", exc)

            self._throttle(extra_delay=0.5)

        hashtag_count = len(results)
        self._logger.info(
            "[RETRIEVAL] platform=instagram source=hashtag results=%d",
            hashtag_count,
        )

        # ── Step 2: Creator profile scanning (fallback / supplemental) ──
        if len(results) < limit:
            # Find matching niche creators for the keywords
            creators_to_scan: List[str] = []

            # Match against niche categories
            kw_lower = [kw.lower() for kw in (creator_keywords or keywords)]
            for niche, creators in _DEFAULT_CREATORS.items():
                if any(niche in kw or kw in niche for kw in kw_lower):
                    creators_to_scan.extend(creators)

            # If no niche match, try general + keyword-as-username
            if not creators_to_scan:
                creators_to_scan.extend(_DEFAULT_CREATORS.get("general", []))
                for kw in keywords:
                    clean = re.sub(r"[^a-zA-Z0-9._]", "", kw.lower())
                    if clean and clean not in creators_to_scan:
                        creators_to_scan.append(clean)

            # Deduplicate
            creators_to_scan = list(dict.fromkeys(creators_to_scan))[:10]

            for username in creators_to_scan:
                if len(results) >= limit:
                    break

                self._logger.info("Instagram: scanning @%s", username)
                posts = self._fetch_user_posts(username)
                self._metrics.record_request(success=bool(posts))

                for post in posts[:5]:  # Limit per creator
                    if len(results) >= limit:
                        break
                    try:
                        normalized = self._normalize_post(post, username)
                        if normalized and normalized.id not in seen_ids:
                            seen_ids.add(normalized.id)
                            results.append(normalized)
                    except Exception as exc:
                        self._logger.debug("Skip IG post: %s", exc)

                self._throttle(extra_delay=0.5)

        creator_count = len(results) - hashtag_count
        self._logger.info(
            "[RETRIEVAL] platform=instagram source=creator_scan results=%d",
            creator_count,
        )

        # ── Step 3: Local relevance scoring ──
        if query_context and results:
            try:
                from analytics.relevance_engine import ContentRelevanceEngine
                relevance = ContentRelevanceEngine()
                scored_results: List[NormalizedContent] = []

                for item in results:
                    # Score using the raw dict representation
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
            "Instagram: fetched %d relevant posts for keywords %s",
            len(results), keywords,
        )
        return results

    def _fetch_hashtag_posts(
        self, hashtag: str
    ) -> List[Dict[str, Any]]:
        """
        Attempt to fetch Instagram posts by hashtag.

        Tries the instagram120 hashtag endpoint with graceful fallback.
        If the API doesn't support hashtag search, returns empty list.
        """
        client = self._get_client()
        try:
            # Try hashtag endpoint (may not be available on all API tiers)
            resp = client.post(
                f"{_RAPIDAPI_BASE_URL}/hashtag",
                json={"hashtag": hashtag},
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    result = data.get("result", data)
                    if isinstance(result, dict):
                        edges = result.get("edges", [])
                        if edges and isinstance(edges, list):
                            posts = []
                            for edge in edges:
                                node = edge.get("node", edge) if isinstance(edge, dict) else edge
                                if isinstance(node, dict):
                                    posts.append(node)
                            if posts:
                                self._logger.info(
                                    "Instagram: hashtag '#%s' returned %d posts",
                                    hashtag, len(posts),
                                )
                                return posts
                    # Try flat format
                    items = (
                        data.get("items", [])
                        or data.get("posts", [])
                        or data.get("data", [])
                        or []
                    )
                    if items:
                        return items

            elif resp.status_code == 429:
                self._logger.warning("Instagram rate limit hit for hashtag '#%s'", hashtag)
                self._metrics.record_rate_limit()
            else:
                self._logger.debug(
                    "Instagram hashtag endpoint returned %d for '#%s' — endpoint may not be available",
                    resp.status_code, hashtag,
                )
        except Exception as exc:
            self._logger.debug(
                "Instagram hashtag fetch failed for '#%s': %s", hashtag, exc
            )

        return []

    def fetch_by_hashtags(
        self,
        hashtags: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch Instagram posts by hashtag.

        Uses intelligent expansion and the hashtag endpoint where available,
        falling back to keyword-based search.
        """
        # Map hashtags to keywords and use the intelligent keyword search
        keywords = [tag.lstrip("#").strip() for tag in hashtags if tag.strip()]
        return self.fetch_by_keywords(keywords, limit=limit)

    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """
        Transform a raw API post dict into NormalizedContent.

        Required by BaseConnector abstract contract.
        """
        result = self._normalize_post(raw_payload)
        if result is None:
            # Fallback: return a minimal NormalizedContent
            return NormalizedContent(
                id=f"ig_{raw_payload.get('pk', 'unknown')}",
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

    def _normalize_post(
        self, raw: Dict[str, Any], fallback_username: str = ""
    ) -> Optional[NormalizedContent]:
        """
        Transform a raw API post dict into NormalizedContent.

        Handles multiple response formats from the instagram120 API.
        """
        if not raw or not isinstance(raw, dict):
            return None

        # ── Extract post ID ──
        post_id = str(
            raw.get("pk", "")
            or raw.get("id", "")
            or raw.get("code", "")
            or raw.get("shortcode", "")
        )
        if not post_id:
            return None

        shortcode = raw.get("code", "") or raw.get("shortcode", post_id)

        # ── Caption / Title ──
        caption_obj = raw.get("caption", {})
        if isinstance(caption_obj, dict):
            caption_text = caption_obj.get("text", "") or ""
        elif isinstance(caption_obj, str):
            caption_text = caption_obj
        else:
            caption_text = ""

        title_lines = caption_text.split("\n")
        title = title_lines[0][:150] if title_lines[0] else f"IG Post {shortcode}"

        # ── Author ──
        user_obj = raw.get("user", {}) or raw.get("owner", {}) or {}
        author = (
            user_obj.get("username", "")
            or user_obj.get("full_name", "")
            or fallback_username
        )
        author_followers = int(user_obj.get("follower_count", 0) or 0)

        # ── Content type ──
        media_type = raw.get("media_type", 0)
        video_duration = raw.get("video_duration", 0) or 0
        is_video = media_type == 2 or raw.get("is_video", False)

        if is_video:
            content_type = "reel" if 0 < video_duration <= 90 else "video"
        else:
            content_type = "post" if media_type == 1 else "carousel" if media_type == 8 else "post"

        # ── Metrics ──
        likes = int(raw.get("like_count", 0) or raw.get("likes", 0) or 0)
        comments = int(
            raw.get("comment_count", 0) or raw.get("comments", 0) or 0
        )
        views = int(
            raw.get("play_count", 0)
            or raw.get("view_count", 0)
            or raw.get("video_view_count", 0)
            or 0
        )

        # For non-video posts, estimate views from likes
        if not is_video and views == 0:
            views = likes * 10

        # ── Hashtags ──
        hashtags = re.findall(r"#(\w+)", caption_text)[:20]

        # ── Published date ──
        taken_at = raw.get("taken_at", 0) or raw.get("taken_at_timestamp", 0)
        if taken_at:
            try:
                published_at = datetime.fromtimestamp(
                    int(taken_at), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                published_at = ""
        else:
            published_at = ""

        # ── Thumbnail ──
        thumbnail_url = ""
        image_versions = raw.get("image_versions2", {})
        if isinstance(image_versions, dict):
            candidates = image_versions.get("candidates", [])
            if candidates and isinstance(candidates, list):
                thumbnail_url = candidates[0].get("url", "")
        if not thumbnail_url:
            thumbnail_url = raw.get("thumbnail_url", "") or raw.get("display_url", "")

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
            source_url=f"https://www.instagram.com/p/{shortcode}/",
            raw_payload=raw,
        )

    def health_check(self) -> ConnectorHealth:
        """Check Instagram connector health via a quick API ping."""
        start = time.time()

        if not self._api_key:
            return ConnectorHealth(
                platform="instagram",
                status="unavailable",
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message="RAPIDAPI_KEY not configured in .env",
                credentials_configured=False,
            )

        try:
            client = self._get_client()
            resp = client.post(
                f"{_RAPIDAPI_BASE_URL}/profile",
                json={"username": "instagram"},
            )
            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                return ConnectorHealth(
                    platform="instagram",
                    status="healthy",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message="",
                    credentials_configured=True,
                )
            elif resp.status_code == 429:
                return ConnectorHealth(
                    platform="instagram",
                    status="degraded",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message="Rate limit — free tier quota may be exhausted",
                    credentials_configured=True,
                )
            else:
                return ConnectorHealth(
                    platform="instagram",
                    status="degraded",
                    latency_ms=round(latency, 1),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error_message=f"HTTP {resp.status_code}",
                    credentials_configured=True,
                )

        except Exception as exc:
            return ConnectorHealth(
                platform="instagram",
                status="unavailable",
                latency_ms=round((time.time() - start) * 1000, 1),
                last_check=datetime.now(timezone.utc).isoformat(),
                error_message=str(exc)[:200],
                credentials_configured=bool(self._api_key),
            )
