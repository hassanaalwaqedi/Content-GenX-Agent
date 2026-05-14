"""
Tests for the Trend Discovery & Opportunity Engine.

Covers: topic parsing, clustering, scoring, opportunity calculation.
"""

import json
import math
import pytest

from trends import (
    _normalize_topic,
    _parse_topics,
    _topics_similar,
    build_trend_clusters,
    score_trend,
    compute_opportunity,
    discover_trends,
    discover_opportunities,
    generate_suggested_titles,
    invalidate_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_video(vid: str, topics: list, score=0.5, eng=0.04, views=10000, niche="ai", **kw):
    return {
        "video_id": vid,
        "title": kw.get("title", f"Test Video {vid}"),
        "channel": kw.get("channel", "TestChannel"),
        "niche": niche,
        "views": views,
        "likes": kw.get("likes", 500),
        "comments": kw.get("comments", 50),
        "engagement_rate": eng,
        "score": score,
        "topics": json.dumps(topics),
        "published_at": "2025-04-01T00:00:00",
        "thumbnail_url": "https://example.com/thumb.jpg",
        **{k: v for k, v in kw.items() if k not in ("title", "channel", "likes", "comments")},
    }


@pytest.fixture(autouse=True)
def clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


# ---------------------------------------------------------------------------
# Topic parsing
# ---------------------------------------------------------------------------
class TestTopicParsing:
    def test_parse_valid(self):
        assert _parse_topics('["ai automation", "startup"]') == ["ai automation", "startup"]

    def test_parse_empty(self):
        assert _parse_topics("") == []
        assert _parse_topics(None) == []

    def test_parse_invalid_json(self):
        assert _parse_topics("not json") == []

    def test_parse_non_list(self):
        assert _parse_topics('"single string"') == []

    def test_normalize(self):
        assert _normalize_topic("AI_Automation") == "ai automation"
        assert _normalize_topic("  hello   world  ") == "hello world"


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------
class TestSimilarity:
    def test_exact_match(self):
        assert _topics_similar("ai automation", "ai automation") is True

    def test_contains(self):
        assert _topics_similar("ai", "ai automation") is True

    def test_word_overlap(self):
        assert _topics_similar("ai automation tools", "ai automation apps") is True

    def test_no_match(self):
        assert _topics_similar("cooking recipes", "ai automation") is False


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
class TestClustering:
    def test_basic_clustering(self):
        videos = [
            _make_video("v1", ["ai automation", "startup"]),
            _make_video("v2", ["ai automation", "business"]),
            _make_video("v3", ["cooking"]),
        ]
        clusters = build_trend_clusters(videos)
        # "ai automation" should cluster v1 and v2
        ai_cluster = next((c for c in clusters if "ai automation" in c["trend"]), None)
        assert ai_cluster is not None
        assert ai_cluster["count"] >= 2

    def test_empty_input(self):
        assert build_trend_clusters([]) == []

    def test_niche_fallback(self):
        videos = [_make_video("v1", [], niche="tech")]
        clusters = build_trend_clusters(videos)
        assert len(clusters) == 1
        assert clusters[0]["trend"] == "tech"

    def test_no_duplicate_videos_in_cluster(self):
        videos = [
            _make_video("v1", ["ai automation", "ai automation"]),  # duplicate topic
        ]
        clusters = build_trend_clusters(videos)
        ai_cluster = next(c for c in clusters if "ai automation" in c["trend"])
        vid_ids = [v["video_id"] for v in ai_cluster["videos"]]
        assert len(vid_ids) == len(set(vid_ids))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
class TestScoring:
    def test_score_basic(self):
        cluster = {
            "trend": "ai automation",
            "videos": [
                _make_video("v1", [], score=0.8, eng=0.06, views=50000),
                _make_video("v2", [], score=0.6, eng=0.04, views=30000),
            ],
            "count": 2,
        }
        result = score_trend(cluster)
        assert 0 < result["trend_score"] <= 1
        assert result["avg_views"] > 0
        assert result["avg_score"] > 0
        assert result["avg_engagement"] > 0

    def test_score_empty(self):
        cluster = {"trend": "x", "videos": [], "count": 0}
        result = score_trend(cluster)
        assert result["trend_score"] == 0

    def test_higher_engagement_scores_higher(self):
        low = score_trend({
            "trend": "a", "count": 2,
            "videos": [_make_video("v1", [], eng=0.01), _make_video("v2", [], eng=0.01)],
        })
        high = score_trend({
            "trend": "b", "count": 2,
            "videos": [_make_video("v3", [], eng=0.10), _make_video("v4", [], eng=0.10)],
        })
        assert high["trend_score"] > low["trend_score"]


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------
class TestOpportunity:
    def test_opportunity_basic(self):
        cluster = score_trend({
            "trend": "new niche",
            "videos": [_make_video("v1", [], score=0.8, eng=0.08)],
            "count": 1,
        })
        result = compute_opportunity(cluster)
        assert 0 <= result["opportunity_score"] <= 1
        assert "low competition" in result["reasons"]

    def test_opportunity_high_competition(self):
        vids = [_make_video(f"v{i}", [], score=0.3, eng=0.02) for i in range(20)]
        cluster = score_trend({"trend": "saturated", "videos": vids, "count": 20})
        result = compute_opportunity(cluster)
        assert "low competition" not in result["reasons"]

    def test_opportunity_empty(self):
        result = compute_opportunity({"trend": "x", "videos": [], "count": 0})
        assert result["opportunity_score"] == 0


# ---------------------------------------------------------------------------
# Suggested Titles
# ---------------------------------------------------------------------------
class TestSuggestedTitles:
    def test_fallback_titles(self):
        cluster = {
            "trend": "ai automation",
            "videos": [_make_video("v1", [], title="How AI Changed My Life")],
        }
        titles = generate_suggested_titles(cluster, client=None)
        assert len(titles) == 3
        assert all(isinstance(t, str) for t in titles)
        assert any("Ai Automation" in t for t in titles)


# ---------------------------------------------------------------------------
# Integration (discover_trends / discover_opportunities)
# ---------------------------------------------------------------------------
class TestDiscovery:
    def test_discover_trends(self):
        videos = [
            _make_video("v1", ["ai agents"], score=0.7, eng=0.05),
            _make_video("v2", ["ai agents"], score=0.6, eng=0.04),
            _make_video("v3", ["cooking"], score=0.3, eng=0.02),
            _make_video("v4", ["cooking"], score=0.2, eng=0.01),
        ]
        trends = discover_trends(videos, min_count=2, limit=10)
        assert len(trends) >= 2
        assert trends[0]["trend_score"] >= trends[1]["trend_score"]

    def test_discover_opportunities(self):
        videos = [
            _make_video("v1", ["rare niche"], score=0.9, eng=0.10),
            _make_video("v2", ["common topic"], score=0.3, eng=0.02),
            _make_video("v3", ["common topic"], score=0.3, eng=0.02),
            _make_video("v4", ["common topic"], score=0.3, eng=0.02),
            _make_video("v5", ["common topic"], score=0.3, eng=0.02),
        ]
        opps = discover_opportunities(videos, min_count=1, limit=10)
        assert len(opps) >= 1
        # The rare niche with high score/engagement should rank first
        rare = next((o for o in opps if "rare niche" in o["trend"]), None)
        assert rare is not None
        assert rare["opportunity_score"] > 0

    def test_caching(self):
        videos = [
            _make_video("v1", ["test"], score=0.5),
            _make_video("v2", ["test"], score=0.5),
        ]
        r1 = discover_trends(videos, min_count=2, limit=5)
        r2 = discover_trends(videos, min_count=2, limit=5)
        assert r1 is r2  # Same object from cache
