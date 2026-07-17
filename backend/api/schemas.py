"""Shared API response models used by focused route modules."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "healthy"})
    timestamp: str
    total_videos: int
    niches: List[str]
    database: str = Field(..., json_schema_extra={"example": "connected"})


class StatsResponse(BaseModel):
    total_videos: int
    total_niches: int
    total_channels: int
    avg_score: Optional[float] = None
    avg_engagement_rate: Optional[float] = None
    max_score: Optional[float] = None
    earliest_video: Optional[str] = None
    latest_video: Optional[str] = None
    niche_stats: Optional[Dict[str, Any]] = None
    platform_stats: Optional[Dict[str, Any]] = None


class TranscriptStatsResponse(BaseModel):
    total_youtube: int = 0
    with_transcript: int = 0
    without_transcript: int = 0
    coverage_pct: float = 0.0
    niche_breakdown: Optional[List[Dict[str, Any]]] = None


class VideoResponse(BaseModel):
    video_id: str
    platform: str = "youtube"
    niche: str
    title: str
    views: int
    likes: int
    comments: int
    engagement_rate: float
    score: float
    published_at: Optional[str] = None
    channel: Optional[str] = None
    thumbnail_url: Optional[str] = None
    target_audience: Optional[str] = None
    strategic_advice: Optional[str] = None
    content_gap: Optional[str] = None
    source_region: Optional[str] = None
    content_type: Optional[str] = None


class VideoDetailResponse(VideoResponse):
    """Full video detail including description and audit timestamps."""

    description: Optional[str] = None
    transcript: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TopVideosResponse(BaseModel):
    niche: str
    days: int
    count: int
    videos: List[VideoResponse]


class TrendingVideosResponse(BaseModel):
    days: int
    count: int
    videos: List[VideoResponse]


class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str
    transcript_30s: str
    cached: bool = False


class CreatorResponse(BaseModel):
    channel: str
    video_count: int
    total_views: int
    avg_engagement_rate: float
    avg_score: float
    total_score: float


class TopCreatorsResponse(BaseModel):
    count: int
    creators: List[CreatorResponse]
