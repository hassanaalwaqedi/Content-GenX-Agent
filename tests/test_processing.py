"""
Unit tests for Content Intelligence Platform — Processing module.

Tests the core scoring logic, helper functions, and edge cases.
Run with: python -m pytest tests/ -v
"""

import math
from datetime import datetime, timezone, timedelta

import pytest

# Import the functions under test
import sys
import os

# Add parent directory to path so we can import project modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from processing import (
    _safe_engagement_rate,
    _recency_factor,
    _normalize,
    ProcessedVideo,
)


# ---------------------------------------------------------------------------
# _safe_engagement_rate
# ---------------------------------------------------------------------------
class TestEngagementRate:
    """Tests for engagement rate calculation."""

    def test_normal_case(self):
        """Standard engagement calculation."""
        rate = _safe_engagement_rate(views=10_000, likes=500, comments=100)
        assert rate == pytest.approx(0.06, rel=1e-6)

    def test_zero_views_returns_zero(self):
        """Division by zero must be guarded."""
        assert _safe_engagement_rate(views=0, likes=100, comments=50) == 0.0

    def test_negative_views_returns_zero(self):
        """Negative views (data anomaly) should not crash."""
        assert _safe_engagement_rate(views=-5, likes=10, comments=5) == 0.0

    def test_zero_engagement(self):
        """Video with views but no likes/comments."""
        assert _safe_engagement_rate(views=1000, likes=0, comments=0) == 0.0

    def test_high_engagement(self):
        """Very high engagement (viral content)."""
        rate = _safe_engagement_rate(views=100, likes=80, comments=20)
        assert rate == pytest.approx(1.0, rel=1e-6)


# ---------------------------------------------------------------------------
# _recency_factor
# ---------------------------------------------------------------------------
class TestRecencyFactor:
    """Tests for exponential decay recency scoring."""

    def test_today_scores_near_one(self):
        """A video published now should score ~1.0."""
        now = datetime.now(timezone.utc).isoformat()
        factor = _recency_factor(now)
        assert factor > 0.99

    def test_30_days_ago_scores_half(self):
        """A video from exactly one half-life ago should score ~0.5."""
        thirty_days_ago = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat()
        factor = _recency_factor(thirty_days_ago)
        assert factor == pytest.approx(0.5, abs=0.02)

    def test_60_days_ago_scores_quarter(self):
        """Two half-lives = ~0.25."""
        sixty_days_ago = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()
        factor = _recency_factor(sixty_days_ago)
        assert factor == pytest.approx(0.25, abs=0.02)

    def test_invalid_date_returns_zero(self):
        """Malformed date strings should not crash."""
        assert _recency_factor("not-a-date") == 0.0

    def test_empty_string_returns_zero(self):
        """Empty string should not crash."""
        assert _recency_factor("") == 0.0

    def test_youtube_z_format(self):
        """YouTube-style ISO-8601 with 'Z' suffix should parse correctly."""
        now_z = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        factor = _recency_factor(now_z)
        assert factor > 0.99


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------
class TestNormalize:
    """Tests for min-max normalization."""

    def test_middle_value(self):
        """Mid-point of range should normalize to 0.5."""
        assert _normalize(5.0, 0.0, 10.0) == pytest.approx(0.5)

    def test_min_value(self):
        """Minimum value should normalize to 0.0."""
        assert _normalize(0.0, 0.0, 10.0) == pytest.approx(0.0)

    def test_max_value(self):
        """Maximum value should normalize to 1.0."""
        assert _normalize(10.0, 0.0, 10.0) == pytest.approx(1.0)

    def test_equal_min_max_returns_half(self):
        """When all values are identical, normalization returns 0.5."""
        assert _normalize(5.0, 5.0, 5.0) == 0.5


# ---------------------------------------------------------------------------
# ProcessedVideo Pydantic model
# ---------------------------------------------------------------------------
class TestProcessedVideo:
    """Tests for the ProcessedVideo validation model."""

    def test_valid_video(self):
        """A well-formed video should validate without errors."""
        v = ProcessedVideo(
            video_id="abc123",
            niche="AI for business",
            title="Test Video",
            views=10000,
            likes=500,
            comments=100,
            engagement_rate=0.06,
            score=0.75,
        )
        assert v.video_id == "abc123"
        assert v.platform == "youtube"

    def test_to_dict_roundtrip(self):
        """to_dict() should produce a serializable dictionary."""
        v = ProcessedVideo(
            video_id="xyz789",
            niche="prompt engineering",
            title="How to Prompt",
            views=5000,
            engagement_rate=0.04,
            score=0.5,
        )
        d = v.to_dict()
        assert isinstance(d, dict)
        assert d["video_id"] == "xyz789"
        assert d["likes"] == 0  # default value

    def test_defaults_applied(self):
        """Missing optional fields should get default values."""
        v = ProcessedVideo(
            video_id="test",
            niche="AI",
            title="Test",
        )
        assert v.views == 0
        assert v.likes == 0
        assert v.platform == "youtube"
        assert v.description == ""

    def test_missing_required_raises(self):
        """Missing required fields should raise ValidationError."""
        with pytest.raises(Exception):
            ProcessedVideo(video_id="test")  # missing niche and title
