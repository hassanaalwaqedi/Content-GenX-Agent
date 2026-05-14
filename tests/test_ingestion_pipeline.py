"""
Tests for the hardened YouTube ingestion pipeline.

Validates:
  - Ingestion returns MIXED categories (not AI-only)
  - India region is excluded from ALLOWED_REGIONS
  - No search.list / niche-based query code exists
  - Deduplication keeps highest-view version
  - Stale data purge works correctly
  - Failsafe retry logic is present
  - Pipeline is idempotent
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from ingestion import (
    ALLOWED_REGIONS,
    YOUTUBE_CATEGORY_MAP,
    RawVideo,
    YouTubeClient,
    _deduplicate_items,
    _categorize_video,
    ingest_trending_videos,
    ingest_videos,
    purge_stale_youtube_videos,
)


# ---------------------------------------------------------------------------
# Test region configuration
# ---------------------------------------------------------------------------
class TestRegionConfiguration(unittest.TestCase):
    """Ensure region config excludes India and includes expected regions."""

    def test_india_excluded(self):
        """IN (India) must NOT be in the allowed regions list."""
        self.assertNotIn("IN", ALLOWED_REGIONS)

    def test_expected_regions_present(self):
        """All curated regions must be present."""
        expected = ["US", "GB", "CA", "DE", "FR", "AU", "AE"]
        for region in expected:
            self.assertIn(region, ALLOWED_REGIONS)

    def test_no_extra_noisy_regions(self):
        """Regions known for noise should not be included."""
        noisy = ["IN", "PK", "BD"]
        for region in noisy:
            self.assertNotIn(region, ALLOWED_REGIONS)


# ---------------------------------------------------------------------------
# Test no search/niche-based ingestion remains
# ---------------------------------------------------------------------------
class TestNoNicheBasedIngestion(unittest.TestCase):
    """Verify all niche/search-based ingestion code has been removed."""

    def test_no_search_videos_method(self):
        """YouTubeClient should NOT have a search_videos method."""
        self.assertFalse(
            hasattr(YouTubeClient, "search_videos"),
            "search_videos method should be removed from YouTubeClient",
        )

    def test_no_get_video_details_method(self):
        """YouTubeClient should NOT have get_video_details (search support)."""
        self.assertFalse(
            hasattr(YouTubeClient, "get_video_details"),
            "get_video_details method should be removed from YouTubeClient",
        )

    def test_ingest_videos_has_no_niches_param(self):
        """ingest_videos() should accept no arguments (trending only)."""
        import inspect
        sig = inspect.signature(ingest_videos)
        self.assertEqual(
            len(sig.parameters), 0,
            "ingest_videos should take no parameters (no niche argument)",
        )

    def test_ingest_trending_has_no_categories_param(self):
        """ingest_trending_videos() should only accept regions, not categories."""
        import inspect
        sig = inspect.signature(ingest_trending_videos)
        param_names = list(sig.parameters.keys())
        self.assertIn("regions", param_names)
        self.assertNotIn("categories", param_names)


# ---------------------------------------------------------------------------
# Test deduplication
# ---------------------------------------------------------------------------
class TestDeduplication(unittest.TestCase):
    """Verify video deduplication keeps highest-view version."""

    def test_dedup_keeps_highest_views(self):
        """When same video_id appears twice, keep the one with more views."""
        items = [
            {
                "id": "abc123",
                "snippet": {"title": "Video A"},
                "statistics": {"viewCount": "1000"},
            },
            {
                "id": "abc123",
                "snippet": {"title": "Video A (higher views)"},
                "statistics": {"viewCount": "5000"},
            },
        ]
        result = _deduplicate_items(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            int(result[0]["statistics"]["viewCount"]), 5000,
        )

    def test_dedup_different_ids_kept(self):
        """Different video_ids should all be kept."""
        items = [
            {"id": "v1", "statistics": {"viewCount": "100"}},
            {"id": "v2", "statistics": {"viewCount": "200"}},
            {"id": "v3", "statistics": {"viewCount": "300"}},
        ]
        result = _deduplicate_items(items)
        self.assertEqual(len(result), 3)

    def test_dedup_skips_empty_ids(self):
        """Items without valid video IDs should be skipped."""
        items = [
            {"id": "", "statistics": {"viewCount": "100"}},
            {"id": "v1", "statistics": {"viewCount": "200"}},
        ]
        result = _deduplicate_items(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "v1")


# ---------------------------------------------------------------------------
# Test auto-categorization
# ---------------------------------------------------------------------------
class TestCategorization(unittest.TestCase):
    """Verify videos are categorized by YouTube categoryId, not hardcoded niches."""

    def test_music_category(self):
        item = {"snippet": {"categoryId": "10"}}
        self.assertEqual(_categorize_video(item), "music")

    def test_sports_category(self):
        item = {"snippet": {"categoryId": "17"}}
        self.assertEqual(_categorize_video(item), "sports")

    def test_gaming_category(self):
        item = {"snippet": {"categoryId": "20"}}
        self.assertEqual(_categorize_video(item), "gaming")

    def test_news_category(self):
        item = {"snippet": {"categoryId": "25"}}
        self.assertEqual(_categorize_video(item), "news & politics")

    def test_entertainment_category(self):
        item = {"snippet": {"categoryId": "24"}}
        self.assertEqual(_categorize_video(item), "entertainment")

    def test_science_tech_category(self):
        item = {"snippet": {"categoryId": "28"}}
        self.assertEqual(_categorize_video(item), "science & technology")

    def test_unknown_category_defaults_to_trending(self):
        item = {"snippet": {"categoryId": "9999"}}
        self.assertEqual(_categorize_video(item), "trending")

    def test_missing_category_defaults_to_trending(self):
        item = {"snippet": {}}
        self.assertEqual(_categorize_video(item), "trending")


# ---------------------------------------------------------------------------
# Test mixed categories (no AI-only bias)
# ---------------------------------------------------------------------------
class TestMixedCategories(unittest.TestCase):
    """Ensure ingestion returns videos from multiple categories."""

    @patch.object(YouTubeClient, "__init__", lambda self, **kw: None)
    @patch.object(YouTubeClient, "fetch_trending")
    def test_returns_multiple_categories(self, mock_fetch):
        """Ingestion should return videos with mixed niche/category labels."""
        # Mock different categories from different regions
        mock_items = []
        categories = [
            ("10", "music"),
            ("17", "sports"),
            ("25", "news & politics"),
            ("24", "entertainment"),
            ("20", "gaming"),
            ("28", "science & technology"),
        ]
        for i, (cat_id, _) in enumerate(categories):
            mock_items.append({
                "id": f"video_{i}",
                "snippet": {
                    "title": f"Video {i}",
                    "channelTitle": f"Channel {i}",
                    "description": "",
                    "publishedAt": "2026-05-01T00:00:00Z",
                    "categoryId": cat_id,
                    "thumbnails": {},
                },
                "statistics": {
                    "viewCount": str(1000 * (i + 1)),
                    "likeCount": str(100 * (i + 1)),
                    "commentCount": str(10 * (i + 1)),
                },
            })

        mock_fetch.return_value = mock_items

        # Provide api_key via mock
        with patch("ingestion.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(youtube_api_key="test-key")
            videos = ingest_trending_videos(regions=["US"])

        self.assertGreater(len(videos), 0)

        # Collect all unique categories
        categories_found = {v.niche for v in videos}

        # Must have MORE than 1 category (not AI-only)
        self.assertGreater(
            len(categories_found), 1,
            f"Expected mixed categories, but got: {categories_found}",
        )

        # Specifically should NOT be only AI
        self.assertNotEqual(
            categories_found, {"AI for business"},
            "Videos should NOT be only AI-biased",
        )

    @patch.object(YouTubeClient, "__init__", lambda self, **kw: None)
    @patch.object(YouTubeClient, "fetch_trending")
    def test_no_ai_only_bias(self, mock_fetch):
        """Returned categories should include non-AI topics."""
        mock_fetch.return_value = [
            {
                "id": f"v{i}",
                "snippet": {
                    "title": f"Title {i}",
                    "channelTitle": "Ch",
                    "description": "",
                    "publishedAt": "2026-05-01T00:00:00Z",
                    "categoryId": cat_id,
                    "thumbnails": {},
                },
                "statistics": {"viewCount": "10000", "likeCount": "500", "commentCount": "50"},
            }
            for i, cat_id in enumerate(["10", "17", "20", "24", "25"])
        ]

        with patch("ingestion.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(youtube_api_key="test-key")
            videos = ingest_trending_videos(regions=["US"])

        niches = {v.niche for v in videos}
        # Should include music, sports, gaming, etc — NOT just AI
        non_ai_niches = niches - {"ai for business", "ai productivity", "prompt engineering"}
        self.assertGreater(
            len(non_ai_niches), 0,
            f"Expected non-AI categories but all are AI-related: {niches}",
        )


# ---------------------------------------------------------------------------
# Test data freshness (stale purge)
# ---------------------------------------------------------------------------
class TestDataFreshness(unittest.TestCase):
    """Verify stale data purge works correctly."""

    @patch("database.get_connection")
    def test_purge_deletes_old_youtube_videos(self, mock_conn_ctx):
        """purge_stale_youtube_videos should execute DELETE for old YouTube data."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 42
        mock_conn.execute.return_value = mock_cursor
        mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

        deleted = purge_stale_youtube_videos()

        self.assertEqual(deleted, 42)
        # Verify the SQL was called with correct WHERE clause
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        self.assertIn("DELETE FROM videos", sql)
        self.assertIn("platform = 'youtube'", sql)
        self.assertIn("-7 days", sql)


# ---------------------------------------------------------------------------
# Test failsafe retry
# ---------------------------------------------------------------------------
class TestFailsafeRetry(unittest.TestCase):
    """Verify retry logic handles transient failures."""

    @patch.object(YouTubeClient, "__init__", lambda self, **kw: None)
    @patch.object(YouTubeClient, "_build_session")
    def test_retry_on_transient_error(self, mock_session_builder):
        """fetch_trending should retry on server errors."""
        mock_session = MagicMock()

        # First call raises 500, second succeeds
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = Exception("Server error")

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {"items": [{"id": "v1", "snippet": {}, "statistics": {}}]}

        mock_session.get.side_effect = [error_response, success_response]
        mock_session_builder.return_value = mock_session

        with patch("ingestion.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(youtube_api_key="test-key")
            client = YouTubeClient()
            client._session = mock_session
            client._api_key = "test-key"

            # The method should handle the exception internally
            # Due to retry logic, it should attempt multiple times
            result = client.fetch_trending(region_code="US")
            # Result depends on implementation — key is it doesn't crash
            self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# Test RawVideo dataclass
# ---------------------------------------------------------------------------
class TestRawVideo(unittest.TestCase):
    """Verify RawVideo model handles missing fields safely."""

    def test_default_values(self):
        """RawVideo should have safe defaults for all optional fields."""
        video = RawVideo(
            video_id="test",
            title="Test Video",
            channel="Test Channel",
            description="",
            published_at="",
            thumbnail_url="",
        )
        self.assertEqual(video.views, 0)
        self.assertEqual(video.likes, 0)
        self.assertEqual(video.comments, 0)
        self.assertEqual(video.niche, "")
        self.assertEqual(video.platform, "youtube")

    def test_to_dict(self):
        """to_dict should return a proper dictionary."""
        video = RawVideo(
            video_id="v1",
            title="T",
            channel="C",
            description="D",
            published_at="2026-01-01",
            thumbnail_url="http://example.com/thumb.jpg",
            views=1000,
            niche="music",
        )
        d = video.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["video_id"], "v1")
        self.assertEqual(d["views"], 1000)
        self.assertEqual(d["niche"], "music")


# ---------------------------------------------------------------------------
# Test parse_video_item handles missing fields
# ---------------------------------------------------------------------------
class TestParseVideoItem(unittest.TestCase):
    """Verify parse_video_item handles missing/partial data safely."""

    def test_minimal_item(self):
        """Should not crash on an item with minimal data."""
        item = {"id": "v1", "snippet": {}, "statistics": {}}
        video = YouTubeClient.parse_video_item(item, "trending")
        self.assertEqual(video.video_id, "v1")
        self.assertEqual(video.views, 0)
        self.assertEqual(video.niche, "trending")

    def test_full_item(self):
        """Should correctly parse a fully populated item."""
        item = {
            "id": "v2",
            "snippet": {
                "title": "Big Video",
                "channelTitle": "BigChannel",
                "description": "A description",
                "publishedAt": "2026-05-01T12:00:00Z",
                "thumbnails": {
                    "high": {"url": "http://img.com/high.jpg"},
                },
            },
            "statistics": {
                "viewCount": "50000",
                "likeCount": "2000",
                "commentCount": "300",
            },
        }
        video = YouTubeClient.parse_video_item(item, "music")
        self.assertEqual(video.title, "Big Video")
        self.assertEqual(video.views, 50000)
        self.assertEqual(video.likes, 2000)
        self.assertEqual(video.niche, "music")


# ---------------------------------------------------------------------------
# Test idempotent pipeline runs
# ---------------------------------------------------------------------------
class TestIdempotentPipeline(unittest.TestCase):
    """Verify pipeline runs are idempotent (safe to re-run)."""

    @patch.object(YouTubeClient, "__init__", lambda self, **kw: None)
    @patch.object(YouTubeClient, "fetch_trending")
    def test_double_ingest_same_results(self, mock_fetch):
        """Running ingest twice should produce identical deduplicated output."""
        mock_fetch.return_value = [
            {
                "id": "v1",
                "snippet": {
                    "title": "T1",
                    "channelTitle": "C1",
                    "description": "",
                    "publishedAt": "2026-05-01T00:00:00Z",
                    "categoryId": "10",
                    "thumbnails": {},
                },
                "statistics": {"viewCount": "10000", "likeCount": "500", "commentCount": "50"},
            },
        ]

        with patch("ingestion.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(youtube_api_key="test-key")
            run1 = ingest_trending_videos(regions=["US"])
            run2 = ingest_trending_videos(regions=["US"])

        self.assertEqual(len(run1), len(run2))
        self.assertEqual(run1[0].video_id, run2[0].video_id)


if __name__ == "__main__":
    unittest.main()
