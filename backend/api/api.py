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

import hmac
import logging
import threading
from contextlib import asynccontextmanager

import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from api.auth import auth_router, require_auth
from api.creators import creators_router
from api.datasets import datasets_router, resolve_dataset_id
from api.middleware import RequestProtectionMiddleware
from api.reddit import reddit_router
from api.schemas import TopVideosResponse, VideoResponse
from api.system import system_router
from api.versioning import V1PathPrefixMiddleware
from api.videos import videos_router
from core.config import get_settings
from core.logging import configure_logging
from core.database import (
    init_db, get_pipeline_history,
    save_pipeline_config, get_pipeline_config,
    list_pipeline_configs, delete_pipeline_config, get_last_used_config,
    acquire_pipeline_lock, release_pipeline_lock,
)
from core.queries import (
    get_videos_with_topics,
)
from pipeline.trends import discover_trends, discover_opportunities

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
    return resolve_dataset_id(dataset_id)


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # ---- Startup ----
    configure_logging(_settings)
    init_db()
    logger.info(
        "API startup complete -- database initialized; rate_limit=%s/%ss.",
        _settings.api_rate_limit_requests,
        _settings.api_rate_limit_window_seconds,
    )
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

# CORS -- allow specific origins only (no wildcard with credentials)
_settings = get_settings()
app.add_middleware(V1PathPrefixMiddleware)
app.add_middleware(
    RequestProtectionMiddleware,
    max_requests=_settings.api_rate_limit_requests,
    window_seconds=_settings.api_rate_limit_window_seconds,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes
app.include_router(auth_router)
app.include_router(creators_router)
app.include_router(datasets_router)
app.include_router(reddit_router)
app.include_router(system_router)
app.include_router(videos_router)

# Pipeline authentication (authenticated operator or optional shared API key)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_pipeline_access(
    request: Request,
    api_key: Optional[str] = Security(_api_key_header),
) -> None:
    """Authorize a costly scan without exposing an unauthenticated trigger."""
    required_key = _settings.pipeline_api_key
    if required_key and api_key and hmac.compare_digest(api_key, required_key):
        return

    # The browser client already sends its JWT/cookie. Keeping the shared key
    # as an alternative preserves service-to-service automation.
    await require_auth(request, request.cookies.get("genx_session"))


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
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
def _launch_pipeline(config_id: Optional[int], triggered_by: str = "api") -> PipelineRunResponse:
    """Reserve the database lock before starting the background scan thread."""
    try:
        init_db()
        run_id = acquire_pipeline_lock(
            triggered_by=triggered_by,
            config_snapshot={"config_id": config_id} if config_id else {},
        )
    except RuntimeError:
        raise HTTPException(
            status_code=409,
            detail="A pipeline run is already in progress.",
        )

    def _background_run() -> None:
        try:
            from pipeline.runner import run_pipeline  # deferred import

            run_pipeline(
                triggered_by=triggered_by,
                config_id=config_id,
                pre_acquired_run_id=run_id,
            )
            logger.info("Background pipeline run completed.")
        except Exception as exc:
            logger.error("Background pipeline run failed: %s", exc, exc_info=True)
            try:
                release_pipeline_lock(
                    run_id,
                    {
                        "status": "failed",
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "error": "Background pipeline worker failed to start.",
                    },
                )
            except Exception as release_exc:
                logger.error("Unable to release failed pipeline run #%s: %s", run_id, release_exc)

    thread = threading.Thread(target=_background_run, daemon=True)
    try:
        thread.start()
    except Exception as exc:
        logger.error("Unable to start pipeline worker: %s", exc, exc_info=True)
        release_pipeline_lock(
            run_id,
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error": "Unable to start pipeline worker.",
            },
        )
        raise HTTPException(status_code=500, detail="Unable to start pipeline worker.") from exc

    return PipelineRunResponse(
        status="accepted",
        message=f"Pipeline triggered{f' with config #{config_id}' if config_id else ' (default config)'}.",
        triggered_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    summary="Trigger pipeline manually",
    tags=["Pipeline"],
    dependencies=[Depends(_verify_pipeline_access)],
)
async def run_pipeline_endpoint(
    config_id: Optional[int] = Query(default=None, description="Pipeline config ID to use"),
) -> PipelineRunResponse:
    """Trigger a full pipeline run (ingest -> process -> store)."""
    return _launch_pipeline(config_id, triggered_by="api")


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


class RedditScanRequest(BaseModel):
    """A Reddit-only pipeline request that reuses the existing run lock."""

    regions: List[str] = Field(default=["US"])
    keywords: List[str] = Field(default=[])
    categories: List[str] = Field(default=[])
    name: str = Field(default="Reddit Intelligence Scan", max_length=100)


@app.post(
    "/pipeline/config",
    tags=["Pipeline Config"],
    summary="Create or update a pipeline config",
    dependencies=[Depends(require_auth)],
)
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


@app.post(
    "/platforms/reddit/scan",
    response_model=PipelineRunResponse,
    tags=["Reddit Intelligence"],
    dependencies=[Depends(_verify_pipeline_access)],
)
async def run_reddit_scan(request: RedditScanRequest) -> PipelineRunResponse:
    if not request.regions or len(request.regions) > 5:
        raise HTTPException(400, "Select between one and five regions.")
    invalid_regions = set(request.regions) - VALID_REGIONS
    if invalid_regions:
        raise HTTPException(400, f"Invalid regions: {', '.join(sorted(invalid_regions))}")
    config_id = save_pipeline_config({
        "name": request.name.strip() or "Reddit Intelligence Scan",
        "regions": request.regions,
        "platforms": ["reddit"],
        "categories": [category.lower().strip() for category in request.categories[:15] if category.strip()],
        "keywords": [keyword.strip() for keyword in request.keywords[:10] if keyword.strip()],
        "content_type": "all",
        "is_preset": False,
    })
    return _launch_pipeline(config_id, triggered_by="reddit")


@app.delete(
    "/pipeline/config/{config_id}",
    tags=["Pipeline Config"],
    summary="Delete a pipeline config",
    dependencies=[Depends(require_auth)],
)
async def delete_config(config_id: int):
    deleted = delete_pipeline_config(config_id)
    if not deleted:
        raise HTTPException(404, f"Config #{config_id} not found.")
    return {"deleted": True, "id": config_id}


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


def _normalize_trend_name(value: str) -> str:
    """Normalize a trend label in the same way as the trend-clustering engine."""
    return " ".join(str(value or "").lower().replace("_", " ").split())


@app.get("/trends/videos", response_model=TopVideosResponse, tags=["Trends"])
async def trend_videos(
    trend: str = Query(..., min_length=1, description="Trend label returned by /trends/discover"),
    days: int = Query(365, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(500, ge=1, le=500, description="Maximum exact trend members to return"),
    platform: Optional[str] = Query(default=None, description="Filter exact trend members by platform"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
) -> TopVideosResponse:
    """Return the exact database records that belong to a discovered trend cluster."""
    run_id = _resolve_dataset_id(dataset_id)
    requested_trend = _normalize_trend_name(trend)

    try:
        videos = get_videos_with_topics(days=days, limit=500, pipeline_run_id=run_id)
        clusters = discover_trends(videos, min_count=1, limit=500)
    except Exception as exc:
        logger.error("Error resolving trend videos for %s: %s", trend, exc)
        raise HTTPException(status_code=500, detail="Unable to resolve trend videos")

    cluster = next(
        (item for item in clusters if _normalize_trend_name(item.get("trend", "")) == requested_trend),
        None,
    )
    if cluster is None:
        return TopVideosResponse(niche=trend, days=days, count=0, videos=[])

    rows = cluster["videos"]
    if platform:
        normalized_platform = platform.lower()
        rows = [item for item in rows if str(item.get("platform", "")).lower() == normalized_platform]
    rows = sorted(rows, key=lambda item: item.get("score", 0), reverse=True)[:limit]
    videos_response = [VideoResponse(**row) for row in rows]
    for video in videos_response:
        if not video.thumbnail_url:
            video.thumbnail_url = DEFAULT_THUMBNAIL

    return TopVideosResponse(
        niche=cluster["trend"], days=days, count=len(videos_response), videos=videos_response,
    )


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
    dependencies=[Depends(require_auth)],
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

    from enrichment.ai import GroqClient
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
    configure_logging(settings)
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
