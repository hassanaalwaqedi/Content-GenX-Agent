"""Dataset/workspace routes and shared dataset resolution helpers."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.auth import require_auth
from core.database import get_active_dataset, get_dataset_list, get_dataset_stats, set_active_dataset

logger = logging.getLogger(__name__)
datasets_router = APIRouter(prefix="/datasets", tags=["Datasets"])


def resolve_dataset_id(dataset_id: Optional[int]) -> Optional[int]:
    """Resolve a request dataset ID, including the all-data sentinel value."""
    if dataset_id is not None:
        return None if dataset_id == 0 else dataset_id
    active = get_active_dataset()
    return active["id"] if active else None


@datasets_router.get("", summary="List all completed pipeline runs as datasets")
async def list_datasets(limit: int = Query(default=20, ge=1, le=50)):
    try:
        datasets = get_dataset_list(limit=limit)
    except Exception as exc:
        logger.error("Error fetching dataset list: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    return {"count": len(datasets), "datasets": datasets}


@datasets_router.get("/active", summary="Get the currently active dataset")
async def active_dataset():
    try:
        active = get_active_dataset()
    except Exception as exc:
        logger.error("Error fetching active dataset: %s", exc)
        raise HTTPException(status_code=500, detail="Internal query error") from exc
    if not active:
        return {"active": None, "stats": None}
    try:
        stats_data = get_dataset_stats(active["id"])
    except Exception as exc:
        logger.warning("Unable to read active dataset statistics: %s", exc)
        stats_data = {}
    return {"active": active, "stats": stats_data}


@datasets_router.post(
    "/{run_id}/activate",
    summary="Set a pipeline run as active dataset",
    dependencies=[Depends(require_auth)],
)
async def activate_dataset(run_id: int):
    try:
        set_active_dataset(run_id)
        active = get_active_dataset()
        stats_data = get_dataset_stats(run_id) if active else {}
    except Exception as exc:
        logger.error("Error activating dataset: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to activate dataset") from exc
    return {"activated": True, "active": active, "stats": stats_data}
