"""
Ingestion module for Content Intelligence Platform.

Fetches video data from YouTube Data API v3 with:
  - API client abstraction
  - Automatic pagination
  - Exponential-backoff retry logic
  - Structured return objects (dataclasses)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import get_settings

logger = logging.getLogger(__name__)


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
      - Pagination across search + videos.list endpoints
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.youtube_api_key
        if not self._api_key:
            raise ValueError(
                "YouTube API key is required. Set YOUTUBE_API_KEY in .env"
            )

        self._max_results = settings.youtube_max_results_per_query
        self._max_pages = settings.youtube_max_pages
        self._retry_attempts = settings.youtube_retry_attempts
        self._retry_delay = settings.youtube_retry_delay_seconds

        # Persistent session with retry strategy
        self._session = self._build_session()

    # ----- Private helpers -------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=self._retry_attempts,
            backoff_factor=self._retry_delay,
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

    # ----- Search videos ---------------------------------------------------

    def search_videos(
        self,
        query: str,
        *,
        order: str = "viewCount",
        published_after: Optional[str] = None,
    ) -> List[str]:
        """
        Search YouTube for video IDs matching *query*.

        Paginates up to ``self._max_pages`` pages, returning a flat list of
        video IDs.
        """
        video_ids: List[str] = []
        page_token: Optional[str] = None

        for page in range(1, self._max_pages + 1):
            params: Dict[str, Any] = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "order": order,
                "maxResults": self._max_results,
                "relevanceLanguage": "en",
            }

            if page_token:
                params["pageToken"] = page_token
            if published_after:
                params["publishedAfter"] = published_after

            try:
                data = self._get("search", params)
            except requests.HTTPError as exc:
                logger.error(
                    "YouTube search API error (page %d, query='%s'): %s",
                    page,
                    query,
                    exc,
                )
                break

            items = data.get("items", [])
            for item in items:
                vid = item.get("id", {}).get("videoId")
                if vid:
                    video_ids.append(vid)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

            logger.info(
                "Query '%s' — fetched page %d (%d IDs so far)",
                query,
                page,
                len(video_ids),
            )

        logger.info(
            "Search complete for '%s': %d video IDs collected.", query, len(video_ids)
        )
        return video_ids

    # ----- Fetch video details ---------------------------------------------

    def get_video_details(self, video_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch full details (snippet + statistics) for a batch of video IDs.

        The API accepts up to 50 IDs per call, so we chunk automatically.
        """
        all_items: List[Dict[str, Any]] = []
        chunk_size = 50

        for i in range(0, len(video_ids), chunk_size):
            chunk = video_ids[i : i + chunk_size]
            params = {
                "part": "snippet,statistics",
                "id": ",".join(chunk),
            }
            try:
                data = self._get("videos", params)
                all_items.extend(data.get("items", []))
            except requests.HTTPError as exc:
                logger.error(
                    "YouTube videos.list error (chunk %d–%d): %s",
                    i,
                    i + len(chunk),
                    exc,
                )

        logger.info("Fetched details for %d videos.", len(all_items))
        return all_items

    # ----- Parse into structured objects -----------------------------------

    @staticmethod
    def parse_video_item(item: Dict[str, Any], niche: str) -> RawVideo:
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
            video_id=item["id"],
            title=snippet.get("title", ""),
            channel=snippet.get("channelTitle", ""),
            description=snippet.get("description", ""),
            published_at=snippet.get("publishedAt", ""),
            thumbnail_url=thumb_url,
            views=int(stats.get("viewCount", 0)),
            likes=int(stats.get("likeCount", 0)),
            comments=int(stats.get("commentCount", 0)),
            niche=niche,
        )


# ---------------------------------------------------------------------------
# Public high-level function
# ---------------------------------------------------------------------------
def ingest_videos(niches: Optional[List[str]] = None) -> List[RawVideo]:
    """
    Ingest videos for each configured niche from YouTube.

    Returns a list of ``RawVideo`` objects ready for processing.
    """
    settings = get_settings()
    niches = niches or settings.niche_keywords

    client = YouTubeClient()
    all_videos: List[RawVideo] = []

    for niche in niches:
        logger.info("▶ Ingesting niche: '%s'", niche)
        try:
            video_ids = client.search_videos(niche)
            if not video_ids:
                logger.warning("No video IDs found for niche '%s'.", niche)
                continue

            details = client.get_video_details(video_ids)
            videos = [
                client.parse_video_item(item, niche) for item in details
            ]
            all_videos.extend(videos)
            logger.info(
                "✔ Ingested %d videos for niche '%s'.", len(videos), niche
            )
        except Exception as exc:
            logger.error(
                "Failed to ingest niche '%s': %s", niche, exc, exc_info=True
            )

    logger.info("Total raw videos ingested: %d", len(all_videos))
    return all_videos
