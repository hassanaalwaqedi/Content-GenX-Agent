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

    # ---- Niche Keywords ----------------------------------------------------
    niche_keywords: List[str] = Field(
        default=[
            "AI for business",
            "AI productivity",
            "prompt engineering",
        ],
        description="Search queries representing target niches",
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
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "https://genxagent-f420f.web.app",
            "https://genxagent-f420f.firebaseapp.com",
            "https://content-genx-agent.onrender.com",
        ],
        description="Allowed CORS origins. Set to ['*'] only for development.",
    )
    pipeline_api_key: str = Field(
        default="",
        description="Shared secret for /pipeline/run. Leave empty to disable auth.",
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
