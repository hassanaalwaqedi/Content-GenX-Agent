"""
Abstract Base Connector for the Content Intelligence Platform.

Defines the contract that ALL platform connectors must implement.
Provides built-in utilities for:
    - Retry with exponential backoff + jitter
    - Rate-limit tracking
    - Structured per-request logging
    - Timeout protection
    - Metrics collection

Usage:
    class MyConnector(BaseConnector):
        platform_id = "myplatform"
        platform_name = "My Platform"

        def fetch_trending(self, ...) -> List[NormalizedContent]: ...
        def fetch_by_keywords(self, ...) -> List[NormalizedContent]: ...
        ...
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

from connectors.models import ConnectorHealth, ConnectorMetrics, NormalizedContent

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Retry decorator with exponential backoff + jitter
# ---------------------------------------------------------------------------
def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    jitter: float = 1.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator: retry a function with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        jitter: Random jitter range added to delay.
        retryable_exceptions: Tuple of exception types that trigger a retry.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Optional[Exception] = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        delay += random.uniform(0, jitter)
                        logger.warning(
                            "[%s] Attempt %d/%d failed: %s — retrying in %.1fs",
                            func.__qualname__,
                            attempt + 1,
                            max_retries + 1,
                            exc,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "[%s] All %d attempts exhausted: %s",
                            func.__qualname__,
                            max_retries + 1,
                            exc,
                        )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Abstract Base Connector
# ---------------------------------------------------------------------------
class BaseConnector(ABC):
    """
    Abstract base class for all platform connectors.

    Every connector must implement the five core methods:
        - fetch_trending()
        - fetch_by_keywords()
        - fetch_by_hashtags()
        - normalize_content()
        - health_check()

    Provides built-in:
        - Metrics tracking (requests, failures, retries, rate limits)
        - Structured logging for every operation
        - Configurable request delays and timeouts
    """

    # Subclasses MUST set these
    platform_id: str = ""
    platform_name: str = ""

    def __init__(
        self,
        *,
        request_delay: float = 1.0,
        request_timeout: int = 15,
        max_retries: int = 3,
    ) -> None:
        if not self.platform_id or not self.platform_name:
            raise ValueError(
                f"{self.__class__.__name__} must define platform_id and platform_name"
            )
        self._request_delay = request_delay
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._metrics = ConnectorMetrics(platform=self.platform_id)
        self._logger = logging.getLogger(f"connector.{self.platform_id}")

    @property
    def metrics(self) -> ConnectorMetrics:
        """Return the current metrics for this connector."""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset metrics for a new pipeline run."""
        self._metrics = ConnectorMetrics(platform=self.platform_id)

    # ---- Throttling --------------------------------------------------------

    def _throttle(self, extra_delay: float = 0.0) -> None:
        """
        Apply a configurable delay between requests.

        Includes a small random jitter to avoid thundering herd.
        """
        delay = self._request_delay + extra_delay + random.uniform(0, 0.5)
        if delay > 0:
            time.sleep(delay)

    # ---- Logging helpers ---------------------------------------------------

    def _log_fetch_start(self, method: str, **kwargs: Any) -> float:
        """Log the start of a fetch operation. Returns start time."""
        self._logger.info(
            "▶ [%s] %s.%s(%s)",
            self.platform_id,
            self.__class__.__name__,
            method,
            ", ".join(f"{k}={v!r}" for k, v in kwargs.items()),
        )
        return time.time()

    def _log_fetch_end(
        self, method: str, start_time: float, count: int
    ) -> None:
        """Log the completion of a fetch operation."""
        elapsed = time.time() - start_time
        self._metrics.items_extracted += count
        self._logger.info(
            "✔ [%s] %s.%s → %d items in %.1fs",
            self.platform_id,
            self.__class__.__name__,
            method,
            count,
            elapsed,
        )

    def _log_fetch_error(self, method: str, error: Exception) -> None:
        """Log a fetch error."""
        self._metrics.record_request(success=False)
        self._logger.error(
            "✕ [%s] %s.%s failed: %s",
            self.platform_id,
            self.__class__.__name__,
            method,
            error,
        )

    # ---- Abstract methods (connector contract) -----------------------------

    @abstractmethod
    def fetch_trending(
        self,
        *,
        limit: int = 30,
        region: str = "US",
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Fetch trending/popular content from the platform.

        Args:
            limit: Maximum number of items to return.
            region: Geographic region code (ISO 3166-1 alpha-2).

        Returns:
            List of NormalizedContent objects.
        """
        ...

    @abstractmethod
    def fetch_by_keywords(
        self,
        keywords: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Search for content matching given keywords.

        Args:
            keywords: Search terms to query.
            limit: Maximum number of items per keyword.

        Returns:
            List of NormalizedContent objects.
        """
        ...

    @abstractmethod
    def fetch_by_hashtags(
        self,
        hashtags: List[str],
        *,
        limit: int = 25,
        **kwargs: Any,
    ) -> List[NormalizedContent]:
        """
        Search for content matching given hashtags.

        Args:
            hashtags: Hashtag strings (without # prefix).
            limit: Maximum number of items per hashtag.

        Returns:
            List of NormalizedContent objects.
        """
        ...

    @abstractmethod
    def normalize_content(
        self, raw_payload: Dict[str, Any]
    ) -> NormalizedContent:
        """
        Transform a raw platform API response into NormalizedContent.

        Args:
            raw_payload: Raw JSON dict from the platform API.

        Returns:
            A NormalizedContent instance.

        This method MUST NOT raise exceptions. Return a best-effort
        NormalizedContent with whatever fields can be extracted.
        """
        ...

    @abstractmethod
    def health_check(self) -> ConnectorHealth:
        """
        Check if the connector is operational.

        Returns:
            ConnectorHealth with status, latency, and any error info.

        Must complete within 10 seconds. Should test:
            - Credential validity
            - API reachability
            - Rate limit status
        """
        ...

    # ---- Convenience: safe fetch wrapper -----------------------------------

    def safe_fetch_trending(
        self, *, limit: int = 30, region: str = "US", **kwargs: Any
    ) -> List[NormalizedContent]:
        """
        Fetch trending with full error handling and daily rate limiting.

        Never raises — returns empty list on failure or rate limit.
        """
        from connectors.rate_limiter import check_rate_limit, record_scan

        allowed, msg = check_rate_limit(self.platform_id)
        if not allowed:
            self._logger.warning("⛔ %s", msg)
            return []

        start = self._log_fetch_start("fetch_trending", limit=limit, region=region)
        try:
            results = self.fetch_trending(limit=limit, region=region, **kwargs)
            self._metrics.record_request(success=True)
            self._log_fetch_end("fetch_trending", start, len(results))
            record_scan(self.platform_id)
            return results
        except Exception as exc:
            self._log_fetch_error("fetch_trending", exc)
            return []

    def safe_fetch_by_keywords(
        self, keywords: List[str], *, limit: int = 25, **kwargs: Any
    ) -> List[NormalizedContent]:
        """
        Fetch by keywords with full error handling and daily rate limiting.

        Never raises — returns empty list on failure or rate limit.
        """
        from connectors.rate_limiter import check_rate_limit, record_scan

        allowed, msg = check_rate_limit(self.platform_id)
        if not allowed:
            self._logger.warning("⛔ %s", msg)
            return []

        start = self._log_fetch_start(
            "fetch_by_keywords", keywords=keywords, limit=limit
        )
        try:
            results = self.fetch_by_keywords(keywords, limit=limit, **kwargs)
            self._metrics.record_request(success=True)
            self._log_fetch_end("fetch_by_keywords", start, len(results))
            record_scan(self.platform_id)
            return results
        except Exception as exc:
            self._log_fetch_error("fetch_by_keywords", exc)
            return []

    def safe_fetch_by_hashtags(
        self, hashtags: List[str], *, limit: int = 25, **kwargs: Any
    ) -> List[NormalizedContent]:
        """
        Fetch by hashtags with full error handling and daily rate limiting.

        Never raises — returns empty list on failure or rate limit.
        """
        from connectors.rate_limiter import check_rate_limit, record_scan

        allowed, msg = check_rate_limit(self.platform_id)
        if not allowed:
            self._logger.warning("⛔ %s", msg)
            return []

        start = self._log_fetch_start(
            "fetch_by_hashtags", hashtags=hashtags, limit=limit
        )
        try:
            results = self.fetch_by_hashtags(hashtags, limit=limit, **kwargs)
            self._metrics.record_request(success=True)
            self._log_fetch_end("fetch_by_hashtags", start, len(results))
            record_scan(self.platform_id)
            return results
        except Exception as exc:
            self._log_fetch_error("fetch_by_hashtags", exc)
            return []

