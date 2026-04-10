"""
AI Enrichment module for Content Intelligence Platform.

Uses Groq's fast LLM inference API for:
  - Strategic content analysis (target audience, actionable advice, gaps)
  - Topic extraction and content categorization

Falls back to rule-based extraction when Groq API key is not set
or when API calls fail. Includes:
  - Selective enrichment: only Top N videos per niche get LLM calls
  - Rate-limit handling with Retry-After header compliance
  - 2-second cooldown between API calls
  - Graceful "Analysis pending" fallback on any failure
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import requests

from config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_RETRY_AFTER: float = 5.0
_MAX_RETRIES_PER_VIDEO: int = 2
_COOLDOWN_BETWEEN_CALLS: float = 2.0   # seconds between Groq API calls
_TOP_N_PER_NICHE: int = 10             # only enrich top N per niche
_CIRCUIT_BREAKER_THRESHOLD: int = 3    # consecutive failures before skipping

_PENDING = "Analysis pending"


# ---------------------------------------------------------------------------
# Keyword-based topic extraction (rule-based fallback)
# ---------------------------------------------------------------------------
_TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "large_language_models": ["llm", "gpt", "chatgpt", "claude", "gemini", "language model"],
    "prompt_engineering": ["prompt", "prompting", "chain of thought", "few-shot", "zero-shot"],
    "ai_automation": ["automation", "automate", "workflow", "agent", "agentic"],
    "machine_learning": ["machine learning", "ml", "neural network", "deep learning", "training"],
    "ai_business": ["business", "enterprise", "startup", "revenue", "roi", "saas"],
    "ai_productivity": ["productivity", "efficiency", "tool", "copilot", "assistant"],
    "computer_vision": ["computer vision", "image recognition", "object detection", "cv"],
    "nlp": ["nlp", "natural language", "text analysis", "sentiment", "tokenization"],
    "ai_ethics": ["ethics", "bias", "fairness", "responsible ai", "alignment"],
    "generative_ai": ["generative", "diffusion", "stable diffusion", "midjourney", "dall-e", "image generation"],
}


def _extract_topics_rule_based(title: str, description: str) -> List[str]:
    """Extract topics using keyword matching (fast, no API calls)."""
    combined = f"{title} {description}".lower()
    topics: List[str] = []

    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            topics.append(topic)

    return topics if topics else ["general_ai"]


def _apply_pending_defaults(video: Dict[str, Any]) -> Dict[str, Any]:
    """Fill strategic insight fields with 'Analysis pending' placeholders."""
    topics = _extract_topics_rule_based(
        video.get("title", ""), video.get("description", "")
    )
    video.setdefault("topics", json.dumps(topics))
    video.setdefault("content_category", topics[0] if topics else "uncategorized")
    video.setdefault("ai_summary", "")
    video.setdefault("target_audience", _PENDING)
    video.setdefault("strategic_advice", _PENDING)
    video.setdefault("content_gap", _PENDING)
    return video


# ---------------------------------------------------------------------------
# Groq-powered extraction
# ---------------------------------------------------------------------------
class GroqClient:
    """Thin client for Groq's OpenAI-compatible chat completions API."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> str:
        """
        Send a chat completion request and return the assistant message.

        Raises ``requests.HTTPError`` on failure so callers can inspect
        the status code (especially 429 for rate limiting).
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = self._session.post(self.BASE_URL, json=payload, timeout=15)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            # Sanitize: strip Authorization header from exception's request
            # object to prevent Bearer tokens leaking into log tracebacks.
            if exc.request is not None and hasattr(exc.request, "headers"):
                exc.request.headers.pop("Authorization", None)
            raise
        data = response.json()

        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Strategic enrichment prompt
# ---------------------------------------------------------------------------
_STRATEGIC_PROMPT = (
    "You are a senior content strategist advising the CEO of a digital media company. "
    "Given a YouTube video's title and description, produce a JSON strategic analysis.\n\n"
    "IMPORTANT: All values must be plain strings on a single line. No newlines inside values.\n\n"
    "{\n"
    '  "topics": ["topic_1", "topic_2"],\n'
    '  "category": "primary_category",\n'
    '  "summary": "one-sentence content summary",\n'
    '  "target_audience": "specific audience (e.g. early-stage SaaS founders, solo developers)",\n'
    '  "strategic_advice": "1) First tip. 2) Second tip. 3) Third tip.",\n'
    '  "content_gap": "What this video missed that we could cover to capture remaining audience"\n'
    "}\n\n"
    "Rules:\n"
    "- topics: 1-5 snake_case slugs (e.g. prompt_engineering, ai_automation)\n"
    "- strategic_advice: exactly 3 tips in a SINGLE LINE separated by numbering 1) 2) 3)\n"
    "- All string values must be on ONE LINE, no line breaks inside values\n"
    "- Respond ONLY with valid JSON, no markdown, no explanation."
)


def _extract_strategic_insights(
    client: GroqClient, title: str, description: str
) -> Dict[str, Any]:
    """
    Use Groq LLM to extract strategic, business-actionable insights.

    Returns a dict with keys: topics, content_category, ai_summary,
    target_audience, strategic_advice, content_gap
    """
    desc_truncated = description[:500] if description else ""

    messages = [
        {"role": "system", "content": _STRATEGIC_PROMPT},
        {"role": "user", "content": f"Title: {title}\nDescription: {desc_truncated}"},
    ]

    try:
        raw = client.chat(messages)
        # Strip potential markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0]

        # Replace literal newlines inside JSON string values to prevent parse errors
        cleaned = re.sub(r'(?<!\\)\n', ' ', cleaned)

        result = json.loads(cleaned)

        # Serialize topics list to JSON string for SQLite storage
        topics_raw = result.get("topics", ["general_ai"])
        topics_str = json.dumps(topics_raw) if isinstance(topics_raw, list) else str(topics_raw)

        return {
            "topics": topics_str,
            "content_category": result.get("category", "uncategorized"),
            "ai_summary": result.get("summary", ""),
            "target_audience": result.get("target_audience", _PENDING),
            "strategic_advice": result.get("strategic_advice", _PENDING),
            "content_gap": result.get("content_gap", _PENDING),
        }
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Groq response parse error: %s -- using pending.", exc)
        topics = _extract_topics_rule_based(title, description)
        return {
            "topics": json.dumps(topics),
            "content_category": "uncategorized",
            "ai_summary": "",
            "target_audience": _PENDING,
            "strategic_advice": _PENDING,
            "content_gap": _PENDING,
        }


# ---------------------------------------------------------------------------
# Single-video enrichment with rate-limit handling
# ---------------------------------------------------------------------------
def enrich_video(
    video: Dict[str, Any], client: Optional[GroqClient] = None
) -> Dict[str, Any]:
    """
    Enrich a single video dict with AI-derived strategic insights.

    Uses Groq LLM if client is provided, otherwise fills with pending.
    Handles 429 rate limits with Retry-After compliance and retries
    up to ``_MAX_RETRIES_PER_VIDEO`` times.
    """
    title = video.get("title", "")
    description = video.get("description", "")

    if client:
        for attempt in range(_MAX_RETRIES_PER_VIDEO + 1):
            try:
                ai_data = _extract_strategic_insights(client, title, description)
                video.update(ai_data)
                return video
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    retry_after = float(
                        exc.response.headers.get("Retry-After", _DEFAULT_RETRY_AFTER)
                    )
                    if attempt < _MAX_RETRIES_PER_VIDEO:
                        logger.info(
                            "Rate limited (429) -- sleeping %.1fs before retry %d/%d",
                            retry_after,
                            attempt + 1,
                            _MAX_RETRIES_PER_VIDEO,
                        )
                        time.sleep(retry_after)
                        continue
                    else:
                        logger.warning(
                            "Rate limited (429) for video '%s' after %d retries -- pending.",
                            video.get("video_id", "?"),
                            _MAX_RETRIES_PER_VIDEO,
                        )
                else:
                    logger.warning(
                        "Groq API error for video '%s': %s -- pending.",
                        video.get("video_id", "?"),
                        exc,
                    )
                break  # Fall through to pending on non-429 errors

    # Fallback: fill with rule-based topics and "Analysis pending"
    return _apply_pending_defaults(video)


# ---------------------------------------------------------------------------
# Selective batch enrichment
# ---------------------------------------------------------------------------
def _select_top_n_per_niche(
    videos: List[Dict[str, Any]], n: int = _TOP_N_PER_NICHE
) -> set:
    """
    Return a set of video_ids for the top N videos per niche (by score).

    This reduces API calls while ensuring the highest-value content
    gets full strategic analysis.
    """
    by_niche: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for v in videos:
        by_niche[v.get("niche", "unknown")].append(v)

    selected_ids: set = set()
    for niche, niche_videos in by_niche.items():
        # Sort by score descending, take top N
        top = sorted(niche_videos, key=lambda x: x.get("score", 0), reverse=True)[:n]
        for v in top:
            selected_ids.add(v["video_id"])
        logger.info(
            "Niche '%s': selected top %d / %d for strategic enrichment.",
            niche,
            len(top),
            len(niche_videos),
        )

    return selected_ids


def enrich_videos(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Selectively enrich videos with strategic AI insights.

    - Only the Top 10 videos per niche (by score) are sent to Groq LLM
    - Remaining videos get rule-based topics + "Analysis pending" fields
    - 2-second cooldown between API calls to avoid 429 rate limits
    - Any failure fills fields with "Analysis pending" (never crashes)
    """
    settings = get_settings()
    client: Optional[GroqClient] = None

    if settings.groq_api_key:
        client = GroqClient(settings.groq_api_key)
        logger.info("Groq API key found -- using strategic LLM enrichment.")
    else:
        logger.info("No Groq API key -- all videos get 'Analysis pending'.")

    # Determine which videos qualify for LLM enrichment
    selected_ids = _select_top_n_per_niche(videos) if client else set()
    logger.info(
        "Selected %d videos for LLM enrichment out of %d total.",
        len(selected_ids),
        len(videos),
    )

    enriched = []
    llm_count = 0
    consecutive_failures = 0
    circuit_open = False

    for i, v in enumerate(videos):
        try:
            if v["video_id"] in selected_ids and client and not circuit_open:
                # Full strategic enrichment via Groq
                result = enrich_video(v, client)
                enriched.append(result)
                llm_count += 1

                # Check if enrichment actually succeeded (not just fallback)
                if result.get("target_audience") == _PENDING:
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0  # Reset on success

                # Circuit breaker: stop LLM calls after N consecutive failures
                if consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
                    circuit_open = True
                    logger.warning(
                        "Circuit breaker OPEN after %d consecutive failures "
                        "-- skipping remaining LLM calls.",
                        consecutive_failures,
                    )

                # Cooldown between API calls
                if i < len(videos) - 1 and not circuit_open:
                    time.sleep(_COOLDOWN_BETWEEN_CALLS)

                if llm_count % 5 == 0:
                    logger.info(
                        "Strategic enrichment: %d / %d LLM calls complete.",
                        llm_count,
                        len(selected_ids),
                    )
            else:
                # Rule-based fallback + pending strategic fields
                enriched.append(_apply_pending_defaults(v))

        except Exception as exc:
            logger.error(
                "Enrichment failed for video %s: %s -- using pending.",
                v.get("video_id", "?"),
                exc,
            )
            consecutive_failures += 1
            enriched.append(_apply_pending_defaults(v))

            if consecutive_failures >= _CIRCUIT_BREAKER_THRESHOLD:
                circuit_open = True
                logger.warning(
                    "Circuit breaker OPEN after %d consecutive failures.",
                    consecutive_failures,
                )

    logger.info(
        "Enrichment complete: %d total, %d with strategic insights, %d pending.%s",
        len(enriched),
        llm_count,
        len(enriched) - llm_count,
        " (circuit breaker was triggered)" if circuit_open else "",
    )
    return enriched
