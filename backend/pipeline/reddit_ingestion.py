"""
Reddit ingestion module for Content Intelligence Platform.

Fetches posts from Reddit using OAuth2 API with:
  - Subreddit search by niche keywords
  - Automatic pagination
  - Exponential-backoff retry logic
  - Reuses the shared RawVideo dataclass
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import get_settings
from pipeline.ingestion import RawVideo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reddit API client
# ---------------------------------------------------------------------------
class RedditClient:
    """
    Thin abstraction over the Reddit OAuth2 API.

    Handles:
      - OAuth2 app-only authentication (script type)
      - Session management with connection pooling
      - Retry with exponential back-off on transient errors
      - Pagination via `after` tokens
    """

    AUTH_URL = "https://www.reddit.com/api/v1/access_token"
    BASE_URL = "https://oauth.reddit.com"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self._client_id = client_id or settings.reddit_client_id
        self._client_secret = client_secret or settings.reddit_client_secret
        self._user_agent = user_agent or settings.reddit_user_agent
        self._max_posts = settings.reddit_max_posts_per_query

        if not self._client_id or not self._client_secret:
            raise ValueError(
                "Reddit API credentials required. "
                "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env"
            )

        self._session = self._build_session()
        self._authenticate()

    # ----- Private helpers -------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _authenticate(self) -> None:
        """Obtain an OAuth2 access token using app-only (script) flow."""
        auth = (self._client_id, self._client_secret)
        headers = {"User-Agent": self._user_agent}
        data = {"grant_type": "client_credentials"}

        response = self._session.post(
            self.AUTH_URL, auth=auth, headers=headers, data=data, timeout=15
        )
        response.raise_for_status()
        token = response.json().get("access_token")

        if not token:
            raise ValueError("Failed to obtain Reddit access token.")

        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": self._user_agent,
            }
        )
        logger.info("Reddit OAuth2 authenticated successfully.")

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GET request against the Reddit OAuth API."""
        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug("GET %s?%s", url, urlencode(params or {}))

        response = self._session.get(url, params=params, timeout=15)
        response.raise_for_status()

        # Respect rate limit headers
        remaining = response.headers.get("X-Ratelimit-Remaining")
        reset = response.headers.get("X-Ratelimit-Reset")
        if remaining and float(remaining) < 5:
            wait = float(reset) if reset else 10
            logger.warning(
                "Reddit rate limit approaching (%s remaining). Sleeping %.0fs.",
                remaining, wait,
            )
            time.sleep(wait)

        return response.json()

    # ----- Search posts by subreddit / keyword ----------------------------

    def search_posts(
        self,
        query: str,
        *,
        sort: str = "top",
        time_filter: str = "month",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search Reddit for posts matching *query*.

        Uses /search endpoint which searches across all subreddits.
        Paginates until we hit the post limit.

        Args:
            query: Search keywords (maps to our niche keywords)
            sort: 'relevance', 'hot', 'top', 'new', 'comments'
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
            limit: Max posts to fetch (defaults to config setting)

        Returns list of raw Reddit post dicts.
        """
        max_posts = limit or self._max_posts
        all_posts: List[Dict[str, Any]] = []
        after: Optional[str] = None
        page = 0

        while len(all_posts) < max_posts:
            page += 1
            batch_size = min(100, max_posts - len(all_posts))  # Reddit max per page is 100

            params: Dict[str, Any] = {
                "q": query,
                "sort": sort,
                "t": time_filter,
                "limit": batch_size,
                "type": "link",  # Posts only (not comments or subreddits)
                "restrict_sr": "false",
            }
            if after:
                params["after"] = after

            try:
                data = self._get("search", params)
            except requests.HTTPError as exc:
                logger.error(
                    "Reddit search error (page %d, query='%s'): %s",
                    page, query, exc,
                )
                break

            listing = data.get("data", {})
            children = listing.get("children", [])

            if not children:
                break

            for child in children:
                post = child.get("data", {})
                # Skip promoted/ad posts
                if post.get("promoted") or post.get("is_self") is None:
                    continue
                all_posts.append(post)

            after = listing.get("after")
            if not after:
                break

            logger.info(
                "Query '%s' — fetched page %d (%d posts so far)",
                query, page, len(all_posts),
            )

        logger.info(
            "Reddit search complete for '%s': %d posts collected.",
            query, len(all_posts),
        )
        return all_posts[:max_posts]

    # ----- Parse into RawVideo objects ------------------------------------

    @staticmethod
    def parse_post(post: Dict[str, Any], niche: str) -> RawVideo:
        """Convert a Reddit post dict into a RawVideo dataclass."""
        # Build a clean description from title + selftext
        selftext = post.get("selftext", "") or ""
        description = selftext[:2000] if selftext else post.get("title", "")

        # Reddit thumbnail handling
        thumbnail = post.get("thumbnail", "")
        if thumbnail in ("self", "default", "nsfw", "spoiler", ""):
            # Try to get preview image instead
            previews = post.get("preview", {}).get("images", [])
            if previews:
                thumbnail = previews[0].get("source", {}).get("url", "")
            else:
                thumbnail = ""

        # Convert UTC timestamp
        created_utc = post.get("created_utc", 0)
        published_at = ""
        if created_utc:
            published_at = datetime.fromtimestamp(
                created_utc, tz=timezone.utc
            ).isoformat()

        return RawVideo(
            video_id=f"reddit_{post.get('id', '')}",
            title=post.get("title", ""),
            channel=f"r/{post.get('subreddit', 'unknown')}",
            description=description,
            published_at=published_at,
            thumbnail_url=thumbnail,
            views=max(int(post.get("score", 0)), 0),  # Upvotes as views
            likes=max(int(post.get("ups", 0)), 0),
            comments=max(int(post.get("num_comments", 0)), 0),
            niche=niche,
            platform="reddit",
        )


# ---------------------------------------------------------------------------
# Public high-level function
# ---------------------------------------------------------------------------
def ingest_reddit_posts(niches: Optional[List[str]] = None) -> List[RawVideo]:
    """
    Ingest posts for each configured niche from Reddit.

    Returns a list of RawVideo objects ready for processing.
    Silently returns empty list if Reddit credentials are not configured.
    """
    settings = get_settings()

    # Skip Reddit ingestion if credentials are not configured
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        logger.info("Reddit credentials not configured — skipping Reddit ingestion.")
        return []

    niches = niches or settings.niche_keywords
    all_posts: List[RawVideo] = []

    try:
        client = RedditClient()
    except Exception as exc:
        logger.error("Failed to initialize Reddit client: %s", exc)
        return []

    for niche in niches:
        logger.info("▶ Ingesting Reddit posts for niche: '%s'", niche)
        try:
            raw_posts = client.search_posts(niche)
            if not raw_posts:
                logger.warning("No Reddit posts found for niche '%s'.", niche)
                continue

            posts = [client.parse_post(post, niche) for post in raw_posts]
            all_posts.extend(posts)
            logger.info(
                "✔ Ingested %d Reddit posts for niche '%s'.", len(posts), niche
            )
        except Exception as exc:
            logger.error(
                "Failed to ingest Reddit posts for niche '%s': %s",
                niche, exc, exc_info=True,
            )

    logger.info("Total Reddit posts ingested: %d", len(all_posts))
    return all_posts
