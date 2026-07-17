"""Read-only Reddit Intelligence endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from api.datasets import resolve_dataset_id
from connectors.registry import ConnectorRegistry
from core.queries import (
    get_reddit_clusters,
    get_reddit_contributors,
    get_reddit_discussions,
    get_reddit_opportunities,
    get_reddit_overview,
    get_reddit_pain_points,
    get_reddit_sentiment,
    get_trending_subreddits,
)

reddit_router = APIRouter(prefix="/platforms/reddit", tags=["Reddit Intelligence"])


@reddit_router.get("/overview")
async def overview(
    days: int = Query(default=30, ge=1, le=365),
    dataset_id: Optional[int] = Query(default=None),
):
    return get_reddit_overview(days=days, pipeline_run_id=resolve_dataset_id(dataset_id))


@reddit_router.get("/subreddits/trending")
async def trending_subreddits(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=8, ge=1, le=20),
    dataset_id: Optional[int] = Query(default=None),
):
    items = get_trending_subreddits(days=days, limit=limit, pipeline_run_id=resolve_dataset_id(dataset_id))
    return {"count": len(items), "subreddits": items}


@reddit_router.get("/discussions/emerging")
async def emerging_discussions(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=100),
    dataset_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=120),
    subreddit: Optional[str] = Query(default=None, max_length=100),
    sentiment: Optional[str] = Query(default=None, max_length=16),
    min_upvotes: int = Query(default=0, ge=0),
    min_comments: int = Query(default=0, ge=0),
    min_opportunity: int = Query(default=0, ge=0, le=100),
    sort_by: str = Query(default="velocity", pattern="^(velocity|engagement|recency|opportunity)$"),
):
    items = get_reddit_discussions(
        days=days,
        limit=limit,
        pipeline_run_id=resolve_dataset_id(dataset_id),
        search=search,
        subreddit=subreddit,
        sentiment=sentiment,
        min_upvotes=min_upvotes,
        min_comments=min_comments,
        min_opportunity=min_opportunity,
        sort_by=sort_by,
    )
    return {"count": len(items), "discussions": items}


@reddit_router.get("/pain-points")
async def pain_points(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=30),
    dataset_id: Optional[int] = Query(default=None),
):
    items = get_reddit_pain_points(days=days, limit=limit, pipeline_run_id=resolve_dataset_id(dataset_id))
    return {"count": len(items), "pain_points": items}


@reddit_router.get("/clusters")
async def clusters(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=30),
    dataset_id: Optional[int] = Query(default=None),
):
    items = get_reddit_clusters(days=days, limit=limit, pipeline_run_id=resolve_dataset_id(dataset_id))
    return {"count": len(items), "clusters": items}


@reddit_router.get("/sentiment")
async def sentiment(
    days: int = Query(default=30, ge=1, le=365),
    dataset_id: Optional[int] = Query(default=None),
):
    return get_reddit_sentiment(days=days, pipeline_run_id=resolve_dataset_id(dataset_id))


@reddit_router.get("/opportunities")
async def opportunities(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=30),
    dataset_id: Optional[int] = Query(default=None),
):
    items = get_reddit_opportunities(days=days, limit=limit, pipeline_run_id=resolve_dataset_id(dataset_id))
    return {"count": len(items), "opportunities": items}


@reddit_router.get("/contributors")
async def contributors(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=30),
    dataset_id: Optional[int] = Query(default=None),
):
    items = get_reddit_contributors(days=days, limit=limit, pipeline_run_id=resolve_dataset_id(dataset_id))
    return {"count": len(items), "contributors": items}


@reddit_router.get("/health")
async def health(dataset_id: Optional[int] = Query(default=None)):
    connector = ConnectorRegistry().health_check_all().get("reddit")
    overview_data = get_reddit_overview(days=365, pipeline_run_id=resolve_dataset_id(dataset_id))
    return {
        "connector": connector.to_dict() if connector else {"platform": "reddit", "status": "disabled"},
        "indexed_posts": overview_data["posts_analyzed"],
        "last_indexed_at": overview_data["last_indexed_at"],
        "analysis_coverage": overview_data["analysis_coverage"],
    }
