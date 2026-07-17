from __future__ import annotations

import logging
from types import SimpleNamespace

from connectors.models import ConnectorMetrics, NormalizedContent
from connectors.reddit_connector import RedditConnector
from connectors.registry import ConnectorRegistry
from core import config


def test_normalized_content_preserves_platform_data_for_the_legacy_pipeline() -> None:
    item = NormalizedContent(
        id="reddit_123",
        platform="reddit",
        title="Useful discussion",
        author_name="example-user",
        source_url="https://reddit.example/post/123",
        platform_metadata={"subreddit": "technology"},
    )

    raw_video = item.to_raw_video()

    assert raw_video["video_id"] == "reddit_123"
    assert raw_video["platform"] == "reddit"
    assert raw_video["source_url"] == "https://reddit.example/post/123"
    assert raw_video["platform_metadata"]["subreddit"] == "technology"


def test_registry_reports_unconfigured_connectors_as_disabled(monkeypatch) -> None:
    ConnectorRegistry.reset_singleton()
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            youtube_api_key="",
            reddit_enabled=False,
            tiktok_enabled=False,
            instagram_enabled=False,
            apify_api_token="",
        ),
    )

    health = ConnectorRegistry().health_check_all()

    assert set(health) == {"youtube", "reddit", "tiktok", "instagram"}
    assert {item.status for item in health.values()} == {"disabled"}
    ConnectorRegistry.reset_singleton()


def test_reddit_connector_uses_multiple_query_variants_without_duplicate_posts() -> None:
    connector = object.__new__(RedditConnector)
    connector._max_results = 10
    connector._metrics = ConnectorMetrics(platform="reddit")
    connector._logger = logging.getLogger("test.reddit")
    calls = []

    def fake_run_actor(actor_input):
        calls.append(actor_input["searchQuery"])
        return [
            {
                "id": actor_input["searchQuery"].replace(" ", "-"),
                "title": actor_input["searchQuery"],
                "subreddit": "technology",
                "score": 10,
            },
            {"id": "shared", "title": "Shared post", "subreddit": "technology", "score": 5},
        ]

    connector.run_actor_sync = fake_run_actor
    items = connector.fetch_by_keywords(["ai automation", "artificial intelligence"], limit=10)

    assert calls == ["ai automation", "artificial intelligence"]
    assert {item.id for item in items} == {"reddit_ai-automation", "reddit_artificial-intelligence", "reddit_shared"}
