"""
Unified content models for the Connector Architecture.

Defines platform-agnostic data models that ALL connectors must
produce. The analytics, enrichment, and storage layers depend
ONLY on these models — never on raw platform payloads.

Models:
    - NormalizedContent: The canonical content record
    - ConnectorHealth: Health check result for a connector
    - ConnectorMetrics: Operational metrics per connector
    - HookAnalysis: Result of hook extraction and categorization
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalized Content Model (THE canonical schema)
# ---------------------------------------------------------------------------
class NormalizedContent(BaseModel):
    """
    Platform-agnostic content record.

    Every connector MUST produce instances of this model.
    The analytics layer, AI enrichment, and database ONLY
    consume this schema — never raw platform payloads.

    The ``raw_payload`` field stores the original platform
    response for debugging and future re-processing.
    """

    # ---- Identity ----------------------------------------------------------
    id: str = Field(
        ...,
        description="Platform-prefixed unique ID (e.g. 'tiktok_123', 'ig_abc')",
    )
    platform: str = Field(
        ...,
        description="Platform identifier: youtube, reddit, tiktok, instagram",
    )
    content_type: str = Field(
        default="video",
        description="Content format: video, reel, post, short",
    )

    # ---- Author ------------------------------------------------------------
    author_name: str = Field(default="", description="Creator/channel name")
    author_followers: int = Field(default=0, ge=0, description="Creator follower count")

    # ---- Content -----------------------------------------------------------
    title: str = Field(default="", description="Content title or first line")
    description: str = Field(default="", description="Full description/caption")
    transcript: str = Field(default="", description="Spoken content transcript")
    hashtags: List[str] = Field(
        default_factory=list,
        description="Hashtags extracted from content",
    )
    audio_name: str = Field(
        default="",
        description="Audio track name (TikTok/Reels)",
    )
    thumbnail_url: str = Field(default="", description="Thumbnail/cover image URL")
    published_at: str = Field(default="", description="ISO 8601 publish timestamp")
    language: str = Field(default="", description="Detected content language")

    # ---- Engagement Metrics ------------------------------------------------
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)

    # ---- Computed Scores ---------------------------------------------------
    engagement_rate: float = Field(default=0.0, ge=0.0)
    virality_score: float = Field(default=0.0, ge=0.0)

    # ---- Hook Intelligence -------------------------------------------------
    hook_text: str = Field(default="", description="Opening hook / first sentence")
    hook_category: str = Field(
        default="",
        description="Hook type: curiosity, authority, fear, story, etc.",
    )

    # ---- Trend Velocity ----------------------------------------------------
    trend_velocity: float = Field(default=0.0, ge=0.0)

    # ---- Relevance Intelligence --------------------------------------------
    relevance_score: int = Field(
        default=0, ge=0, le=100,
        description="Query relevance score (0-100). 0 = not scored.",
    )
    matched_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords that matched this content",
    )
    matched_hashtags: List[str] = Field(
        default_factory=list,
        description="Hashtags that matched the query",
    )
    match_reason: str = Field(
        default="",
        description="Human-readable explanation of why this content was selected",
    )

    # ---- Source ------------------------------------------------------------
    source_url: str = Field(default="", description="Direct link to content")
    raw_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Original platform JSON for debugging",
    )

    # ---- Backward-Compatibility Bridge -------------------------------------

    def to_raw_video(self) -> Dict[str, Any]:
        """
        Convert to the legacy RawVideo-compatible dict used by the
        existing processing pipeline.

        This bridge allows the new connector architecture to feed
        into the existing process_videos() → enrich_videos() → insert_videos()
        pipeline without modifications to those layers.
        """
        return {
            "video_id": self.id,
            "platform": self.platform,
            "title": self.title,
            "channel": self.author_name,
            "description": self.description,
            "published_at": self.published_at,
            "thumbnail_url": self.thumbnail_url,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "niche": "",  # Will be set by categorization
            "source_region": "",
            "content_type": self.content_type,
            # New fields carried forward
            "hashtags": json.dumps(self.hashtags) if self.hashtags else "",
            "audio_name": self.audio_name,
            "hook_text": self.hook_text,
            "hook_category": self.hook_category,
            "trend_velocity": self.trend_velocity,
            "virality_score": self.virality_score,
            "shares": self.shares,
            "saves": self.saves,
            "author_followers": self.author_followers,
            "source_url": self.source_url,
            "raw_payload": json.dumps(self.raw_payload) if self.raw_payload else "",
            # Relevance intelligence
            "relevance_score": self.relevance_score,
            "matched_keywords": ",".join(self.matched_keywords) if self.matched_keywords else "",
            "matched_hashtags": ",".join(self.matched_hashtags) if self.matched_hashtags else "",
            "match_reason": self.match_reason,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full serialization for storage or transport."""
        return self.model_dump()


# ---------------------------------------------------------------------------
# Connector Health
# ---------------------------------------------------------------------------
@dataclass
class ConnectorHealth:
    """Health check result for a single connector."""

    platform: str
    status: str = "unknown"  # "healthy", "degraded", "unavailable", "disabled"
    latency_ms: float = 0.0
    last_check: str = ""
    error_message: str = ""
    credentials_configured: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Connector Metrics
# ---------------------------------------------------------------------------
@dataclass
class ConnectorMetrics:
    """
    Operational metrics for a connector instance.

    Tracks request counts, failures, retries, and rate limits
    during a single pipeline run for observability.
    """

    platform: str
    requests_made: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    retries: int = 0
    rate_limits_hit: int = 0
    items_extracted: int = 0
    execution_duration_seconds: float = 0.0

    def record_request(self, success: bool = True) -> None:
        """Record a request outcome."""
        self.requests_made += 1
        if success:
            self.requests_succeeded += 1
        else:
            self.requests_failed += 1

    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.retries += 1

    def record_rate_limit(self) -> None:
        """Record a rate limit hit."""
        self.rate_limits_hit += 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



