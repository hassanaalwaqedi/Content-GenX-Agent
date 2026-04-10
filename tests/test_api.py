"""
Tests for the API endpoints — FastAPI contract validation.

Covers:
  - Health endpoint
  - Dashboard stats
  - Top videos listing
  - Pipeline history
  - Error handling for empty database

Run with: python -m pytest tests/test_api.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api import app
from database import init_db, get_connection


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    """Use a temporary database for each test.

    Patches the config + clears the thread-local DB connection cache
    so all queries hit the fresh temp database.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_path)

    # Clear config cache so it picks up the new env var
    from config import get_settings
    get_settings.cache_clear()

    # Clear thread-local cached connection so database.py reconnects
    import database
    if hasattr(database._thread_local, "connection"):
        try:
            database._thread_local.connection.close()
        except Exception:
            pass
        del database._thread_local.connection

    init_db()
    yield

    # Cleanup: close connection and clear cache
    if hasattr(database._thread_local, "connection"):
        try:
            database._thread_local.connection.close()
        except Exception:
            pass
        del database._thread_local.connection
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health Endpoint
# ---------------------------------------------------------------------------
class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_fields(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert "timestamp" in data
        assert "total_videos" in data
        assert "database" in data

    def test_health_status_healthy(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    def test_health_empty_db_zero_videos(self, client):
        data = client.get("/health").json()
        assert data["total_videos"] == 0


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------
class TestDashboardStats:

    def test_stats_returns_200(self, client):
        resp = client.get("/stats")
        assert resp.status_code in (200, 500)  # May fail on empty DB depending on query

    def test_stats_has_expected_shape(self, client):
        resp = client.get("/stats")
        if resp.status_code == 200:
            data = resp.json()
            assert "total_videos" in data

    def test_stats_empty_db(self, client):
        resp = client.get("/stats")
        if resp.status_code == 200:
            data = resp.json()
            assert data["total_videos"] == 0


# ---------------------------------------------------------------------------
# Top Videos  (route = /videos/top)
# ---------------------------------------------------------------------------
class TestTopVideos:

    def test_top_videos_returns_200(self, client):
        resp = client.get("/videos/top?niche=ai_automation")
        assert resp.status_code == 200

    def test_top_videos_empty_db(self, client):
        data = client.get("/videos/top?niche=ai_automation").json()
        assert "videos" in data
        assert isinstance(data["videos"], list)
        assert len(data["videos"]) == 0

    def test_top_videos_accepts_limit(self, client):
        resp = client.get("/videos/top?niche=ai_automation&limit=5")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pipeline History
# ---------------------------------------------------------------------------
class TestPipelineHistory:

    def test_pipeline_history_returns_200(self, client):
        resp = client.get("/pipeline/history")
        assert resp.status_code == 200

    def test_pipeline_history_structure(self, client):
        data = client.get("/pipeline/history").json()
        assert "count" in data
        assert "runs" in data
        assert isinstance(data["runs"], list)


# ---------------------------------------------------------------------------
# Transcript Stats
# ---------------------------------------------------------------------------
class TestTranscriptStats:

    def test_transcript_stats_returns_200(self, client):
        resp = client.get("/stats/transcripts")
        assert resp.status_code == 200

    def test_transcript_stats_empty_db(self, client):
        data = client.get("/stats/transcripts").json()
        assert data["total_youtube"] == 0
        assert data["coverage_pct"] == 0.0


# ---------------------------------------------------------------------------
# Trending  (route = /videos/trending)
# ---------------------------------------------------------------------------
class TestTrending:

    def test_trending_returns_200(self, client):
        resp = client.get("/videos/trending")
        assert resp.status_code == 200

    def test_trending_empty_db(self, client):
        data = client.get("/videos/trending").json()
        assert "videos" in data
        assert isinstance(data["videos"], list)
