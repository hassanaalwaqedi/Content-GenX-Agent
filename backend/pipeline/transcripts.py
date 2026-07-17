"""
Transcript extraction module for Content Intelligence Platform.

Fetches video transcripts/captions from YouTube using the
youtube-transcript-api library (no API key required).

Features:
  - Uses the v1.2+ API with instance-based client
  - Auto-detects available languages (prefers English)
  - Falls back to auto-generated captions
  - Truncates long transcripts for efficient storage
  - Graceful failure: returns empty string on any error
"""

from __future__ import annotations

import logging
from typing import List

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)

# Maximum transcript length to store (characters)
_MAX_TRANSCRIPT_LENGTH = 5000

# Languages to try, in order of preference
_PREFERRED_LANGUAGES = ["en", "de", "fr", "es", "ar", "tr"]

# Reusable client instance
_api = YouTubeTranscriptApi()


def fetch_transcript(video_id: str, *, max_length: int = _MAX_TRANSCRIPT_LENGTH) -> str:
    """
    Fetch the transcript for a YouTube video.

    Args:
        video_id: YouTube video ID (e.g., 'dQw4w9WgXcQ')
        max_length: Maximum characters to store (default 5000)

    Returns:
        The transcript text, or empty string if unavailable.
    """
    # Skip non-YouTube content (e.g., Reddit posts)
    if video_id.startswith("reddit_"):
        return ""

    try:
        # Try to find a transcript in preferred languages
        transcript_list = _api.list(video_id)

        # Try manually created transcripts first (higher quality)
        fetched = None
        try:
            fetched = transcript_list.find_manually_created_transcript(_PREFERRED_LANGUAGES)
        except NoTranscriptFound:
            pass

        # Fall back to auto-generated
        if fetched is None:
            try:
                fetched = transcript_list.find_generated_transcript(_PREFERRED_LANGUAGES)
            except NoTranscriptFound:
                logger.debug("No transcript available for video %s.", video_id)
                return ""

        # Fetch the actual transcript data
        result = fetched.fetch()

        # Extract text from snippets
        full_text = " ".join(snippet.text for snippet in result.snippets)

        # Clean up whitespace
        full_text = " ".join(full_text.split())

        # Truncate if too long
        if len(full_text) > max_length:
            full_text = full_text[:max_length] + "..."

        logger.info(
            "Transcript fetched for %s (%d chars, lang=%s).",
            video_id, len(full_text), result.language_code,
        )
        return full_text

    except TranscriptsDisabled:
        logger.debug("Transcripts disabled for video %s.", video_id)
        return ""
    except VideoUnavailable:
        logger.debug("Video %s is unavailable.", video_id)
        return ""
    except Exception as exc:
        logger.warning("Failed to fetch transcript for %s: %s", video_id, exc)
        return ""


def fetch_transcript_segments(video_id: str) -> List[dict]:
    """
    Fetch raw transcript segments with timing data for a YouTube video.

    Returns a list of dicts with keys: text, start, duration.
    Returns empty list if unavailable.
    """
    if video_id.startswith("reddit_"):
        return []

    try:
        transcript_list = _api.list(video_id)

        fetched = None
        try:
            fetched = transcript_list.find_manually_created_transcript(_PREFERRED_LANGUAGES)
        except NoTranscriptFound:
            pass

        if fetched is None:
            try:
                fetched = transcript_list.find_generated_transcript(_PREFERRED_LANGUAGES)
            except NoTranscriptFound:
                logger.debug("No transcript segments available for video %s.", video_id)
                return []

        result = fetched.fetch()
        segments = [
            {
                "text": snippet.text,
                "start": getattr(snippet, "start", 0),
                "duration": getattr(snippet, "duration", 0),
            }
            for snippet in result.snippets
        ]
        logger.info(
            "Transcript segments fetched for %s (%d segments).",
            video_id, len(segments),
        )
        return segments

    except (TranscriptsDisabled, VideoUnavailable):
        return []
    except Exception as exc:
        logger.warning("Failed to fetch transcript segments for %s: %s", video_id, exc)
        return []


def extract_first_30s(transcript_segments: List[dict]) -> str:
    """
    Extract the text from the first 30 seconds of transcript segments.

    Args:
        transcript_segments: List of dicts with 'text', 'start', 'duration' keys.

    Returns:
        Concatenated text from segments within the first 30 seconds.
    """
    duration = 0
    result = []

    for segment in transcript_segments:
        result.append(segment["text"])
        duration += segment.get("duration", 0)

        if duration >= 30:
            break

    return " ".join(result)
