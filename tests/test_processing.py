"""
Tests for the processing module — scoring, filtering, normalization.

Covers:
  - Engagement rate calculation
  - Recency factor (exponential decay)
  - Min-max normalization
  - Composite score computation
  - Filter thresholds
  - Edge cases (zero views, future dates, empty input)
"""

import math
from datetime import datetime, timezone, timedelta

import pytest

# Ensure project root is on path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processing import (
    _safe_engagement_rate,
    _recency_factor,
    _normalize,
    process_videos,
)
from ingestion import RawVideo


# ---------------------------------------------------------------------------
# Engagement Rate Tests
# ---------------------------------------------------------------------------
class TestEngagementRate:

    def test_normal_engagement(self):
        assert _safe_engagement_rate(1000, 50, 10) == pytest.approx(0.06, abs=1e-6)

    def test_zero_views_returns_zero(self):
        assert _safe_engagement_rate(0, 100, 50) == 0.0

    def test_negative_views_returns_zero(self):
        assert _safe_engagement_rate(-1, 10, 5) == 0.0

    def test_high_engagement(self):
        rate = _safe_engagement_rate(100, 200, 50)
        assert rate == pytest.approx(2.5, abs=1e-6)

    def test_zero_engagement(self):
        assert _safe_engagement_rate(10000, 0, 0) == 0.0


# ---------------------------------------------------------------------------
# Recency Factor Tests
# ---------------------------------------------------------------------------
class TestRecencyFactor:

    def test_today_scores_near_one(self):
        now = datetime.now(timezone.utc).isoformat()
        assert _recency_factor(now) > 0.95

    def test_30_day_old_scores_half(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        factor = _recency_factor(ts)
        assert 0.45 < factor < 0.55

    def test_ancient_video_near_zero(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        assert _recency_factor(ts) < 0.01

    def test_invalid_date_returns_zero(self):
        assert _recency_factor("not-a-date") == 0.0
        assert _recency_factor("") == 0.0

    def test_youtube_z_format(self):
        factor = _recency_factor("2026-04-10T12:00:00Z")
        assert 0.0 <= factor <= 1.0

    def test_custom_half_life(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        factor = _recency_factor(ts, half_life_days=7.0)
        assert 0.45 < factor < 0.55


# ---------------------------------------------------------------------------
# Normalization Tests
# ---------------------------------------------------------------------------
class TestNormalize:

    def test_mid_value(self):
        assert _normalize(5.0, 0.0, 10.0) == pytest.approx(0.5)

    def test_min_value(self):
        assert _normalize(0.0, 0.0, 10.0) == pytest.approx(0.0)

    def test_max_value(self):
        assert _normalize(10.0, 0.0, 10.0) == pytest.approx(1.0)

    def test_equal_min_max_returns_half(self):
        assert _normalize(5.0, 5.0, 5.0) == 0.5


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------
class TestProcessVideos:

    def _make_video(self, video_id="v1", views=5000, likes=100, comments=20, **kw):
        defaults = dict(
            video_id=video_id,
            title=f"Test Video {video_id}",
            channel="TestChannel",
            description="A test video",
            published_at=datetime.now(timezone.utc).isoformat(),
            thumbnail_url="https://example.com/thumb.jpg",
            views=views, likes=likes, comments=comments,
            niche="ai_automation", platform="youtube",
        )
        defaults.update(kw)
        return RawVideo(**defaults)

    def test_empty_input(self):
        assert process_videos([]) == []

    def test_single_video(self):
        result = process_videos([self._make_video()])
        assert len(result) == 1
        assert result[0]["video_id"] == "v1"

    def test_score_positive(self):
        result = process_videos([self._make_video(views=10000, likes=500)])
        assert result[0]["score"] > 0

    def test_higher_views_higher_score(self):
        videos = [
            self._make_video("low", views=5000, likes=200, comments=50),
            self._make_video("high", views=500000, likes=15000, comments=5000),
        ]
        result = process_videos(videos)
        scores = {r["video_id"]: r["score"] for r in result}
        assert "high" in scores and "low" in scores
        assert scores["high"] > scores["low"]

    def test_engagement_rate_computed(self):
        result = process_videos([self._make_video(views=1000, likes=50, comments=10)])
        assert result[0]["engagement_rate"] == pytest.approx(0.06, abs=1e-4)

    def test_sorted_descending(self):
        videos = [
            self._make_video("a", views=1000, likes=10, comments=5),
            self._make_video("b", views=1000000, likes=50000, comments=10000),
            self._make_video("c", views=50000, likes=500, comments=100),
        ]
        result = process_videos(videos)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)
