"""
Content Relevance Scoring Engine for the Content Intelligence Platform.

Scores every piece of ingested content against the user's query context
to determine how relevant it is to the original search intent.

Scoring factors (positive):
    - Exact keyword in caption/title
    - Exact hashtag match
    - Partial phrase match
    - Synonym match
    - Hook relevance
    - Audio relevance (TikTok)
    - Engagement rate boost
    - Recency boost
    - Velocity boost

Negative scoring:
    - Unrelated hashtags dominant
    - Language mismatch indicators
    - Low metadata quality
    - Spam caption indicators

Usage:
    from analytics.relevance_engine import ContentRelevanceEngine
    from services.query_intelligence import QueryIntelligenceEngine

    qi = QueryIntelligenceEngine()
    ctx = qi.expand("cutekid")

    engine = ContentRelevanceEngine(threshold=55)
    result = engine.score(content_dict, ctx)
    # result.score          → 82
    # result.passed         → True
    # result.matched_keywords → ["cute kid"]
    # result.matched_hashtags → ["#cutekid"]
    # result.match_reason   → "Exact keyword in caption"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Relevance Result
# ---------------------------------------------------------------------------
@dataclass
class RelevanceResult:
    """Result of relevance scoring for a single piece of content."""

    score: int = 0                               # 0–100
    passed: bool = False                         # Above threshold
    matched_keywords: List[str] = field(default_factory=list)
    matched_hashtags: List[str] = field(default_factory=list)
    match_reason: str = ""                       # Human-readable explanation
    score_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relevance_score": self.score,
            "relevance_passed": self.passed,
            "matched_keywords": self.matched_keywords,
            "matched_hashtags": self.matched_hashtags,
            "match_reason": self.match_reason,
        }


# ---------------------------------------------------------------------------
# Scoring Weights
# ---------------------------------------------------------------------------
_POSITIVE_WEIGHTS = {
    "exact_keyword_title":   25,
    "exact_keyword_caption": 20,
    "exact_hashtag":         20,
    "partial_phrase":        15,
    "synonym_match":         10,
    "hook_relevance":         8,
    "audio_relevance":        7,
    "engagement_boost":       5,
    "recency_boost":          5,
    "velocity_boost":         5,
}

_NEGATIVE_WEIGHTS = {
    "unrelated_hashtags":   -10,
    "low_metadata":          -5,
    "spam_indicators":      -10,
}

# Spam indicators in captions
_SPAM_PATTERNS = [
    re.compile(r"follow\s*(for|4)\s*follow", re.IGNORECASE),
    re.compile(r"(f4f|l4l|s4s)\b", re.IGNORECASE),
    re.compile(r"link\s*in\s*bio", re.IGNORECASE),
    re.compile(r"dm\s*(me|for|to)\s*(collab|promo)", re.IGNORECASE),
    re.compile(r"free\s*followers", re.IGNORECASE),
    re.compile(r"(onlyfans|cashapp|telegram\s*group)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Content Relevance Engine
# ---------------------------------------------------------------------------
class ContentRelevanceEngine:
    """
    Scores content relevance against a QueryContext.

    Operates on content dicts (from NormalizedContent.to_raw_video()
    or plain dicts with standard keys).  Pure CPU — no network calls.
    """

    def __init__(self, threshold: int = 55) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> int:
        return self._threshold

    # ── Public API ──────────────────────────────────────────────────────────

    def score(
        self,
        content: Dict[str, Any],
        query_context: Any,  # QueryContext from services.query_intelligence
    ) -> RelevanceResult:
        """
        Score a single content item against the query context.

        Args:
            content:       Dict with keys: title, description, hashtags,
                           hook_text, audio_name, engagement_rate,
                           published_at, trend_velocity, views, likes, etc.
            query_context: QueryContext from QueryIntelligenceEngine.expand()

        Returns:
            RelevanceResult with score, matched terms, and pass/fail.
        """
        result = RelevanceResult()
        breakdown: Dict[str, int] = {}

        # Extract text fields
        title = (content.get("title", "") or "").lower()
        description = (content.get("description", "") or "").lower()
        caption = f"{title} {description}"
        hook_text = (content.get("hook_text", "") or "").lower()
        audio_name = (content.get("audio_name", "") or "").lower()

        # Extract hashtags (handle both list and JSON string)
        hashtags_raw = content.get("hashtags", [])
        if isinstance(hashtags_raw, str):
            try:
                import json
                hashtags_raw = json.loads(hashtags_raw)
            except (ValueError, TypeError):
                hashtags_raw = re.findall(r"#?(\w+)", hashtags_raw)
        content_hashtags = [
            h.lower().lstrip("#") for h in (hashtags_raw or []) if h
        ]

        # Get query terms
        original_kw = getattr(query_context, "original_keyword", "").lower()
        required = [t.lower() for t in getattr(query_context, "required_terms", [])]
        soft = [t.lower() for t in getattr(query_context, "soft_terms", [])]
        synonyms = [t.lower() for t in getattr(query_context, "synonyms", [])]
        all_positive = [t.lower() for t in getattr(query_context, "all_positive_terms", [])]

        # ── Positive scoring ──

        # 1. Exact keyword in title
        if original_kw and original_kw in title:
            pts = _POSITIVE_WEIGHTS["exact_keyword_title"]
            breakdown["exact_keyword_title"] = pts
            result.matched_keywords.append(original_kw)

        # Also check normalized terms in title
        for term in required:
            if term in title and term not in result.matched_keywords:
                pts = _POSITIVE_WEIGHTS["exact_keyword_title"]
                breakdown["exact_keyword_title"] = breakdown.get("exact_keyword_title", 0) + pts
                result.matched_keywords.append(term)
                break  # Only count once

        # 2. Exact keyword in caption/description
        if original_kw and original_kw in description and "exact_keyword_title" not in breakdown:
            pts = _POSITIVE_WEIGHTS["exact_keyword_caption"]
            breakdown["exact_keyword_caption"] = pts
            if original_kw not in result.matched_keywords:
                result.matched_keywords.append(original_kw)

        for term in required:
            if term in description and term not in result.matched_keywords:
                pts = _POSITIVE_WEIGHTS["exact_keyword_caption"]
                breakdown["exact_keyword_caption"] = breakdown.get("exact_keyword_caption", 0) + pts
                result.matched_keywords.append(term)
                break

        # 3. Exact hashtag match
        query_hashtags_raw = getattr(query_context, "instagram_variants", [])
        query_hashtags = {
            h.lower().lstrip("#") for h in query_hashtags_raw if h
        }
        # Also add normalized terms as potential hashtag matches
        for term in required + [original_kw]:
            if term:
                query_hashtags.add(term.replace(" ", ""))

        matched_ht = set(content_hashtags) & query_hashtags
        if matched_ht:
            pts = _POSITIVE_WEIGHTS["exact_hashtag"]
            breakdown["exact_hashtag"] = pts
            result.matched_hashtags.extend(f"#{h}" for h in matched_ht)

        # 4. Partial phrase match
        partial_matched = False
        for term in all_positive:
            if len(term) >= 3 and term in caption:
                if term not in result.matched_keywords:
                    pts = _POSITIVE_WEIGHTS["partial_phrase"]
                    breakdown["partial_phrase"] = breakdown.get("partial_phrase", 0) + pts
                    result.matched_keywords.append(term)
                    partial_matched = True
                    if len(result.matched_keywords) >= 5:
                        break

        # 5. Synonym match (only if no direct matches yet)
        if not result.matched_keywords:
            for syn in synonyms:
                if len(syn) >= 3 and syn in caption:
                    pts = _POSITIVE_WEIGHTS["synonym_match"]
                    breakdown["synonym_match"] = breakdown.get("synonym_match", 0) + pts
                    result.matched_keywords.append(f"~{syn}")
                    break

        # 6. Hook relevance
        if hook_text:
            for term in all_positive[:5]:
                if len(term) >= 3 and term in hook_text:
                    breakdown["hook_relevance"] = _POSITIVE_WEIGHTS["hook_relevance"]
                    break

        # 7. Audio relevance (TikTok sounds)
        if audio_name:
            for term in all_positive[:5]:
                if len(term) >= 3 and term in audio_name:
                    breakdown["audio_relevance"] = _POSITIVE_WEIGHTS["audio_relevance"]
                    break

        # 8. Engagement rate boost
        engagement = float(content.get("engagement_rate", 0) or 0)
        if engagement > 0.05:
            breakdown["engagement_boost"] = _POSITIVE_WEIGHTS["engagement_boost"]
        elif engagement > 0.03:
            breakdown["engagement_boost"] = _POSITIVE_WEIGHTS["engagement_boost"] // 2

        # 9. Recency boost
        published = content.get("published_at", "")
        if published:
            try:
                pub_dt = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                )
                age_hours = (
                    datetime.now(timezone.utc) - pub_dt
                ).total_seconds() / 3600
                if age_hours < 168:  # Less than 7 days
                    breakdown["recency_boost"] = _POSITIVE_WEIGHTS["recency_boost"]
                elif age_hours < 720:  # Less than 30 days
                    breakdown["recency_boost"] = _POSITIVE_WEIGHTS["recency_boost"] // 2
            except (ValueError, TypeError):
                pass

        # 10. Velocity boost
        velocity = float(content.get("trend_velocity", 0) or 0)
        if velocity > 0.001:
            breakdown["velocity_boost"] = _POSITIVE_WEIGHTS["velocity_boost"]

        # ── Negative scoring ──

        # 1. Unrelated hashtags dominate
        if content_hashtags and query_hashtags:
            overlap_ratio = len(matched_ht) / max(len(content_hashtags), 1)
            if overlap_ratio < 0.1 and len(content_hashtags) > 5:
                breakdown["unrelated_hashtags"] = _NEGATIVE_WEIGHTS["unrelated_hashtags"]

        # 2. Low metadata quality
        if not description and not content_hashtags and not title:
            breakdown["low_metadata"] = _NEGATIVE_WEIGHTS["low_metadata"]

        # 3. Spam indicators
        for pattern in _SPAM_PATTERNS:
            if pattern.search(caption):
                breakdown["spam_indicators"] = _NEGATIVE_WEIGHTS["spam_indicators"]
                break

        # ── Final score ──
        raw_score = sum(breakdown.values())
        # Clamp to 0–100
        final_score = max(0, min(100, raw_score))

        # Build match reason
        reasons = []
        if "exact_keyword_title" in breakdown:
            reasons.append("Keyword in title")
        if "exact_keyword_caption" in breakdown:
            reasons.append("Keyword in caption")
        if "exact_hashtag" in breakdown:
            reasons.append("Hashtag match")
        if "partial_phrase" in breakdown:
            reasons.append("Phrase match")
        if "synonym_match" in breakdown:
            reasons.append("Synonym match")
        if "hook_relevance" in breakdown:
            reasons.append("Hook match")
        if "audio_relevance" in breakdown:
            reasons.append("Audio match")

        result.score = final_score
        result.passed = final_score >= self._threshold
        result.match_reason = " · ".join(reasons) if reasons else "Low relevance"
        result.score_breakdown = breakdown

        return result


