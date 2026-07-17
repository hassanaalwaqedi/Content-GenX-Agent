"""System health, connector, and aggregate statistics routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from api.datasets import resolve_dataset_id
from api.schemas import HealthResponse, StatsResponse, TranscriptStatsResponse
from connectors.registry import ConnectorRegistry
from core.database import get_distinct_niches, get_video_count
from core.queries import get_transcript_stats, get_video_stats

logger = logging.getLogger(__name__)
system_router = APIRouter(tags=["System"])


@system_router.get("/health", response_model=HealthResponse, summary="System health check")
async def health() -> HealthResponse:
    try:
        total = get_video_count()
        niches = get_distinct_niches()
    except Exception as exc:
        logger.error("Health check database error: %s", exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_videos=total,
        niches=niches,
        database="connected",
    )


@system_router.get("/connectors/health", summary="Connector health checks", tags=["Connectors"])
async def connector_health() -> dict[str, Any]:
    results = ConnectorRegistry().health_check_all()
    return {"connectors": {platform: health.to_dict() for platform, health in results.items()}}


@system_router.get("/stats", response_model=StatsResponse, summary="Database aggregate statistics")
async def stats(
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope stats to. Defaults to active dataset."),
) -> StatsResponse:
    try:
        data = get_video_stats(pipeline_run_id=resolve_dataset_id(dataset_id))
    except Exception as exc:
        logger.error("Error fetching stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    return StatsResponse(**data)


@system_router.get("/stats/transcripts", response_model=TranscriptStatsResponse, summary="Transcript extraction coverage")
async def transcript_stats() -> TranscriptStatsResponse:
    try:
        data = get_transcript_stats()
    except Exception as exc:
        logger.error("Error fetching transcript stats: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    return TranscriptStatsResponse(**data)
