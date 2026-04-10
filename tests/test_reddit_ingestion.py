"""
Unit tests for Reddit ingestion module.

Tests RedditClient and ingest_reddit_posts with mocked API responses.
"""

import pytest
from unittest.mock import patch, MagicMock
from reddit_ingestion import RedditClient, RawVideo, ingest_reddit_posts


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
MOCK_OAUTH_RESPONSE = {"access_token": "test_token_123", "token_type": "bearer"}

MOCK_SEARCH_RESPONSE = {
    "data": {
        "children": [
            {
                "data": {
                    "id": "abc123",
                    "title": "Best AI tools for business in 2024",
                    "subreddit": "artificial",
                    "selftext": "Here are the top AI tools I've found for business...",
                    "score": 1500,
                    "ups": 1500,
                    "num_comments": 234,
                    "created_utc": 1700000000,
                    "thumbnail": "https://preview.redd.it/example.jpg",
                    "is_self": True,
                    "promoted": False,
                    "preview": {
                        "images": [
                            {"source": {"url": "https://preview.redd.it/full.jpg"}}
                        ]
                    },
                }
            },
            {
                "data": {
                    "id": "def456",
                    "title": "How I automated my workflow with AI",
                    "subreddit": "productivity",
                    "selftext": "Sharing my experience...",
                    "score": 800,
                    "ups": 800,
                    "num_comments": 120,
                    "created_utc": 1700100000,
                    "thumbnail": "self",
                    "is_self": True,
                    "promoted": False,
                }
            },
        ],
        "after": None,
    }
}

MOCK_EMPTY_RESPONSE = {"data": {"children": [], "after": None}}


# ---------------------------------------------------------------------------
# RedditClient.parse_post
# ---------------------------------------------------------------------------
class TestParsePost:
    """Tests for RedditClient.parse_post static method."""

    def test_parse_basic_post(self):
        """Should correctly parse a standard Reddit post into RawVideo."""
        post = MOCK_SEARCH_RESPONSE["data"]["children"][0]["data"]
        result = RedditClient.parse_post(post, "AI for business")

        assert isinstance(result, RawVideo)
        assert result.video_id == "reddit_abc123"
        assert result.title == "Best AI tools for business in 2024"
        assert result.channel == "r/artificial"
        assert result.views == 1500
        assert result.likes == 1500
        assert result.comments == 234
        assert result.niche == "AI for business"
        assert result.platform == "reddit"
        assert "2023" in result.published_at  # 1700000000 is in Nov 2023

    def test_parse_post_with_preview_thumbnail(self):
        """Should extract thumbnail from preview when thumbnail is 'self'."""
        post = MOCK_SEARCH_RESPONSE["data"]["children"][1]["data"]
        result = RedditClient.parse_post(post, "AI productivity")

        assert result.thumbnail_url == ""  # 'self' thumbnail with no preview
        assert result.video_id == "reddit_def456"
        assert result.channel == "r/productivity"

    def test_parse_post_negative_score(self):
        """Should handle negative scores by clamping to 0."""
        post = {
            "id": "neg1",
            "title": "Unpopular opinion",
            "subreddit": "test",
            "selftext": "",
            "score": -5,
            "ups": -5,
            "num_comments": 3,
            "created_utc": 1700000000,
            "thumbnail": "default",
            "is_self": True,
        }
        result = RedditClient.parse_post(post, "test")
        assert result.views == 0
        assert result.likes == 0

    def test_parse_post_long_description(self):
        """Should truncate long descriptions to 2000 chars."""
        post = {
            "id": "long1",
            "title": "Long post",
            "subreddit": "test",
            "selftext": "A" * 5000,
            "score": 100,
            "ups": 100,
            "num_comments": 10,
            "created_utc": 1700000000,
            "thumbnail": "self",
            "is_self": True,
        }
        result = RedditClient.parse_post(post, "test")
        assert len(result.description) == 2000


# ---------------------------------------------------------------------------
# ingest_reddit_posts
# ---------------------------------------------------------------------------
class TestIngestRedditPosts:
    """Tests for the ingest_reddit_posts high-level function."""

    @patch("reddit_ingestion.get_settings")
    def test_skips_when_no_credentials(self, mock_settings):
        """Should silently return empty list when Reddit credentials are missing."""
        mock_settings.return_value.reddit_client_id = ""
        mock_settings.return_value.reddit_client_secret = ""

        result = ingest_reddit_posts()
        assert result == []

    @patch("reddit_ingestion.RedditClient")
    @patch("reddit_ingestion.get_settings")
    def test_ingest_success(self, mock_settings, mock_client_class):
        """Should ingest posts from all configured niches."""
        mock_settings.return_value.reddit_client_id = "test_id"
        mock_settings.return_value.reddit_client_secret = "test_secret"
        mock_settings.return_value.reddit_user_agent = "Test/1.0"
        mock_settings.return_value.reddit_max_posts_per_query = 100
        mock_settings.return_value.niche_keywords = ["AI for business", "AI productivity"]

        # Mock client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        posts_data = [
            MOCK_SEARCH_RESPONSE["data"]["children"][0]["data"],
            MOCK_SEARCH_RESPONSE["data"]["children"][1]["data"],
        ]
        mock_client.search_posts.return_value = posts_data

        raw_video = RawVideo(
            video_id="reddit_abc123",
            title="Test",
            channel="r/test",
            description="desc",
            published_at="2023-11-14T22:13:20+00:00",
            thumbnail_url="",
            views=100,
            likes=100,
            comments=10,
            niche="AI for business",
            platform="reddit",
        )
        mock_client.parse_post.return_value = raw_video

        result = ingest_reddit_posts()

        # Should call search_posts for each niche
        assert mock_client.search_posts.call_count == 2
        # Should produce RawVideo objects
        assert len(result) > 0
        assert all(isinstance(r, RawVideo) for r in result)

    @patch("reddit_ingestion.RedditClient")
    @patch("reddit_ingestion.get_settings")
    def test_ingest_handles_api_errors(self, mock_settings, mock_client_class):
        """Should handle errors gracefully and continue with other niches."""
        mock_settings.return_value.reddit_client_id = "test_id"
        mock_settings.return_value.reddit_client_secret = "test_secret"
        mock_settings.return_value.reddit_user_agent = "Test/1.0"
        mock_settings.return_value.reddit_max_posts_per_query = 100
        mock_settings.return_value.niche_keywords = ["niche1", "niche2"]

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search_posts.side_effect = [
            Exception("API error"),
            [MOCK_SEARCH_RESPONSE["data"]["children"][0]["data"]],
        ]
        mock_client.parse_post.return_value = RawVideo(
            video_id="reddit_test",
            title="Test",
            channel="r/test",
            description="",
            published_at="",
            thumbnail_url="",
            views=0,
            likes=0,
            comments=0,
            niche="niche2",
            platform="reddit",
        )

        result = ingest_reddit_posts()
        # Should have results from niche2 but not niche1
        assert len(result) == 1
