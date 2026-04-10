"""Backfill transcripts for existing YouTube videos in the database.

Uses a configurable delay between requests to avoid YouTube IP blocking.
Can be run multiple times safely — only fetches for videos without transcripts.

Features:
  - Auto-detects IP blocks and stops early after consecutive failures
  - Configurable delay between requests
  - Progress reporting every 10 videos
  - Safe to interrupt and resume later
"""
import sys
import time
import logging

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

from database import get_connection, init_db
from transcripts import fetch_transcript

logger = logging.getLogger(__name__)

# Delay between transcript requests (seconds) to avoid YouTube rate limiting
DELAY_BETWEEN_REQUESTS = 2.0

# Stop after this many consecutive failures (likely IP block)
MAX_CONSECUTIVE_FAILURES = 10


def backfill():
    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT video_id FROM videos "
            "WHERE platform = 'youtube' "
            "AND (transcript IS NULL OR transcript = '')"
        ).fetchall()

    total = len(rows)
    if total == 0:
        logger.info("All videos already have transcripts. Nothing to do.")
        return

    logger.info("Found %d videos without transcripts. Starting backfill...", total)
    logger.info("Using %.1fs delay between requests to avoid rate limiting.", DELAY_BETWEEN_REQUESTS)
    logger.info("Will stop after %d consecutive failures (IP block detection).", MAX_CONSECUTIVE_FAILURES)

    success = 0
    consecutive_failures = 0

    for i, row in enumerate(rows, 1):
        vid = row["video_id"]
        transcript = fetch_transcript(vid)

        if transcript:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE videos SET transcript = ? WHERE video_id = ?",
                    (transcript, vid),
                )
            success += 1
            consecutive_failures = 0  # Reset on success
        else:
            consecutive_failures += 1

        if i % 10 == 0 or i == total:
            logger.info("Progress: %d/%d (%d transcripts found, %d consecutive fails)", i, total, success, consecutive_failures)

        # Stop early if likely IP-blocked
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning(
                "Stopping early: %d consecutive failures detected (likely YouTube IP block). "
                "Try again later or use a VPN/proxy.",
                consecutive_failures,
            )
            break

        # Throttle to avoid YouTube IP blocking
        if i < total:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    logger.info("Backfill complete: %d/%d videos now have transcripts.", success, total)
    logger.info("Run this script again later to continue backfilling remaining videos.")


if __name__ == "__main__":
    backfill()
