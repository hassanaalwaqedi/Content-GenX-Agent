"""
Unit tests for AI enrichment module — JSON parsing, fallback, circuit breaker.

Run with: python -m pytest tests/test_enrichment.py -v
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_enrichment import (
    _extract_topics_rule_based,
    _apply_pending_defaults,
    _extract_strategic_insights,
    enrich_video,
    enrich_videos,
    GroqClient,
    _PENDING,
)


# ---------------------------------------------------------------------------
# Rule-Based Topic Extraction
# ---------------------------------------------------------------------------
class TestRuleBasedTopics:
    """Tests for keyword-based topic extraction."""

    def test_llm_keywords_detected(self):
        topics = _extract_topics_rule_based("How to use ChatGPT for business", "")
        assert "large_language_models" in topics
        assert "ai_business" in topics

    def test_prompt_engineering(self):
        topics = _extract_topics_rule_based("Chain of Thought Prompting", "few-shot")
        assert "prompt_engineering" in topics

    def test_no_match_returns_general(self):
        topics = _extract_topics_rule_based("Random Title", "No relevant keywords")
        assert topics == ["general_ai"]

    def test_multiple_topics(self):
        topics = _extract_topics_rule_based(
            "GPT Automation Tool for Business Efficiency", ""
        )
        assert "large_language_models" in topics
        assert "ai_automation" in topics

    def test_case_insensitive(self):
        topics = _extract_topics_rule_based("MACHINE LEARNING tutorial", "")
        assert "machine_learning" in topics


# ---------------------------------------------------------------------------
# Pending Defaults
# ---------------------------------------------------------------------------
class TestPendingDefaults:
    """Tests for _apply_pending_defaults()."""

    def test_fills_missing_fields(self):
        video = {"title": "Test", "description": "ChatGPT tips"}
        result = _apply_pending_defaults(video)
        assert result["target_audience"] == _PENDING
        assert result["strategic_advice"] == _PENDING
        assert result["content_gap"] == _PENDING
        assert "topics" in result

    def test_does_not_overwrite_existing(self):
        video = {
            "title": "Test",
            "description": "",
            "target_audience": "developers",
        }
        result = _apply_pending_defaults(video)
        assert result["target_audience"] == "developers"  # Not overwritten

    def test_topics_is_json_string(self):
        video = {"title": "GPT tutorial", "description": ""}
        result = _apply_pending_defaults(video)
        # Topics should be a JSON string, not a list
        parsed = json.loads(result["topics"])
        assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# Strategic Insight Extraction (mocked Groq)
# ---------------------------------------------------------------------------
class TestStrategicInsights:
    """Tests for _extract_strategic_insights() with mocked LLM."""

    def _make_mock_client(self, response_json: dict) -> GroqClient:
        """Create a GroqClient that returns a predefined JSON response."""
        client = MagicMock(spec=GroqClient)
        client.chat.return_value = json.dumps(response_json)
        return client

    def test_successful_extraction(self):
        mock_response = {
            "topics": ["ai_automation", "ai_business"],
            "category": "automation",
            "summary": "A video about AI automation.",
            "target_audience": "CTOs and tech leads",
            "strategic_advice": "1) Automate X. 2) Scale Y. 3) Monitor Z.",
            "content_gap": "Missing cost analysis.",
        }
        client = self._make_mock_client(mock_response)

        result = _extract_strategic_insights(client, "AI Automation Tips", "A video")
        assert result["target_audience"] == "CTOs and tech leads"
        assert "Automate X" in result["strategic_advice"]
        assert result["content_gap"] == "Missing cost analysis."

    def test_malformed_json_falls_back(self):
        client = MagicMock(spec=GroqClient)
        client.chat.return_value = "NOT VALID JSON {{{}"

        result = _extract_strategic_insights(client, "Test Title", "Description")
        assert result["target_audience"] == _PENDING
        assert result["strategic_advice"] == _PENDING

    def test_markdown_fences_stripped(self):
        mock_response = {
            "topics": ["nlp"],
            "category": "nlp",
            "summary": "NLP video.",
            "target_audience": "data scientists",
            "strategic_advice": "1) A. 2) B. 3) C.",
            "content_gap": "Missing deployment guide.",
        }
        client = MagicMock(spec=GroqClient)
        client.chat.return_value = f"```json\n{json.dumps(mock_response)}\n```"

        result = _extract_strategic_insights(client, "NLP Basics", "")
        assert result["target_audience"] == "data scientists"

    def test_topics_serialized_as_json(self):
        mock_response = {
            "topics": ["topic_a", "topic_b"],
            "category": "test",
            "summary": "Test.",
            "target_audience": "all",
            "strategic_advice": "1) A. 2) B. 3) C.",
            "content_gap": "None.",
        }
        client = self._make_mock_client(mock_response)

        result = _extract_strategic_insights(client, "Title", "Desc")
        # topics should be a JSON string, not a Python list
        assert isinstance(result["topics"], str)
        parsed = json.loads(result["topics"])
        assert parsed == ["topic_a", "topic_b"]


# ---------------------------------------------------------------------------
# Rate Limit & Retry
# ---------------------------------------------------------------------------
class TestRateLimitHandling:
    """Tests for 429 retry logic in enrich_video()."""

    def test_429_retry_with_backoff(self):
        """Should retry on 429 and succeed on second attempt."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "0.1"}

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "topics": ["ai"],
                "category": "ai",
                "summary": "Test",
                "target_audience": "devs",
                "strategic_advice": "1) A. 2) B. 3) C.",
                "content_gap": "None.",
            })}}]
        }

        client = GroqClient.__new__(GroqClient)
        client._session = MagicMock()
        client._session.post = MagicMock(
            side_effect=[mock_response_429, mock_response_ok]
        )
        # First call raises 429, second succeeds
        mock_response_429.raise_for_status.side_effect = requests.HTTPError(
            response=mock_response_429
        )
        mock_response_429.request = MagicMock()
        mock_response_429.request.headers = {}
        mock_response_ok.raise_for_status.return_value = None

        video = {"video_id": "v1", "title": "Test", "description": ""}
        result = enrich_video(video, client)
        assert result["target_audience"] == "devs"

    def test_all_retries_exhausted_falls_back(self):
        """After max retries on 429, should fall back to pending."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "0.1"}
        mock_response.request = MagicMock()
        mock_response.request.headers = {}

        exc = requests.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = exc

        client = GroqClient.__new__(GroqClient)
        client._session = MagicMock()
        client._session.post.return_value = mock_response

        video = {"video_id": "v1", "title": "Test", "description": ""}
        result = enrich_video(video, client)
        assert result["target_audience"] == _PENDING

    def test_non_429_error_falls_back(self):
        """A 500 error should immediately fall back to pending."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.request = MagicMock()
        mock_response.request.headers = {}

        exc = requests.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = exc

        client = GroqClient.__new__(GroqClient)
        client._session = MagicMock()
        client._session.post.return_value = mock_response

        video = {"video_id": "v1", "title": "Test", "description": ""}
        result = enrich_video(video, client)
        assert result["target_audience"] == _PENDING


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
class TestCircuitBreaker:
    """Tests for circuit breaker in enrich_videos()."""

    @patch("ai_enrichment.get_settings")
    @patch("ai_enrichment.GroqClient")
    def test_circuit_breaker_opens(self, MockGroqClient, mock_settings):
        """After 3 consecutive failures, remaining LLM calls should be skipped."""
        settings = MagicMock()
        settings.groq_api_key = "fake-key"
        mock_settings.return_value = settings

        # Create a client that always returns pending (simulating parse failures)
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API down")
        MockGroqClient.return_value = mock_client

        # Create 10 videos, all in same niche with high scores
        videos = [
            {
                "video_id": f"v{i}",
                "title": f"Video {i}",
                "description": "test",
                "niche": "test_niche",
                "score": 1.0 - (i * 0.01),
            }
            for i in range(10)
        ]

        result = enrich_videos(videos)
        assert len(result) == 10
        # All should have pending (circuit breaker should have opened)
        for v in result:
            assert v.get("target_audience") == _PENDING

    def test_no_groq_key_all_pending(self):
        """Without Groq API key, all videos should get pending."""
        with patch("ai_enrichment.get_settings") as mock_settings:
            settings = MagicMock()
            settings.groq_api_key = ""
            mock_settings.return_value = settings

            videos = [
                {"video_id": "v1", "title": "T", "description": "", "niche": "n", "score": 1.0},
            ]
            result = enrich_videos(videos)
            assert result[0]["target_audience"] == _PENDING


# ---------------------------------------------------------------------------
# API Key Redaction
# ---------------------------------------------------------------------------
class TestAPIKeyRedaction:
    """Tests for Bearer token stripping from error tracebacks."""

    def test_authorization_header_stripped(self):
        """HTTPError should not contain Authorization header."""
        client = GroqClient.__new__(GroqClient)
        client._session = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_request = MagicMock()
        mock_request.headers = {"Authorization": "Bearer secret_key_123"}
        mock_response.request = mock_request

        exc = requests.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = exc
        client._session.post.return_value = mock_response

        with pytest.raises(requests.HTTPError) as exc_info:
            client.chat([{"role": "user", "content": "test"}])

        # Authorization should have been stripped
        assert "Authorization" not in exc_info.value.request.headers
