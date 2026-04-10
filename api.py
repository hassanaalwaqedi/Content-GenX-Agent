"""
FastAPI REST API for Content Intelligence Platform.

Endpoints:
  GET  /health             -- system health & stats
  GET  /videos/top         -- top-scoring videos per niche
  GET  /videos/trending    -- fastest-growing videos
  GET  /creators/top       -- top creators by aggregate score
  GET  /stats              -- aggregate database statistics
  POST /pipeline/run       -- trigger a pipeline run manually
  GET  /pipeline/history   -- recent pipeline run audit log
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from config import get_settings
from database import init_db, get_video_count, get_distinct_niches, get_pipeline_history, is_pipeline_running
from queries import (
    get_fastest_growing_videos,
    get_top_creators,
    get_top_videos_per_niche,
    get_video_by_id,
    get_video_stats,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # ---- Startup ----
    init_db()
    logger.info("API startup complete -- database initialized.")
    yield
    # ---- Shutdown ----
    logger.info("API shutting down gracefully.")


# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Content Intelligence Platform",
    description=(
        "REST API for discovering high-performing AI-related YouTube content. "
        "Provides insights on top videos, trending content, and leading creators."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS -- restricted to configured origins (secure by default)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Pipeline authentication (optional shared-secret API key)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_pipeline_key(
    api_key: str = Security(_api_key_header),
) -> None:
    """Verify the pipeline API key if one is configured."""
    required_key = _settings.pipeline_api_key
    if not required_key:
        return  # Auth disabled -- no key configured
    if api_key != required_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing X-API-Key header.",
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    timestamp: str
    total_videos: int
    niches: List[str]
    database: str = Field(..., example="connected")


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


class VideoDetailResponse(BaseModel):
    """Full video detail including description and audit timestamps."""
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
    description: Optional[str] = None
    target_audience: Optional[str] = None
    strategic_advice: Optional[str] = None
    content_gap: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreatorResponse(BaseModel):
    channel: str
    video_count: int
    total_views: int
    avg_engagement_rate: float
    avg_score: float
    total_score: float


class PipelineRunResponse(BaseModel):
    status: str
    message: str
    triggered_at: str


class PipelineRunRecord(BaseModel):
    id: int
    started_at: str
    finished_at: Optional[str] = None
    status: str
    videos_ingested: int = 0
    videos_processed: int = 0
    videos_enriched: int = 0
    videos_stored: int = 0
    elapsed_seconds: Optional[float] = None
    error_message: Optional[str] = None
    triggered_by: str = "manual"


class PipelineHistoryResponse(BaseModel):
    count: int
    runs: List[PipelineRunRecord]


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


class TopVideosResponse(BaseModel):
    niche: str
    days: int
    count: int
    videos: List[VideoResponse]


class TrendingVideosResponse(BaseModel):
    days: int
    count: int
    videos: List[VideoResponse]


class TopCreatorsResponse(BaseModel):
    count: int
    creators: List[CreatorResponse]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    tags=["System"],
)
async def health() -> HealthResponse:
    """Return current system status, video count, and available niches."""
    try:
        total = get_video_count()
        niches = get_distinct_niches()
        db_status = "connected"
    except Exception as exc:
        logger.error("Health check database error: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable")

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_videos=total,
        niches=niches,
        database=db_status,
    )


@app.get(
    "/videos/top",
    response_model=TopVideosResponse,
    summary="Top videos per niche",
    tags=["Videos"],
)
async def top_videos(
    niche: str = Query(
        ..., description="Niche to filter by (e.g. 'AI for business')"
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Look-back window in days",
    ),
    limit: int = Query(default=20, ge=1, le=100),
) -> TopVideosResponse:
    """Return the highest-scoring videos for a specific niche."""
    try:
        rows = get_top_videos_per_niche(niche, days=days, limit=limit)
    except Exception as exc:
        logger.error("Error fetching top videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    videos = [VideoResponse(**r) for r in rows]
    return TopVideosResponse(
        niche=niche, days=days, count=len(videos), videos=videos
    )


@app.get(
    "/videos/trending",
    response_model=TrendingVideosResponse,
    summary="Fastest-growing / trending videos",
    tags=["Videos"],
)
async def trending_videos(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
) -> TrendingVideosResponse:
    """Return videos that are gaining traction rapidly."""
    try:
        rows = get_fastest_growing_videos(days=days, limit=limit)
    except Exception as exc:
        logger.error("Error fetching trending videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    videos = [VideoResponse(**r) for r in rows]
    return TrendingVideosResponse(days=days, count=len(videos), videos=videos)


@app.get(
    "/videos/{video_id}",
    response_model=VideoDetailResponse,
    summary="Get video details",
    tags=["Videos"],
)
async def video_detail(video_id: str) -> VideoDetailResponse:
    """Return full details for a single video by its YouTube ID."""
    try:
        row = get_video_by_id(video_id)
    except Exception as exc:
        logger.error("Error fetching video %s: %s", video_id, exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    if not row:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")

    return VideoDetailResponse(**row)


@app.get(
    "/creators/top",
    response_model=TopCreatorsResponse,
    summary="Top content creators",
    tags=["Creators"],
)
async def top_creators(
    limit: int = Query(default=20, ge=1, le=100),
    min_videos: int = Query(
        default=2,
        ge=1,
        description="Minimum number of videos to qualify",
    ),
) -> TopCreatorsResponse:
    """Return creators ranked by aggregate score and engagement."""
    try:
        rows = get_top_creators(limit=limit, min_videos=min_videos)
    except Exception as exc:
        logger.error("Error fetching top creators: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    creators = [CreatorResponse(**r) for r in rows]
    return TopCreatorsResponse(count=len(creators), creators=creators)


@app.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    summary="Trigger pipeline manually",
    tags=["Pipeline"],
    dependencies=[Security(_verify_pipeline_key)],
)
async def run_pipeline_endpoint() -> PipelineRunResponse:
    """
    Trigger a full pipeline run (ingest -> process -> store).

    Runs in a background thread so the API response returns immediately.
    Only one pipeline run can be active at a time (enforced at DB level).
    """
    # Check database-level lock instead of in-memory flag
    if is_pipeline_running():
        raise HTTPException(
            status_code=409,
            detail="A pipeline run is already in progress.",
        )

    def _background_run() -> None:
        try:
            from main import run_pipeline  # deferred import

            run_pipeline(triggered_by="api")
            logger.info("Background pipeline run completed.")
        except Exception as exc:
            logger.error("Background pipeline run failed: %s", exc, exc_info=True)

    thread = threading.Thread(target=_background_run, daemon=True)
    thread.start()

    return PipelineRunResponse(
        status="accepted",
        message="Pipeline run triggered in background.",
        triggered_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/pipeline/history",
    response_model=PipelineHistoryResponse,
    summary="Pipeline run audit log",
    tags=["Pipeline"],
)
async def pipeline_history(
    limit: int = Query(default=10, ge=1, le=50),
) -> PipelineHistoryResponse:
    """Return the most recent pipeline execution records for observability."""
    try:
        rows = get_pipeline_history(limit=limit)
    except Exception as exc:
        logger.error("Error fetching pipeline history: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    runs = [PipelineRunRecord(**r) for r in rows]
    return PipelineHistoryResponse(count=len(runs), runs=runs)


@app.get(
    "/stats",
    response_model=StatsResponse,
    summary="Database aggregate statistics",
    tags=["System"],
)
async def stats() -> StatsResponse:
    """Return aggregate statistics for the entire video database."""
    try:
        data = get_video_stats()
    except Exception as exc:
        logger.error("Error fetching stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    return StatsResponse(**data)


# ---------------------------------------------------------------------------
# Run with Uvicorn (for development)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
    )
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
