"""
Unit tests for FastAPI endpoints — contracts, error codes, pipeline lock.

Run with: python -m pytest tests/test_api_endpoints.py -v
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

# Patch DB path before importing app to use temp database
import database
import tempfile

_test_db_path = os.path.join(tempfile.mkdtemp(), "test_api.db")


@pytest.fixture(autouse=True)
def _setup_test_db(monkeypatch):
    """Use a temporary database for all API tests."""
    monkeypatch.setattr("database._get_db_path", lambda: _test_db_path)
    if hasattr(database._thread_local, "connection"):
        del database._thread_local.connection
    database.init_db()
    yield
    conn = getattr(database._thread_local, "connection", None)
    if conn:
        conn.close()
        del database._thread_local.connection


from api import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health Endpoint
# ---------------------------------------------------------------------------
class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_response_shape(self):
        r = client.get("/health")
        data = r.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "total_videos" in data
        assert "niches" in data
        assert "database" in data
        assert data["database"] == "connected"

    def test_health_has_timestamp(self):
        r = client.get("/health")
        data = r.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format


# ---------------------------------------------------------------------------
# Stats Endpoint
# ---------------------------------------------------------------------------
class TestStatsEndpoint:
    """Tests for GET /stats."""

    def test_stats_returns_200(self):
        r = client.get("/stats")
        assert r.status_code == 200

    def test_stats_empty_db(self):
        r = client.get("/stats")
        data = r.json()
        assert data["total_videos"] == 0
        assert data["total_niches"] == 0


# ---------------------------------------------------------------------------
# Videos Endpoints
# ---------------------------------------------------------------------------
class TestVideoEndpoints:
    """Tests for video-related endpoints."""

    def test_top_videos_without_niche_returns_all(self):
        """GET /videos/top without niche should return 200 (returns all categories)."""
        r = client.get("/videos/top")
        assert r.status_code == 200
        data = r.json()
        assert data["niche"] == "all"

    def test_top_videos_empty_niche(self):
        """Valid request but no data should return 200 with empty list."""
        r = client.get("/videos/top", params={"niche": "nonexistent", "days": 365})
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["videos"] == []

    def test_top_videos_days_validation(self):
        """days must be between 1 and 365."""
        r = client.get("/videos/top", params={"niche": "test", "days": 0})
        assert r.status_code == 422

        r = client.get("/videos/top", params={"niche": "test", "days": 500})
        assert r.status_code == 422

    def test_trending_returns_200(self):
        r = client.get("/videos/trending")
        assert r.status_code == 200
        data = r.json()
        assert "videos" in data

    def test_video_detail_not_found(self):
        """Non-existent video should return 404."""
        r = client.get("/videos/NONEXISTENT_ID_12345")
        assert r.status_code == 404

    def test_video_detail_found(self):
        """Video that exists should return 200 with full detail."""
        # Insert a video first
        now = datetime.now(timezone.utc).isoformat()
        database.insert_videos([{
            "video_id": "found_vid_001",
            "niche": "AI for business",
            "title": "Found Video",
            "views": 5000,
            "likes": 200,
            "comments": 50,
            "engagement_rate": 0.05,
            "score": 0.5,
            "published_at": now,
            "channel": "TestChannel",
            "thumbnail_url": "",
            "description": "A video.",
        }])

        r = client.get("/videos/found_vid_001")
        assert r.status_code == 200
        data = r.json()
        assert data["video_id"] == "found_vid_001"
        assert data["title"] == "Found Video"
        assert "created_at" in data
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# Creators Endpoint
# ---------------------------------------------------------------------------
class TestCreatorsEndpoint:
    """Tests for GET /creators/top."""

    def test_creators_returns_200(self):
        r = client.get("/creators/top")
        assert r.status_code == 200

    def test_creators_limit_validation(self):
        r = client.get("/creators/top", params={"limit": 0})
        assert r.status_code == 422

        r = client.get("/creators/top", params={"limit": 200})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Pipeline Endpoints
# ---------------------------------------------------------------------------
class TestPipelineEndpoints:
    """Tests for pipeline trigger and history."""

    def test_pipeline_history_returns_200(self):
        r = client.get("/pipeline/history")
        assert r.status_code == 200
        data = r.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)

    @patch("api.is_pipeline_running", return_value=True)
    def test_pipeline_run_409_when_already_running(self, mock_running):
        """Should return 409 Conflict if pipeline is already active."""
        r = client.post("/pipeline/run")
        assert r.status_code == 409
        assert "already in progress" in r.json()["detail"]

    def test_pipeline_auth_with_wrong_key(self, monkeypatch):
        """When PIPELINE_API_KEY is set, wrong key should return 403."""
        # Set a required key
        monkeypatch.setattr("api._settings.pipeline_api_key", "correct-secret-key")

        r = client.post(
            "/pipeline/run",
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code == 403

    def test_pipeline_auth_without_key_header(self, monkeypatch):
        """When PIPELINE_API_KEY is set, missing header should return 403."""
        monkeypatch.setattr("api._settings.pipeline_api_key", "correct-secret-key")

        r = client.post("/pipeline/run")
        assert r.status_code == 403

    def test_pipeline_auth_correct_key(self, monkeypatch):
        """Correct API key should be accepted."""
        monkeypatch.setattr("api._settings.pipeline_api_key", "correct-secret-key")
        monkeypatch.setattr("api.is_pipeline_running", lambda: False)

        r = client.post(
            "/pipeline/run",
            headers={"X-API-Key": "correct-secret-key"},
        )
        # Should be 200 (accepted), not 403
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
class TestCORS:
    """Tests for CORS configuration."""

    def test_allowed_origin(self):
        """Configured origin should receive CORS headers."""
        r = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert r.status_code == 200
        # Should have CORS header for this origin
        cors_header = r.headers.get("access-control-allow-origin", "")
        assert cors_header == "http://localhost:3000"

    def test_disallowed_origin(self):
        """Unknown origin should not receive CORS headers."""
        r = client.get("/health", headers={"Origin": "http://evil.com"})
        assert r.status_code == 200
        cors_header = r.headers.get("access-control-allow-origin", "")
        assert cors_header != "http://evil.com"
        assert cors_header != "*"
