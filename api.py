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

from fastapi import FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from auth import auth_router, require_auth, _COOKIE_NAME, _decode_token, _get_auth_settings

from config import get_settings
from database import (
    init_db, get_video_count, get_distinct_niches, get_pipeline_history,
    is_pipeline_running, save_pipeline_config, get_pipeline_config,
    list_pipeline_configs, delete_pipeline_config, get_last_used_config,
    get_active_dataset, set_active_dataset, get_dataset_list, get_dataset_stats,
)
from queries import (
    get_fastest_growing_videos,
    get_top_creators,
    get_creator_intelligence,
    get_rising_creators,
    get_creators_by_trend,
    get_creator_videos,
    get_top_videos_per_niche,
    get_video_by_id,
    get_video_stats,
    get_transcript_stats,
    get_transcript_by_video_id,
    get_videos_with_topics,
    update_transcript,
)
from transcripts import fetch_transcript, fetch_transcript_segments, extract_first_30s
from trends import discover_trends, discover_opportunities

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_THUMBNAIL = "https://via.placeholder.com/320x180.png?text=No+Thumbnail"


def _resolve_dataset_id(dataset_id: Optional[int]) -> Optional[int]:
    """
    Resolve the effective pipeline_run_id for data scoping.
    - dataset_id=0  → "all data" mode, return None (no scoping)
    - dataset_id>0  → use that specific run ID
    - dataset_id=None → look up the active dataset and return its run ID
    Returns None if no active dataset exists (backward compat: shows all).
    """
    if dataset_id is not None:
        if dataset_id == 0:
            return None  # Sentinel: all historical data, no scoping
        return dataset_id
    active = get_active_dataset()
    return active["id"] if active else None


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
        "REST API for discovering globally trending YouTube content. "
        "Provides insights on top videos, trending content, and leading creators "
        "across mixed categories (music, sports, news, entertainment, etc)."
    ),
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS -- allow cross-origin requests from Firebase frontend
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Auth router & middleware -----------------------------------------------
app.include_router(auth_router)

# Public paths that do NOT require authentication
_PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
_PUBLIC_PREFIXES = ("/auth/",)


def _cors_401(request: Request, detail: str) -> JSONResponse:
    """Return a 401 response with CORS headers so the browser can read it."""
    origin = request.headers.get("origin", "")
    headers = {}
    if origin:
        allowed = _settings.cors_allowed_origins
        if "*" in allowed or origin in allowed:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers=headers,
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Global authentication middleware.
    Checks for a valid session cookie on every request except public paths.
    """
    path = request.url.path

    # Allow public endpoints and OPTIONS preflight
    if (
        request.method == "OPTIONS"
        or path in _PUBLIC_PATHS
        or any(path.startswith(p) for p in _PUBLIC_PREFIXES)
    ):
        return await call_next(request)

    # Check auth: Bearer token first, cookie fallback
    token = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return _cors_401(request, "Authentication required.")

    settings = _get_auth_settings()
    payload = _decode_token(token, settings["secret"])
    if payload is None:
        return _cors_401(request, "Session expired or invalid.")

    # Attach user info to request state for downstream use
    request.state.user = payload
    return await call_next(request)


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
    source_region: Optional[str] = None
    content_type: Optional[str] = None


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
    transcript: Optional[str] = None
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
    platform_stats: Optional[Dict[str, Any]] = None


class TranscriptStatsResponse(BaseModel):
    total_youtube: int = 0
    with_transcript: int = 0
    without_transcript: int = 0
    coverage_pct: float = 0.0
    niche_breakdown: Optional[List[Dict[str, Any]]] = None


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


class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str
    transcript_30s: str
    cached: bool = False


class TrendVideoSummary(BaseModel):
    video_id: str
    title: str
    channel: Optional[str] = None
    views: int = 0
    engagement_rate: float = 0.0
    score: float = 0.0
    thumbnail_url: Optional[str] = None


class TrendClusterResponse(BaseModel):
    trend: str
    trend_score: float = 0.0
    count: int = 0
    avg_views: float = 0.0
    avg_engagement: float = 0.0
    avg_score: float = 0.0
    total_views: int = 0
    top_videos: List[TrendVideoSummary] = []


class TrendsDiscoverResponse(BaseModel):
    days: int
    total_videos_analyzed: int
    count: int
    trends: List[TrendClusterResponse]


class OpportunityResponse(BaseModel):
    trend: str
    opportunity_score: float = 0.0
    trend_score: float = 0.0
    count: int = 0
    avg_engagement: float = 0.0
    avg_score: float = 0.0
    reasons: List[str] = []
    suggested_titles: List[str] = []
    top_videos: List[TrendVideoSummary] = []


class OpportunitiesResponse(BaseModel):
    days: int
    total_videos_analyzed: int
    count: int
    opportunities: List[OpportunityResponse]


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
    summary="Top videos (optionally filter by category)",
    tags=["Videos"],
)
async def top_videos(
    niche: Optional[str] = Query(
        default=None, description="Category to filter by (e.g. 'music', 'sports'). Omit for all categories."
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Look-back window in days",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    region: Optional[str] = Query(default=None, description="Filter by source region code (e.g. US, DE)"),
    category: Optional[str] = Query(default=None, description="Filter by category/niche"),
    content_type: Optional[str] = Query(default=None, description="Filter by content type (shorts, long, all)"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to. Defaults to active dataset."),
) -> TopVideosResponse:
    """Return the highest-scoring videos, optionally filtered by category, region, content_type."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        rows = get_top_videos_per_niche(
            niche, days=days, limit=limit,
            region=region, category=category, content_type=content_type,
            pipeline_run_id=run_id,
        )
    except Exception as exc:
        logger.error("Error fetching top videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    videos = [VideoResponse(**r) for r in rows]
    for v in videos:
        if not v.thumbnail_url:
            v.thumbnail_url = DEFAULT_THUMBNAIL
    return TopVideosResponse(
        niche=niche or "all", days=days, count=len(videos), videos=videos
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
    region: Optional[str] = Query(default=None, description="Filter by source region code"),
    category: Optional[str] = Query(default=None, description="Filter by category/niche"),
    content_type: Optional[str] = Query(default=None, description="Filter by content type"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to. Defaults to active dataset."),
) -> TrendingVideosResponse:
    """Return videos that are gaining traction rapidly."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        rows = get_fastest_growing_videos(
            days=days, limit=limit,
            region=region, category=category, content_type=content_type,
            pipeline_run_id=run_id,
        )
    except Exception as exc:
        logger.error("Error fetching trending videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    videos = [VideoResponse(**r) for r in rows]
    for v in videos:
        if not v.thumbnail_url:
            v.thumbnail_url = DEFAULT_THUMBNAIL
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

    detail = VideoDetailResponse(**row)
    if not detail.thumbnail_url:
        detail.thumbnail_url = DEFAULT_THUMBNAIL
    return detail


@app.post(
    "/videos/{video_id}/transcript",
    response_model=TranscriptResponse,
    summary="Fetch video transcript on-demand",
    tags=["Videos"],
)
async def fetch_video_transcript(video_id: str) -> TranscriptResponse:
    """
    On-demand transcript fetching with DB caching.

    1. Check DB for existing transcript.
    2. If found → return cached result.
    3. If missing → fetch from YouTube, store in DB, return.
    """
    # Check if video exists
    existing = get_transcript_by_video_id(video_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")

    # If transcript already cached in DB
    if existing.strip():
        # We have a cached transcript but no segments for 30s extraction.
        # Use a simple heuristic: split on sentences, take first ~30s worth.
        # For cached transcripts, approximate 30s ≈ first 80 words.
        words = existing.split()
        transcript_30s = " ".join(words[:80]) if len(words) > 80 else existing
        return TranscriptResponse(
            video_id=video_id,
            transcript=existing,
            transcript_30s=transcript_30s,
            cached=True,
        )

    # Fetch fresh from YouTube
    try:
        segments = fetch_transcript_segments(video_id)
        if not segments:
            raise HTTPException(
                status_code=404,
                detail="No transcript available for this video. Captions may be disabled.",
            )

        full_text = " ".join(s["text"] for s in segments)
        full_text = " ".join(full_text.split())  # clean whitespace

        # Truncate for storage
        if len(full_text) > 5000:
            full_text = full_text[:5000] + "..."

        transcript_30s = extract_first_30s(segments)

        # Cache in DB
        update_transcript(video_id, full_text)

        return TranscriptResponse(
            video_id=video_id,
            transcript=full_text,
            transcript_30s=transcript_30s,
            cached=False,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching transcript for %s: %s", video_id, exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch transcript. Please try again later.",
        )


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
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
) -> TopCreatorsResponse:
    """Return creators ranked by aggregate score and engagement."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        rows = get_top_creators(limit=limit, min_videos=min_videos, pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching top creators: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    creators = [CreatorResponse(**r) for r in rows]
    return TopCreatorsResponse(count=len(creators), creators=creators)


@app.get(
    "/creators/intelligence",
    summary="Creator intelligence with advanced metrics",
    tags=["Creators"],
)
async def creator_intelligence(
    days: int = Query(default=365, ge=1, le=730),
    limit: int = Query(default=30, ge=1, le=100),
    min_videos: int = Query(default=1, ge=1),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    """Return creators with trend dominance, topics, velocity, and opportunity alignment."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        data = get_creator_intelligence(days=days, limit=limit, min_videos=min_videos, pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching creator intelligence: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")
    return {"count": len(data), "creators": data}


@app.get(
    "/creators/rising",
    summary="Rising creators with high growth velocity",
    tags=["Creators"],
)
async def rising_creators(
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    """Return creators with highest recent velocity (growth momentum)."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        data = get_rising_creators(days=days, limit=limit, pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching rising creators: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")
    return {"count": len(data), "creators": data}


@app.get(
    "/creators/by-trend",
    summary="Creators filtered by trend/topic",
    tags=["Creators"],
)
async def creators_by_trend(
    trend: str = Query(..., description="Trend or topic keyword to filter by"),
    days: int = Query(default=365, ge=1, le=730),
    limit: int = Query(default=20, ge=1, le=100),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    """Return creators whose content matches a given trend keyword."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        data = get_creators_by_trend(trend=trend, days=days, limit=limit, pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching creators by trend: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")
    return {"trend": trend, "count": len(data), "creators": data}


@app.get(
    "/creators/{channel}/videos",
    summary="Get videos for a specific creator",
    tags=["Creators"],
)
async def creator_videos(
    channel: str,
    limit: int = Query(default=20, ge=1, le=50),
):
    """Return top-scoring videos for a specific creator/channel."""
    try:
        data = get_creator_videos(channel=channel, limit=limit)
    except Exception as exc:
        logger.error("Error fetching creator videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    videos = []
    for v in data:
        if not v.get("thumbnail_url"):
            v["thumbnail_url"] = DEFAULT_THUMBNAIL
        videos.append(v)
    return {"channel": channel, "count": len(videos), "videos": videos}


# ---------------------------------------------------------------------------
# Dataset Management Endpoints
# ---------------------------------------------------------------------------
@app.get("/datasets", tags=["Datasets"], summary="List all completed pipeline runs as datasets")
async def list_datasets(
    limit: int = Query(default=20, ge=1, le=50),
):
    """Return all completed pipeline runs available as datasets for the workspace switcher."""
    try:
        datasets = get_dataset_list(limit=limit)
    except Exception as exc:
        logger.error("Error fetching dataset list: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")
    return {"count": len(datasets), "datasets": datasets}


@app.get("/datasets/active", tags=["Datasets"], summary="Get the currently active dataset")
async def active_dataset():
    """Return the active dataset with config and aggregate stats."""
    try:
        active = get_active_dataset()
    except Exception as exc:
        logger.error("Error fetching active dataset: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    if not active:
        return {"active": None, "stats": None}

    try:
        stats_data = get_dataset_stats(active["id"])
    except Exception:
        stats_data = {}

    return {
        "active": active,
        "stats": stats_data,
    }


@app.post("/datasets/{run_id}/activate", tags=["Datasets"], summary="Set a pipeline run as active dataset")
async def activate_dataset(run_id: int):
    """Activate a specific pipeline run as the current workspace dataset."""
    try:
        set_active_dataset(run_id)
        active = get_active_dataset()
        stats_data = get_dataset_stats(run_id) if active else {}
    except Exception as exc:
        logger.error("Error activating dataset: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to activate dataset")

    return {
        "activated": True,
        "active": active,
        "stats": stats_data,
    }


@app.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    summary="Trigger pipeline manually",
    tags=["Pipeline"],
    dependencies=[Security(_verify_pipeline_key)],
)
async def run_pipeline_endpoint(
    config_id: Optional[int] = Query(default=None, description="Pipeline config ID to use"),
) -> PipelineRunResponse:
    """
    Trigger a full pipeline run (ingest -> process -> store).

    Runs in a background thread so the API response returns immediately.
    Only one pipeline run can be active at a time (enforced at DB level).
    Optionally accepts a config_id for user-defined filters.
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

            run_pipeline(triggered_by="api", config_id=config_id)
            logger.info("Background pipeline run completed.")
        except Exception as exc:
            logger.error("Background pipeline run failed: %s", exc, exc_info=True)

    thread = threading.Thread(target=_background_run, daemon=True)
    thread.start()

    return PipelineRunResponse(
        status="accepted",
        message=f"Pipeline triggered{f' with config #{config_id}' if config_id else ' (default config)'}.",
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
    "/connectors/health",
    summary="Health status of all platform connectors",
    tags=["System"],
)
async def connectors_health():
    """Return health status of all registered platform connectors."""
    try:
        from connectors.registry import ConnectorRegistry
        registry = ConnectorRegistry()
        health = registry.health_check_all()
        return {
            "connectors": {k: v.to_dict() for k, v in health.items()},
            "available": registry.get_available(),
        }
    except Exception as exc:
        logger.error("Error checking connector health: %s", exc)
        return {
            "connectors": {},
            "available": [],
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Pipeline Config CRUD (Parts 2, 7, 8)
# ---------------------------------------------------------------------------
VALID_REGIONS = {"US", "GB", "CA", "DE", "FR", "AU", "AE", "JP", "KR", "BR", "MX", "IN", "SA", "EG", "TR"}
VALID_PLATFORMS = {"youtube", "reddit", "tiktok", "instagram"}
VALID_CONTENT_TYPES = {"all", "shorts", "long"}


class PipelineConfigRequest(BaseModel):
    name: str = Field(default="Custom", max_length=100)
    regions: List[str] = Field(default=["US", "GB", "CA", "DE", "FR", "AU", "AE"])
    platforms: List[str] = Field(default=["youtube"])
    categories: List[str] = Field(default=[])
    keywords: List[str] = Field(default=[])
    content_type: str = Field(default="all")
    is_preset: bool = False


class PipelineConfigResponse(BaseModel):
    id: int
    name: str
    regions: List[str]
    platforms: List[str]
    categories: List[str]
    keywords: List[str]
    content_type: str
    is_preset: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@app.post("/pipeline/config", tags=["Pipeline Config"], summary="Create or update a pipeline config")
async def create_pipeline_config(req: PipelineConfigRequest):
    """Save a pipeline configuration with validation."""
    import re as _re

    # Validation (Part 8)
    if not req.regions:
        raise HTTPException(400, "At least one region is required.")
    if len(req.regions) > 5:
        raise HTTPException(400, "Maximum 5 regions allowed.")
    invalid_regions = set(req.regions) - VALID_REGIONS
    if invalid_regions:
        raise HTTPException(400, f"Invalid regions: {', '.join(invalid_regions)}")
    invalid_platforms = set(req.platforms) - VALID_PLATFORMS
    if invalid_platforms:
        raise HTTPException(400, f"Invalid platforms: {', '.join(invalid_platforms)}")
    if req.content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(400, f"content_type must be one of: {', '.join(VALID_CONTENT_TYPES)}")

    # Sanitize keywords: strip, lowercase, remove special chars, max 10
    sanitized_kw = []
    for kw in req.keywords[:10]:
        clean = _re.sub(r'[^\w\s\-]', '', kw.strip())
        if clean and len(clean) <= 50:
            sanitized_kw.append(clean)

    config_data = {
        "name": req.name.strip()[:100],
        "regions": req.regions,
        "platforms": req.platforms,
        "categories": [c.lower().strip() for c in req.categories[:15]],
        "keywords": sanitized_kw,
        "content_type": req.content_type,
        "is_preset": req.is_preset,
    }

    config_id = save_pipeline_config(config_data)
    saved = get_pipeline_config(config_id)
    return {"id": config_id, "config": saved}


@app.get("/pipeline/configs", tags=["Pipeline Config"], summary="List all pipeline configs")
async def list_configs(presets_only: bool = Query(default=False)):
    configs = list_pipeline_configs(presets_only=presets_only)
    return {"count": len(configs), "configs": configs}


@app.get("/pipeline/config/last", tags=["Pipeline Config"], summary="Get last used config")
async def last_used_config():
    config = get_last_used_config()
    return {"config": config}


@app.get("/pipeline/config/{config_id}", tags=["Pipeline Config"], summary="Get a pipeline config")
async def get_config(config_id: int):
    config = get_pipeline_config(config_id)
    if not config:
        raise HTTPException(404, f"Config #{config_id} not found.")
    return {"config": config}


@app.delete("/pipeline/config/{config_id}", tags=["Pipeline Config"], summary="Delete a pipeline config")
async def delete_config(config_id: int):
    deleted = delete_pipeline_config(config_id)
    if not deleted:
        raise HTTPException(404, f"Config #{config_id} not found.")
    return {"deleted": True, "id": config_id}


@app.get(
    "/stats",
    response_model=StatsResponse,
    summary="Database aggregate statistics",
    tags=["System"],
)
async def stats(
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope stats to. Defaults to active dataset."),
) -> StatsResponse:
    """Return aggregate statistics, scoped to active dataset by default."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        data = get_video_stats(pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    return StatsResponse(**data)


@app.get(
    "/stats/transcripts",
    response_model=TranscriptStatsResponse,
    summary="Transcript extraction coverage",
    tags=["System"],
)
async def transcript_stats() -> TranscriptStatsResponse:
    """Return statistics on transcript extraction coverage."""
    try:
        data = get_transcript_stats()
    except Exception as exc:
        logger.error("Error fetching transcript stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error")

    return TranscriptStatsResponse(**data)


# ---------------------------------------------------------------------------
# Trend Discovery & Opportunities
# ---------------------------------------------------------------------------
def _video_to_summary(v: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "video_id": v.get("video_id", ""),
        "title": v.get("title", ""),
        "channel": v.get("channel"),
        "views": v.get("views", 0),
        "engagement_rate": v.get("engagement_rate", 0.0),
        "score": v.get("score", 0.0),
        "thumbnail_url": v.get("thumbnail_url") or DEFAULT_THUMBNAIL,
    }


@app.get("/trends/discover", response_model=TrendsDiscoverResponse, tags=["Trends"])
async def trends_discover(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(20, ge=1, le=50, description="Max trends to return"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    """Discover trending topics from video data."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        videos = get_videos_with_topics(days=days, limit=500, pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching videos for trends: %s", exc)
        raise HTTPException(status_code=500, detail="Database query error")

    trends = discover_trends(videos, min_count=2, limit=limit)

    trend_responses = []
    for t in trends:
        top_vids = sorted(t["videos"], key=lambda v: v.get("score", 0), reverse=True)[:5]
        trend_responses.append(TrendClusterResponse(
            trend=t["trend"],
            trend_score=t.get("trend_score", 0),
            count=t["count"],
            avg_views=t.get("avg_views", 0),
            avg_engagement=t.get("avg_engagement", 0),
            avg_score=t.get("avg_score", 0),
            total_views=t.get("total_views", 0),
            top_videos=[TrendVideoSummary(**_video_to_summary(v)) for v in top_vids],
        ))

    return TrendsDiscoverResponse(
        days=days,
        total_videos_analyzed=len(videos),
        count=len(trend_responses),
        trends=trend_responses,
    )


@app.get("/opportunities", response_model=OpportunitiesResponse, tags=["Trends"])
async def opportunities(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(15, ge=1, le=50, description="Max opportunities to return"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    """Identify content opportunities with low competition and high potential."""
    run_id = _resolve_dataset_id(dataset_id)
    try:
        videos = get_videos_with_topics(days=days, limit=500, pipeline_run_id=run_id)
    except Exception as exc:
        logger.error("Error fetching videos for opportunities: %s", exc)
        raise HTTPException(status_code=500, detail="Database query error")

    opps = discover_opportunities(videos, min_count=1, limit=limit)

    opp_responses = []
    for o in opps:
        top_vids = sorted(o["videos"], key=lambda v: v.get("score", 0), reverse=True)[:5]
        opp_responses.append(OpportunityResponse(
            trend=o["trend"],
            opportunity_score=o.get("opportunity_score", 0),
            trend_score=o.get("trend_score", 0),
            count=o["count"],
            avg_engagement=o.get("avg_engagement", 0),
            avg_score=o.get("avg_score", 0),
            reasons=o.get("reasons", []),
            suggested_titles=o.get("suggested_titles", []),
            top_videos=[TrendVideoSummary(**_video_to_summary(v)) for v in top_vids],
        ))

    return OpportunitiesResponse(
        days=days,
        total_videos_analyzed=len(videos),
        count=len(opp_responses),
        opportunities=opp_responses,
    )


# ---------------------------------------------------------------------------
# AI Content Generator
# ---------------------------------------------------------------------------
_content_cache: Dict[str, Any] = {}


class ContentGenerateRequest(BaseModel):
    video_id: str
    platform: str = "youtube"
    tone: str = "professional"


@app.post(
    "/ai/generate-content",
    summary="Generate viral content from a trending video",
    tags=["AI"],
)
async def generate_content(req: ContentGenerateRequest):
    """
    Generate content ideas, titles, hooks, scripts, hashtags & strategy
    from a trending video using Groq LLM.
    """
    # Check cache
    cache_key = f"{req.video_id}_{req.platform}_{req.tone}"
    if cache_key in _content_cache:
        return {**_content_cache[cache_key], "cached": True}

    # Fetch video from DB
    video = get_video_by_id(req.video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video '{req.video_id}' not found.")

    title = video.get("title", "")
    transcript = video.get("transcript", "") or ""
    description = video.get("description", "") or ""
    engagement = video.get("engagement_rate", 0)
    score = video.get("score", 0)
    channel = video.get("channel", "")
    target_audience = video.get("target_audience", "")
    strategic_advice = video.get("strategic_advice", "")
    content_gap = video.get("content_gap", "")

    # Fallback: use description if no transcript
    content_source = transcript[:2000] if transcript.strip() else description[:1000]
    source_label = "Transcript" if transcript.strip() else "Description"

    # Build existing insights context
    insights_ctx = ""
    if target_audience and target_audience != "Analysis pending":
        insights_ctx += f"Target Audience: {target_audience}\n"
    if strategic_advice and strategic_advice != "Analysis pending":
        insights_ctx += f"Strategic Advice: {strategic_advice}\n"
    if content_gap and content_gap != "Analysis pending":
        insights_ctx += f"Content Gap: {content_gap}\n"

    prompt = f"""You are a viral content strategist who helps creators dominate social media.

Based on this trending video:

Title: {title}
Channel: {channel}
{source_label}: {content_source}
Engagement Rate: {(engagement * 100):.1f}%
Performance Score: {score:.2f}
{insights_ctx}

Generate the following for {req.platform.upper()} platform with a {req.tone} tone:

1. A better viral content idea (1-2 sentences)
2. 3 high-CTR titles (curiosity, emotion, urgency)
3. 3 hooks (first 3 seconds — short, emotional, curiosity-driven)
4. A short-form script (30-60 seconds, ready to record)
5. Target audience (specific demographic)
6. Content strategy (how to maximize reach)
7. 5-10 relevant hashtags

Respond ONLY with valid JSON in this exact format:
{{
  "idea": "...",
  "titles": ["title1", "title2", "title3"],
  "hooks": ["hook1", "hook2", "hook3"],
  "script": "...",
  "target_audience": "...",
  "strategy": "...",
  "hashtags": ["#tag1", "#tag2", "#tag3"]
}}

Make it practical, viral, and optimized for {req.platform}. No markdown, no explanation."""

    # Call Groq LLM
    settings = get_settings()
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="AI service not configured (no API key).")

    from ai_enrichment import GroqClient
    import json as _json

    client = GroqClient(settings.groq_api_key)

    for attempt in range(3):
        try:
            raw = client.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.7,
            )
            # Clean markdown fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
            import re as _re
            cleaned = _re.sub(r'(?<!\\)\n', ' ', cleaned)

            result = _json.loads(cleaned)

            # Validate structure
            response = {
                "video_id": req.video_id,
                "video_title": title,
                "platform": req.platform,
                "tone": req.tone,
                "idea": result.get("idea", ""),
                "titles": result.get("titles", [])[:3],
                "hooks": result.get("hooks", [])[:3],
                "script": result.get("script", ""),
                "target_audience": result.get("target_audience", ""),
                "strategy": result.get("strategy", ""),
                "hashtags": result.get("hashtags", [])[:10],
                "source": source_label.lower(),
                "cached": False,
            }

            # Cache the result
            _content_cache[cache_key] = response
            return response

        except requests.HTTPError as exc:
            # Handle 429 rate limit with Retry-After
            if exc.response is not None and exc.response.status_code == 429:
                retry_after = float(exc.response.headers.get("Retry-After", 8))
                retry_after = min(retry_after, 30)  # Cap at 30s
                if attempt < 2:
                    logger.warning(
                        "Groq rate limited (429) — sleeping %.1fs before retry %d/3",
                        retry_after, attempt + 1,
                    )
                    import time as _time
                    _time.sleep(retry_after)
                    continue
            if attempt < 2:
                logger.warning("AI generation attempt %d failed: %s — retrying...", attempt + 1, exc)
                import time as _time
                _time.sleep(2)
                continue
            logger.error("AI generation failed after 3 attempts: %s", exc)
            raise HTTPException(
                status_code=500,
                detail=f"AI generation failed: {str(exc)[:200]}",
            )


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
