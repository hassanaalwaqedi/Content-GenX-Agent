"""Video discovery, detail, and transcript routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import require_auth
from api.datasets import resolve_dataset_id
from api.schemas import (
    TopVideosResponse,
    TranscriptResponse,
    TrendingVideosResponse,
    VideoDetailResponse,
    VideoResponse,
)
from core.queries import (
    get_fastest_growing_videos,
    get_top_videos_per_niche,
    get_transcript_by_video_id,
    get_video_by_id,
    update_transcript,
)
from pipeline.transcripts import extract_first_30s, fetch_transcript_segments

logger = logging.getLogger(__name__)
DEFAULT_THUMBNAIL = "https://via.placeholder.com/320x180.png?text=No+Thumbnail"
videos_router = APIRouter(prefix="/videos", tags=["Videos"])


def _with_thumbnail(video: VideoResponse) -> VideoResponse:
    if not video.thumbnail_url:
        video.thumbnail_url = DEFAULT_THUMBNAIL
    return video


@videos_router.get("/top", response_model=TopVideosResponse, summary="Top videos (optionally filter by category)")
async def top_videos(
    niche: Optional[str] = Query(default=None, description="Category to filter by (e.g. 'music', 'sports'). Omit for all categories."),
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    limit: int = Query(default=20, ge=1, le=100),
    region: Optional[str] = Query(default=None, description="Filter by source region code (e.g. US, DE)"),
    category: Optional[str] = Query(default=None, description="Filter by category/niche"),
    content_type: Optional[str] = Query(default=None, description="Filter by content type (shorts, long, all)"),
    platform: Optional[str] = Query(default=None, description="Filter by platform (youtube, tiktok, instagram, reddit)"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to. Defaults to active dataset."),
) -> TopVideosResponse:
    try:
        rows = get_top_videos_per_niche(
            niche,
            days=days,
            limit=limit,
            region=region,
            category=category,
            content_type=content_type,
            platform=platform,
            pipeline_run_id=resolve_dataset_id(dataset_id),
        )
    except Exception as exc:
        logger.error("Error fetching top videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    videos = [_with_thumbnail(VideoResponse(**row)) for row in rows]
    return TopVideosResponse(niche=niche or "all", days=days, count=len(videos), videos=videos)


@videos_router.get("/trending", response_model=TrendingVideosResponse, summary="Fastest-growing / trending videos")
async def trending_videos(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    region: Optional[str] = Query(default=None, description="Filter by source region code"),
    category: Optional[str] = Query(default=None, description="Filter by category/niche"),
    content_type: Optional[str] = Query(default=None, description="Filter by content type"),
    dataset_id: Optional[int] = Query(default=None, description="Pipeline run ID to scope data to. Defaults to active dataset."),
) -> TrendingVideosResponse:
    try:
        rows = get_fastest_growing_videos(
            days=days,
            limit=limit,
            region=region,
            category=category,
            content_type=content_type,
            pipeline_run_id=resolve_dataset_id(dataset_id),
        )
    except Exception as exc:
        logger.error("Error fetching trending videos: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    videos = [_with_thumbnail(VideoResponse(**row)) for row in rows]
    return TrendingVideosResponse(days=days, count=len(videos), videos=videos)


@videos_router.get("/{video_id}", response_model=VideoDetailResponse, summary="Get video details")
async def video_detail(video_id: str) -> VideoDetailResponse:
    try:
        row = get_video_by_id(video_id)
    except Exception as exc:
        logger.error("Error fetching video %s: %s", video_id, exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")
    return _with_thumbnail(VideoDetailResponse(**row))


@videos_router.post("/{video_id}/transcript", response_model=TranscriptResponse, summary="Fetch video transcript on-demand", dependencies=[Depends(require_auth)])
async def fetch_video_transcript(video_id: str) -> TranscriptResponse:
    existing = get_transcript_by_video_id(video_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")
    if existing.strip():
        words = existing.split()
        return TranscriptResponse(
            video_id=video_id,
            transcript=existing,
            transcript_30s=" ".join(words[:80]) if len(words) > 80 else existing,
            cached=True,
        )
    try:
        segments = fetch_transcript_segments(video_id)
        if not segments:
            raise HTTPException(status_code=404, detail="No transcript available for this video. Captions may be disabled.")
        full_text = " ".join(" ".join(segment["text"] for segment in segments).split())
        if len(full_text) > 5000:
            full_text = full_text[:5000] + "..."
        transcript_30s = extract_first_30s(segments)
        update_transcript(video_id, full_text)
        return TranscriptResponse(video_id=video_id, transcript=full_text, transcript_30s=transcript_30s)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching transcript for %s: %s", video_id, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch transcript. Please try again later.") from exc
