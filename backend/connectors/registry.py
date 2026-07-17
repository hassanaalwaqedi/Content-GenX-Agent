"""
Connector Registry for the Content Intelligence Platform.

Auto-discovers available connectors based on configured credentials
and provides a single access point for the pipeline to obtain
connector instances.

Usage:
    registry = ConnectorRegistry()
    available = registry.get_available()          # ["youtube", "reddit", ...]
    connector = registry.get_connector("tiktok")  # TikTokConnector or None
    health = registry.health_check_all()          # {platform: ConnectorHealth}
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from connectors.base import BaseConnector
from connectors.models import ConnectorHealth

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """
    Singleton registry that discovers and manages all platform connectors.

    Connectors are lazily initialized on first access. A connector is
    considered "available" only if its required credentials are configured.
    """

    _instance: Optional["ConnectorRegistry"] = None
    _connectors: Dict[str, BaseConnector]

    def __new__(cls) -> "ConnectorRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connectors = {}
            cls._instance._discovered = False
        return cls._instance

    def _discover(self) -> None:
        """
        Lazily discover and initialize all available connectors.

        Imports are deferred so that missing optional dependencies
        (e.g. TikTokApi, instaloader) don't crash the application
        at import time.
        """
        if self._discovered:
            return
        self._discovered = True

        from core.config import get_settings

        settings = get_settings()

        # ---- YouTube -------------------------------------------------------
        try:
            from connectors.youtube_connector import YouTubeConnector

            if settings.youtube_api_key and settings.youtube_api_key.strip().lower() not in (
                "your_youtube_api_key_here",
                "your_api_key_here",
                "change_me",
                "xxx",
                "",
            ):
                connector = YouTubeConnector()
                self._connectors["youtube"] = connector
                logger.info("✔ YouTube connector registered.")
            else:
                logger.info("⊘ YouTube connector skipped (no API key).")
        except Exception as exc:
            logger.warning("YouTube connector init failed: %s", exc)

        # ---- Reddit (Apify) --------------------------------------------------
        try:
            from connectors.reddit_connector import RedditConnector

            if getattr(settings, "reddit_enabled", False) and getattr(
                settings, "apify_api_token", ""
            ):
                connector = RedditConnector()
                self._connectors["reddit"] = connector
                logger.info("✔ Reddit connector registered (Apify).")
            elif getattr(settings, "reddit_enabled", False):
                logger.info(
                    "⊘ Reddit connector skipped (APIFY_API_TOKEN not set)."
                )
            else:
                logger.info("⊘ Reddit connector skipped (disabled).")
        except Exception as exc:
            logger.warning("Reddit connector init failed: %s", exc)

        # ---- TikTok (Apify) -------------------------------------------------
        try:
            from connectors.tiktok_connector import TikTokConnector

            if getattr(settings, "tiktok_enabled", False) and getattr(
                settings, "apify_api_token", ""
            ):
                connector = TikTokConnector()
                self._connectors["tiktok"] = connector
                logger.info("✔ TikTok connector registered (Apify).")
            elif getattr(settings, "tiktok_enabled", False):
                logger.info(
                    "⊘ TikTok connector skipped (APIFY_API_TOKEN not set)."
                )
            else:
                logger.info("⊘ TikTok connector skipped (disabled).")
        except Exception as exc:
            logger.warning("TikTok connector init failed: %s", exc)

        # ---- Instagram (Apify) ----------------------------------------------
        try:
            from connectors.instagram_connector import InstagramConnector

            if getattr(settings, "instagram_enabled", False) and getattr(
                settings, "apify_api_token", ""
            ):
                connector = InstagramConnector()
                self._connectors["instagram"] = connector
                logger.info("✔ Instagram connector registered (Apify).")
            elif getattr(settings, "instagram_enabled", False):
                logger.info(
                    "⊘ Instagram connector skipped (APIFY_API_TOKEN not set)."
                )
            else:
                logger.info("⊘ Instagram connector skipped (disabled).")
        except Exception as exc:
            logger.warning("Instagram connector init failed: %s", exc)

        logger.info(
            "Connector registry: %d connector(s) available: %s",
            len(self._connectors),
            list(self._connectors.keys()),
        )

    # ---- Public API --------------------------------------------------------

    def get_connector(self, platform_id: str) -> Optional[BaseConnector]:
        """
        Return the connector for a given platform, or None if unavailable.

        Args:
            platform_id: Platform identifier (e.g. "youtube", "tiktok").
        """
        self._discover()
        return self._connectors.get(platform_id)

    def get_available(self) -> List[str]:
        """Return a list of available (initialized) platform IDs."""
        self._discover()
        return list(self._connectors.keys())

    def get_all_connectors(self) -> Dict[str, BaseConnector]:
        """Return all registered connectors."""
        self._discover()
        return dict(self._connectors)

    def is_available(self, platform_id: str) -> bool:
        """Check if a connector is registered and available."""
        self._discover()
        return platform_id in self._connectors

    def health_check_all(self) -> Dict[str, ConnectorHealth]:
        """
        Run health checks on all registered connectors.

        Returns a dict mapping platform_id → ConnectorHealth.
        Also includes entries for known-but-unavailable connectors
        with status="disabled".
        """
        self._discover()
        results: Dict[str, ConnectorHealth] = {}

        # Known platforms (for completeness)
        all_known = ["youtube", "reddit", "tiktok", "instagram"]

        for platform_id in all_known:
            connector = self._connectors.get(platform_id)
            if connector is None:
                results[platform_id] = ConnectorHealth(
                    platform=platform_id,
                    status="disabled",
                    error_message="Connector not configured or credentials missing.",
                )
                continue

            try:
                start = time.time()
                health = connector.health_check()
                health.latency_ms = round((time.time() - start) * 1000, 1)
                results[platform_id] = health
            except Exception as exc:
                results[platform_id] = ConnectorHealth(
                    platform=platform_id,
                    status="unavailable",
                    error_message=str(exc),
                )

        return results

    def reset(self) -> None:
        """
        Reset the registry (for testing or re-initialization).

        Clears all connectors and marks as undiscovered.
        """
        self._connectors.clear()
        self._discovered = False
        logger.info("Connector registry reset.")

    @classmethod
    def reset_singleton(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None
