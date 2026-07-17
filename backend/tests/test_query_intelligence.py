from __future__ import annotations

from types import SimpleNamespace

from pipeline.ingestion import PipelineConfig
from pipeline.runner import _platform_keywords
from services.query_intelligence import QueryIntelligenceEngine


def test_query_intelligence_creates_plain_youtube_and_reddit_variants() -> None:
    context = QueryIntelligenceEngine().expand("AI automation")

    assert context.youtube_variants[0] == "ai automation"
    assert context.reddit_variants[0] == "ai automation"
    assert all(not term.startswith("#") for term in context.youtube_variants)
    assert all(not term.startswith("#") for term in context.reddit_variants)
    assert context.tiktok_variants
    assert context.instagram_variants


def test_runner_uses_platform_specific_keywords(monkeypatch) -> None:
    monkeypatch.setattr(
        "pipeline.runner.get_settings",
        lambda: SimpleNamespace(query_max_synonyms=5, query_max_hashtag_variants=8),
    )
    config = PipelineConfig(keywords=["AI automation"])

    youtube_terms = _platform_keywords(config, "youtube")
    reddit_terms = _platform_keywords(config, "reddit")

    assert youtube_terms[0] == "ai automation"
    assert reddit_terms[0] == "ai automation"
    assert all(not term.startswith("#") for term in youtube_terms + reddit_terms)
