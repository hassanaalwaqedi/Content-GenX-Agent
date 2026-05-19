"""
Hook Intelligence Engine for the Content Intelligence Platform.

Extracts and categorizes opening hooks from any short-form or
long-form content. Works across all platforms (YouTube, TikTok,
Instagram, Reddit) by operating on text descriptions/captions.

Hook Categories:
    - curiosity: Creates information gap
    - authority: Establishes credibility
    - fear: Triggers loss aversion
    - story: Personal narrative opener
    - contrarian: Challenges common belief
    - question: Direct audience question
    - educational: Teaches or explains
    - urgency: Time-sensitive appeal

Usage:
    analyzer = HookAnalyzer()
    analysis = analyzer.analyze_text("I can't believe this actually worked...")
    # analysis.hook_text = "I can't believe this actually worked"
    # analysis.hook_category = "curiosity"
    # analysis.confidence = 0.85
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from connectors.models import HookAnalysis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hook Category Patterns
# ---------------------------------------------------------------------------
# Each category has a list of (regex_pattern, weight) tuples.
# Higher weight = stronger signal for that category.
# Patterns are case-insensitive.

_HOOK_PATTERNS: Dict[str, List[Tuple[str, float]]] = {
    "curiosity": [
        (r"\b(you won'?t believe|can'?t believe|never knew)\b", 0.9),
        (r"\b(secret|hidden|unknown|revealed|shocking)\b", 0.8),
        (r"\b(nobody|no one) (talks?|knows?|told)\b", 0.85),
        (r"\b(what happens? (when|if|next))\b", 0.8),
        (r"\b(the truth about|real reason)\b", 0.85),
        (r"\b(finally|just discovered|found out)\b", 0.7),
        (r"\b(i tried|i tested|i spent)\b", 0.6),
        (r"\b(here'?s? (what|why|how))\b", 0.6),
        (r"\b(wait (for|till|until))\b", 0.7),
    ],
    "authority": [
        (r"\b(as a|i'?m a) (ceo|founder|doctor|expert|engineer|scientist)\b", 0.9),
        (r"\b(\d+) years? (of experience|in (the )?industry)\b", 0.85),
        (r"\b(according to|research shows?|studies? (show|prove))\b", 0.8),
        (r"\b(harvard|stanford|mit|google|microsoft|meta)\b", 0.75),
        (r"\b(proven|data.driven|evidence.based)\b", 0.7),
        (r"\b(after (working|building|running))\b", 0.65),
        (r"\b(in my experience|from my)\b", 0.6),
    ],
    "fear": [
        (r"\b(stop|don'?t|never|avoid|warning|danger|mistake)\b", 0.8),
        (r"\b(worst|terrible|horrible|nightmare|disaster)\b", 0.75),
        (r"\b(ruining|destroying|killing|dying)\b", 0.8),
        (r"\b(before it'?s too late|running out of)\b", 0.85),
        (r"\b(you'?re (losing|missing|wasting))\b", 0.8),
        (r"\b(scam|fraud|fake|lie|lies)\b", 0.75),
        (r"\b(be careful|watch out|beware)\b", 0.7),
    ],
    "story": [
        (r"^(i|we|my|when i|last (week|month|year))\b", 0.7),
        (r"\b(story time|let me tell you|true story)\b", 0.9),
        (r"\b(happened to me|i remember when)\b", 0.85),
        (r"\b(one day|so basically|it all started)\b", 0.75),
        (r"\b(plot twist|you'?ll never guess)\b", 0.8),
        (r"\b(this (changed|transformed|ruined) my)\b", 0.75),
    ],
    "contrarian": [
        (r"\b(unpopular opinion|hot take|controversial)\b", 0.9),
        (r"\b(everyone is wrong|they'?re lying|myth)\b", 0.85),
        (r"\b(overrated|overhyped|actually (bad|wrong|worse))\b", 0.8),
        (r"\b(stop (saying|doing|believing))\b", 0.8),
        (r"\b(the problem with|what'?s wrong with)\b", 0.7),
        (r"\b(but actually|in reality|the real)\b", 0.6),
    ],
    "question": [
        (r"^(what|why|how|when|where|who|which|do you|have you|are you|is it|can you|should)\b", 0.85),
        (r"\?$", 0.7),
        (r"\b(ever wonder|did you know|have you ever)\b", 0.8),
        (r"\b(what if|imagine if|would you)\b", 0.75),
    ],
    "educational": [
        (r"\b(\d+) (tips?|tricks?|ways?|steps?|hacks?|methods?|lessons?|things?)\b", 0.9),
        (r"\b(how to|guide|tutorial|explained|for beginners)\b", 0.85),
        (r"\b(ultimate|complete|definitive) guide\b", 0.8),
        (r"\b(learn|master|understand|intro(duction)? to)\b", 0.7),
        (r"\b(everything you need|all you need)\b", 0.75),
        (r"\b(cheat sheet|roadmap|framework)\b", 0.7),
    ],
    "urgency": [
        (r"\b(right now|today|immediately|asap|hurry)\b", 0.85),
        (r"\b(limited time|last chance|ending soon|almost over)\b", 0.9),
        (r"\b(don'?t miss|don'?t wait|act (now|fast))\b", 0.85),
        (r"\b(before (it'?s|they|you))\b", 0.7),
        (r"\b(breaking|just (in|announced|dropped|released))\b", 0.8),
        (r"\b(update|new|latest|fresh)\b", 0.5),
    ],
}


# ---------------------------------------------------------------------------
# Hook Analyzer
# ---------------------------------------------------------------------------
class HookAnalyzer:
    """
    Extract and categorize content hooks from any platform.

    Uses pattern matching (regex + keyword lists) for fast,
    deterministic categorization. No LLM needed.
    """

    def __init__(self) -> None:
        # Pre-compile all patterns for performance
        self._compiled_patterns: Dict[str, List[Tuple[re.Pattern, float]]] = {}
        for category, patterns in _HOOK_PATTERNS.items():
            self._compiled_patterns[category] = [
                (re.compile(pattern, re.IGNORECASE), weight)
                for pattern, weight in patterns
            ]

    def extract_hook(self, text: str) -> str:
        """
        Extract the opening hook from a text body.

        Strategy:
        1. Take the first sentence (up to first . ! ? or newline)
        2. If first sentence is too short (<10 chars), take first 2 sentences
        3. Cap at 200 characters
        """
        if not text or not text.strip():
            return ""

        # Clean up whitespace and newlines
        cleaned = text.strip()
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+|\n", cleaned)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return cleaned[:200]

        hook = sentences[0]

        # If first sentence is too short, add the second
        if len(hook) < 10 and len(sentences) > 1:
            hook = f"{hook} {sentences[1]}"

        # Cap length
        if len(hook) > 200:
            hook = hook[:197] + "..."

        return hook

    def categorize_hook(self, hook: str) -> Tuple[str, float]:
        """
        Categorize a hook into one of the defined categories.

        Returns (category, confidence) tuple.
        Confidence is the highest matching pattern weight.
        """
        if not hook:
            return ("", 0.0)

        best_category = ""
        best_confidence = 0.0
        category_scores: Dict[str, float] = {}

        for category, patterns in self._compiled_patterns.items():
            max_weight = 0.0
            match_count = 0

            for compiled_pattern, weight in patterns:
                if compiled_pattern.search(hook):
                    match_count += 1
                    max_weight = max(max_weight, weight)

            if match_count > 0:
                # Boost confidence if multiple patterns match
                boost = min(match_count * 0.05, 0.15)
                score = min(max_weight + boost, 1.0)
                category_scores[category] = score

                if score > best_confidence:
                    best_confidence = score
                    best_category = category

        return (best_category, round(best_confidence, 2))

    def analyze_text(self, text: str) -> HookAnalysis:
        """
        Full hook analysis: extract + categorize.

        Args:
            text: Full caption, description, or title text.

        Returns:
            HookAnalysis with hook_text, hook_category, and confidence.
        """
        hook = self.extract_hook(text)
        category, confidence = self.categorize_hook(hook)

        return HookAnalysis(
            hook_text=hook,
            hook_category=category,
            confidence=confidence,
        )

    def analyze_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a content dict and add hook fields.

        Uses description for primary analysis, falls back to title.
        Modifies the dict in-place and returns it.
        """
        # Prefer description (full caption), fall back to title
        text = content.get("description", "") or content.get("title", "")

        if text:
            analysis = self.analyze_text(text)
            content["hook_text"] = analysis.hook_text
            content["hook_category"] = analysis.hook_category
        else:
            content.setdefault("hook_text", "")
            content.setdefault("hook_category", "")

        return content

    def analyze_batch(
        self, contents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze a batch of content dicts. Returns the modified list."""
        analyzed = 0
        for content in contents:
            try:
                self.analyze_content(content)
                analyzed += 1
            except Exception as exc:
                logger.warning(
                    "Hook analysis failed for %s: %s",
                    content.get("id", content.get("video_id", "?")),
                    exc,
                )

        # Log category distribution
        categories: Dict[str, int] = {}
        for c in contents:
            cat = c.get("hook_category", "")
            if cat:
                categories[cat] = categories.get(cat, 0) + 1

        logger.info(
            "HookAnalyzer: analyzed %d / %d items. Categories: %s",
            analyzed,
            len(contents),
            dict(sorted(categories.items(), key=lambda x: -x[1])),
        )
        return contents
