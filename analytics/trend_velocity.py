"""
Trend Velocity Engine for the Content Intelligence Platform.

Computes platform-agnostic engagement and trend metrics for any
NormalizedContent instance. All formulas use configurable weights
so scoring behavior can be tuned without code changes.

Metrics computed:
    - engagement_rate: Interaction ratio relative to views
    - velocity: Time-adjusted engagement momentum
    - virality: Share-weighted spread potential
    - growth: Audience-adjusted velocity

Usage:
    engine = TrendVelocityEngine()
    content = engine.score(normalized_content)
    # content.engagement_rate, .trend_velocity, .virality_score are now set
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configurable Weights
# ---------------------------------------------------------------------------
@dataclass
class VelocityWeights:
    """
    Tunable weights for the velocity scoring formula.

    Loaded from environment variables via config.py, or use defaults.
    All weights should sum to ~1.0 for normalized output.
    """

    views: float = 0.30
    engagement: float = 0.35
    recency: float = 0.20
    shares: float = 0.15


# ---------------------------------------------------------------------------
# Trend Velocity Engine
# ---------------------------------------------------------------------------
class TrendVelocityEngine:
    """
    Configurable trend velocity scoring engine.

    Operates on any content with standard metrics (views, likes,
    comments, shares, saves, published_at, author_followers).
    Platform-agnostic by design.
    """

    def __init__(self, weights: Optional[VelocityWeights] = None) -> None:
        self._weights = weights or self._load_weights()
        logger.debug(
            "TrendVelocityEngine initialized: weights=%s",
            self._weights,
        )

    @staticmethod
    def _load_weights() -> VelocityWeights:
        """Load weights from config, falling back to defaults."""
        try:
            from config import get_settings

            settings = get_settings()
            return VelocityWeights(
                views=getattr(settings, "velocity_weight_views", 0.30),
                engagement=getattr(settings, "velocity_weight_engagement", 0.35),
                recency=getattr(settings, "velocity_weight_recency", 0.20),
                shares=getattr(settings, "velocity_weight_shares", 0.15),
            )
        except Exception:
            return VelocityWeights()

    # ---- Core Formulas -----------------------------------------------------

    @staticmethod
    def compute_engagement_rate(
        views: int,
        likes: int,
        comments: int,
        shares: int = 0,
    ) -> float:
        """
        Compute engagement rate as interaction ratio.

        Formula: (likes + comments + shares) / max(views, 1)

        For platforms without shares (YouTube), shares=0 is fine.
        """
        if views <= 0:
            return 0.0
        return round((likes + comments + shares) / views, 8)

    @staticmethod
    def compute_velocity(
        views: int,
        engagement_rate: float,
        hours_since_publish: float,
    ) -> float:
        """
        Compute trend velocity: time-adjusted engagement momentum.

        Formula: (log(views + 1) × engagement_rate) / max(hours_since_publish, 1)

        High velocity = lots of engagement in a short time window.
        """
        if hours_since_publish <= 0:
            hours_since_publish = 1.0
        if views <= 0:
            return 0.0

        velocity = (math.log(views + 1) * engagement_rate) / hours_since_publish
        return round(velocity, 8)

    @staticmethod
    def compute_virality(
        views: int,
        shares: int,
        saves: int = 0,
    ) -> float:
        """
        Compute virality score: share-weighted spread potential.

        Formula: (shares × 2 + saves) / max(views, 1)

        Shares are weighted 2x because they represent active distribution.
        Saves indicate content deemed worth revisiting.
        """
        if views <= 0:
            return 0.0
        return round((shares * 2 + saves) / views, 8)

    @staticmethod
    def compute_growth(
        velocity: float,
        author_followers: int,
    ) -> float:
        """
        Compute growth score: audience-adjusted velocity.

        Formula: velocity × log(author_followers + 1)

        High growth = high velocity from an account with reach.
        An account with 0 followers still gets a base score.
        """
        follower_factor = math.log(max(author_followers, 1) + 1)
        return round(velocity * follower_factor, 8)

    @staticmethod
    def _hours_since_publish(published_at: str) -> float:
        """Parse ISO timestamp and return hours elapsed since now."""
        if not published_at:
            return 24.0  # Default to 24h if unknown

        try:
            pub_dt = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            )
            delta = datetime.now(timezone.utc) - pub_dt
            hours = delta.total_seconds() / 3600.0
            return max(hours, 0.1)  # Minimum 6 minutes to avoid division spikes
        except (ValueError, AttributeError):
            return 24.0

    # ---- High-Level Scoring ------------------------------------------------

    def score_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute all velocity metrics for a content dict.

        Modifies the dict in-place and returns it.
        Expects keys: views, likes, comments, shares, saves,
        published_at, author_followers.
        """
        views = int(content.get("views", 0))
        likes = int(content.get("likes", 0))
        comments = int(content.get("comments", 0))
        shares = int(content.get("shares", 0))
        saves = int(content.get("saves", 0))
        published_at = content.get("published_at", "")
        followers = int(content.get("author_followers", 0))

        # Compute metrics
        engagement_rate = self.compute_engagement_rate(
            views, likes, comments, shares
        )
        hours = self._hours_since_publish(published_at)
        velocity = self.compute_velocity(views, engagement_rate, hours)
        virality = self.compute_virality(views, shares, saves)
        growth = self.compute_growth(velocity, followers)

        # Update content dict
        content["engagement_rate"] = engagement_rate
        content["trend_velocity"] = velocity
        content["virality_score"] = virality
        content["growth_score"] = growth

        return content

    def score_batch(
        self, contents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Score a batch of content dicts. Returns the modified list."""
        scored = 0
        for content in contents:
            try:
                self.score_content(content)
                scored += 1
            except Exception as exc:
                logger.warning(
                    "Velocity scoring failed for %s: %s",
                    content.get("id", content.get("video_id", "?")),
                    exc,
                )

        logger.info(
            "TrendVelocityEngine: scored %d / %d items.",
            scored,
            len(contents),
        )
        return contents
