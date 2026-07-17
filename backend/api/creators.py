"""Creator intelligence API routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.datasets import resolve_dataset_id
from api.schemas import CreatorResponse, TopCreatorsResponse
from core.queries import (
    get_creator_intelligence,
    get_creator_videos,
    get_creators_by_trend,
    get_rising_creators,
    get_top_creators,
)

logger = logging.getLogger(__name__)
DEFAULT_THUMBNAIL = "https://via.placeholder.com/320x180.png?text=No+Thumbnail"

creators_router = APIRouter(prefix="/creators", tags=["Creators"])


@creators_router.get(
    "/top",
    response_model=TopCreatorsResponse,
    summary="Top content creators",
)
async def top_creators(
    limit: int = Query(default=20, ge=1, le=100),
    min_videos: int = Query(default=2, ge=1, description="Minimum number of videos to qualify"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
) -> TopCreatorsResponse:
    """Return creators ranked by aggregate score and engagement."""
    try:
        rows = get_top_creators(
            limit=limit,
            min_videos=min_videos,
            pipeline_run_id=resolve_dataset_id(dataset_id),
        )
    except Exception as exc:
        logger.error("Error fetching top creators: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc

    creators = [CreatorResponse(**row) for row in rows]
    return TopCreatorsResponse(count=len(creators), creators=creators)


@creators_router.get("/intelligence", summary="Creator intelligence with advanced metrics")
async def creator_intelligence(
    days: int = Query(default=365, ge=1, le=730),
    limit: int = Query(default=30, ge=1, le=100),
    min_videos: int = Query(default=1, ge=1),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    try:
        data = get_creator_intelligence(
            days=days,
            limit=limit,
            min_videos=min_videos,
            pipeline_run_id=resolve_dataset_id(dataset_id),
        )
    except Exception as exc:
        logger.error("Error fetching creator intelligence: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    return {"count": len(data), "creators": data}


@creators_router.get("/rising", summary="Rising creators with high growth velocity")
async def rising_creators(
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    try:
        data = get_rising_creators(
            days=days,
            limit=limit,
            pipeline_run_id=resolve_dataset_id(dataset_id),
        )
    except Exception as exc:
        logger.error("Error fetching rising creators: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    return {"count": len(data), "creators": data}


@creators_router.get("/by-trend", summary="Creators filtered by trend/topic")
async def creators_by_trend(
    trend: str = Query(..., description="Trend or topic keyword to filter by"),
    days: int = Query(default=365, ge=1, le=730),
    limit: int = Query(default=20, ge=1, le=100),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to."),
):
    try:
        data = get_creators_by_trend(
            trend=trend,
            days=days,
            limit=limit,
            pipeline_run_id=resolve_dataset_id(dataset_id),
        )
    except Exception as exc:
        logger.error("Error fetching creators by trend: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    return {"trend": trend, "count": len(data), "creators": data}


@creators_router.get("/{channel}/videos", summary="Get videos for a specific creator")
async def creator_videos(channel: str, limit: int = Query(default=20, ge=1, le=50)):
    try:
        data = get_creator_videos(channel=channel, limit=limit)
    except Exception as exc:
        logger.error("Error fetching creator videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc

    videos = []
    for video in data:
        if not video.get("thumbnail_url"):
            video["thumbnail_url"] = DEFAULT_THUMBNAIL
        videos.append(video)
    return {"channel": channel, "count": len(videos), "videos": videos}
