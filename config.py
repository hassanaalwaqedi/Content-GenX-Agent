"""
Configuration module for Content Intelligence Platform.

Loads settings from environment variables with sensible defaults.
Uses pydantic-settings for type-safe configuration management.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Resolve .env path relative to this file so it works regardless of cwd
# ---------------------------------------------------------------------------
_ENV_FILE = Path(__file__).resolve().parent / ".env"


class ScoringWeights(BaseSettings):
    """Weights used in the composite video scoring formula."""

    model_config = SettingsConfigDict(env_prefix="SCORE_WEIGHT_")

    views: float = Field(default=0.4, description="Weight for log(views)")
    engagement: float = Field(default=0.35, description="Weight for engagement_rate")
    recency: float = Field(default=0.25, description="Weight for recency factor")


class FilterThresholds(BaseSettings):
    """Minimum thresholds for video filtering."""

    model_config = SettingsConfigDict(env_prefix="FILTER_")

    min_views: int = Field(default=1000, description="Minimum view count to keep a video")
    min_engagement_rate: float = Field(
        default=0.02, description="Minimum engagement rate to keep a video"
    )


class Settings(BaseSettings):
    """
    Application-wide settings.

    Values are loaded from environment variables (case-insensitive) and
    optionally from a `.env` file located next to this module.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- API Keys ----------------------------------------------------------
    youtube_api_key: str = Field(
        default="",
        description="Google / YouTube Data API v3 key",
    )
    groq_api_key: str = Field(
        default="",
        description="Groq API key for AI enrichment (LLM inference)",
    )

    # ---- Database ----------------------------------------------------------
    database_url: str = Field(
        default="sqlite:///content_intelligence.db",
        description="Database connection string (SQLite default, PostgreSQL-ready)",
    )
    sqlite_db_path: str = Field(
        default="content_intelligence.db",
        description="Path to the SQLite database file",
    )

    # ---- YouTube Ingestion -------------------------------------------------
    youtube_max_results_per_query: int = Field(
        default=50,
        ge=1,
        le=50,
        description="Max results per YouTube API page (1-50)",
    )
    youtube_max_pages: int = Field(
        default=3,
        ge=1,
        description="Max pages to paginate through per query",
    )
    youtube_retry_attempts: int = Field(default=3, ge=1)
    youtube_retry_delay_seconds: float = Field(default=2.0, ge=0.5)

    # ---- Reddit Ingestion --------------------------------------------------
    reddit_client_id: str = Field(
        default="",
        description="Reddit app client ID (from reddit.com/prefs/apps)",
    )
    reddit_client_secret: str = Field(
        default="",
        description="Reddit app client secret",
    )
    reddit_user_agent: str = Field(
        default="GenXContentIntel/1.0",
        description="User-Agent string for Reddit API requests",
    )
    reddit_max_posts_per_query: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Max Reddit posts to fetch per niche keyword",
    )

    # ---- TikTok Ingestion --------------------------------------------------
    tiktok_enabled: bool = Field(
        default=False,
        description="Enable TikTok connector (uses RapidAPI tiktok-scraper7)",
    )
    tiktok_request_delay: float = Field(
        default=2.0, ge=0.5,
        description="Delay between TikTok API requests (seconds)",
    )
    tiktok_max_results: int = Field(
        default=30, ge=1, le=100,
        description="Max TikTok videos to fetch per query",
    )
    tiktok_request_timeout: int = Field(
        default=30, ge=5,
        description="TikTok request timeout in seconds",
    )
    tiktok_daily_scan_limit: int = Field(
        default=3, ge=0,
        description="Max TikTok scans per day (0 = unlimited). Prevents rate limiting.",
    )

    # ---- Instagram Ingestion -----------------------------------------------
    instagram_enabled: bool = Field(
        default=False,
        description="Enable Instagram connector (requires RapidAPI key)",
    )
    rapidapi_key: str = Field(
        default="",
        description="RapidAPI key for Instagram (instagram120) API",
    )
    instagram_request_delay: float = Field(
        default=3.0, ge=1.0,
        description="Delay between Instagram requests (seconds)",
    )
    instagram_max_results: int = Field(
        default=30, ge=1, le=100,
        description="Max Instagram posts to fetch per creator",
    )
    instagram_daily_scan_limit: int = Field(
        default=5, ge=0,
        description="Max Instagram scans per day (0 = unlimited). Prevents rate limiting.",
    )

    # ---- Velocity Scoring Weights ------------------------------------------
    velocity_weight_views: float = Field(default=0.30)
    velocity_weight_engagement: float = Field(default=0.35)
    velocity_weight_recency: float = Field(default=0.20)
    velocity_weight_shares: float = Field(default=0.15)

    # ---- Relevance Scoring -------------------------------------------------
    relevance_threshold: int = Field(
        default=55, ge=0, le=100,
        description="Minimum relevance score (0-100) to keep content. Content below this is rejected.",
    )
    relevance_skip_youtube: bool = Field(
        default=True,
        description="Skip relevance scoring for YouTube (already relevant via API search).",
    )
    relevance_skip_trending: bool = Field(
        default=True,
        description="Skip relevance scoring for trending-only pipeline runs (no keywords).",
    )

    # ---- Query Intelligence ------------------------------------------------
    query_max_synonyms: int = Field(
        default=5, ge=1, le=20,
        description="Maximum synonym expansions per keyword.",
    )
    query_max_hashtag_variants: int = Field(
        default=8, ge=1, le=20,
        description="Maximum hashtag variants to try per keyword.",
    )

    # ---- Reddit Search Keywords (NOT used for YouTube) ----------------------
    niche_keywords: List[str] = Field(
        default=[
            "AI for business",
            "AI productivity",
            "prompt engineering",
        ],
        description="Search queries for Reddit ingestion only. YouTube uses trending API (mostPopular) with NO query bias.",
    )

    # ---- Scoring & Filtering -----------------------------------------------
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    filter_thresholds: FilterThresholds = Field(default_factory=FilterThresholds)

    # ---- Scheduler ---------------------------------------------------------
    pipeline_schedule_time: str = Field(
        default="06:00",
        description="Daily pipeline run time in HH:MM (24h)",
    )

    # ---- Logging -----------------------------------------------------------
    log_level: str = Field(default="INFO")
    log_format: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    # ---- API Server --------------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # ---- Security -----------------------------------------------------------
    cors_allowed_origins: List[str] = Field(
        default=["*"],
        description="Allowed CORS origins. Set to ['*'] to allow all origins.",
    )
    pipeline_api_key: str = Field(
        default="",
        description="Shared secret for /pipeline/run. Leave empty to disable auth.",
    )

    # ---- Authentication (single-operator) -----------------------------------
    genx_admin_username: str = Field(
        default="",
        description="Admin username for platform login",
    )
    genx_admin_password: str = Field(
        default="",
        description="Admin password for platform login",
    )
    genx_auth_secret: str = Field(
        default="",
        description="JWT signing secret (HMAC-SHA256). Auto-generated if empty.",
    )

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
