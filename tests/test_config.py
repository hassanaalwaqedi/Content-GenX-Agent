"""
Tests for configuration module — validation, defaults, env loading.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


class TestConfig:
    """Tests for Settings, ScoringWeights, FilterThresholds."""

    def test_settings_loads(self):
        from config import get_settings
        settings = get_settings()
        assert hasattr(settings, "youtube_api_key")
        assert hasattr(settings, "groq_api_key")
        assert hasattr(settings, "niche_keywords")
        assert hasattr(settings, "sqlite_db_path")

    def test_scoring_weights_sum_to_one(self):
        from config import get_settings
        w = get_settings().scoring_weights
        total = w.views + w.engagement + w.recency
        assert 0.99 < total < 1.01

    def test_scoring_weights_positive(self):
        from config import get_settings
        w = get_settings().scoring_weights
        assert w.views > 0
        assert w.engagement > 0
        assert w.recency > 0

    def test_filter_thresholds_non_negative(self):
        from config import get_settings
        t = get_settings().filter_thresholds
        assert t.min_views >= 0
        assert t.min_engagement_rate >= 0

    def test_youtube_max_results_bounds(self):
        from config import get_settings
        s = get_settings()
        assert 1 <= s.youtube_max_results_per_query <= 50

    def test_niche_keywords_is_list(self):
        from config import get_settings
        assert isinstance(get_settings().niche_keywords, list)
        assert len(get_settings().niche_keywords) > 0

    def test_cors_origins_is_list(self):
        from config import get_settings
        assert isinstance(get_settings().cors_allowed_origins, list)

    def test_log_level_valid(self):
        from config import get_settings
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        assert get_settings().log_level.upper() in valid_levels
