"""
Scheduler module for Content Intelligence Platform.

Runs the data pipeline on a configurable daily schedule using the
``schedule`` library. Supports graceful shutdown via signal handlers.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Optional

import schedule

from config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_shutdown_event = threading.Event()


def _signal_handler(signum: int, frame: Optional[object]) -> None:
    """Handle termination signals for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — initiating graceful shutdown.", sig_name)
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# Pipeline job wrapper
# ---------------------------------------------------------------------------
def _run_pipeline_job() -> None:
    """Execute the pipeline and log the outcome."""
    from main import run_pipeline  # deferred import to avoid circular deps

    start = datetime.now(timezone.utc)
    logger.info("═══════════════════════════════════════════════════════════")
    logger.info("Scheduled pipeline run started at %s", start.isoformat())
    logger.info("═══════════════════════════════════════════════════════════")

    try:
        result = run_pipeline(triggered_by="scheduler")
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(
            "Pipeline completed in %.1fs — ingested=%d, processed=%d, stored=%d",
            elapsed,
            result.get("ingested", 0),
            result.get("processed", 0),
            result.get("stored", 0),
        )
    except Exception as exc:
        logger.error("Scheduled pipeline run failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def start_scheduler() -> None:
    """
    Start the blocking scheduler loop.

    The pipeline runs daily at the time configured via
    ``PIPELINE_SCHEDULE_TIME`` (default ``06:00``).

    Graceful shutdown on SIGINT / SIGTERM.
    """
    settings = get_settings()
    run_time = settings.pipeline_schedule_time

    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    schedule.every().day.at(run_time).do(_run_pipeline_job)

    logger.info(
        "Scheduler started — pipeline will run daily at %s UTC.", run_time
    )
    logger.info("Press Ctrl+C to stop.")

    # Blocking loop
    while not _shutdown_event.is_set():
        schedule.run_pending()
        _shutdown_event.wait(timeout=30)

    logger.info("Scheduler stopped gracefully.")


def run_once() -> None:
    """Run the pipeline immediately (useful for testing)."""
    _run_pipeline_job()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    start_scheduler()
