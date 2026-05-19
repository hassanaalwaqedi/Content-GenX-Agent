"""
Daily Rate Limiter for Platform Connectors.

Tracks scan counts per platform per day using a lightweight
JSON file. Prevents excessive scraping that would trigger
IP bans or account restrictions.

Default limits (configurable via .env):
    - TikTok:    3 scans/day  (unofficial API, high ban risk)
    - Instagram: 5 scans/day  (authenticated, moderate risk)
    - YouTube:   Unlimited    (official API with quota)
    - Reddit:    Unlimited    (official API)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# File stored next to the SQLite DB
_RATE_FILE = Path(__file__).resolve().parent.parent / ".rate_limits.json"

# Default daily limits per platform
DEFAULT_DAILY_LIMITS: Dict[str, int] = {
    "tiktok": 3,
    "instagram": 5,
    "youtube": 0,   # 0 = unlimited
    "reddit": 0,    # 0 = unlimited
}


def _today() -> str:
    """Return today's date string in UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_state() -> Dict:
    """Load rate limit state from disk."""
    if _RATE_FILE.exists():
        try:
            return json.loads(_RATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: Dict) -> None:
    """Persist rate limit state to disk."""
    try:
        _RATE_FILE.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("Failed to save rate limit state: %s", exc)


def get_daily_limit(platform: str) -> int:
    """
    Get the daily scan limit for a platform.

    Checks env vars first (e.g. TIKTOK_DAILY_SCAN_LIMIT=5),
    falls back to DEFAULT_DAILY_LIMITS.
    """
    from config import get_settings
    settings = get_settings()

    # Check for platform-specific env var
    env_key = f"{platform}_daily_scan_limit"
    limit = getattr(settings, env_key, None)
    if limit is not None:
        return int(limit)

    return DEFAULT_DAILY_LIMITS.get(platform, 0)


def get_scans_today(platform: str) -> int:
    """Return how many scans have been used today for a platform."""
    state = _load_state()
    today = _today()
    return state.get(today, {}).get(platform, 0)


def get_remaining_scans(platform: str) -> int:
    """Return how many scans are left today for a platform."""
    limit = get_daily_limit(platform)
    if limit <= 0:
        return 999  # Unlimited
    used = get_scans_today(platform)
    return max(0, limit - used)


def check_rate_limit(platform: str) -> tuple[bool, str]:
    """
    Check if a platform scan is allowed.

    Returns:
        (allowed: bool, message: str)
    """
    limit = get_daily_limit(platform)
    if limit <= 0:
        return True, ""  # Unlimited

    used = get_scans_today(platform)
    remaining = limit - used

    if remaining <= 0:
        msg = (
            f"{platform.title()} daily scan limit reached ({limit}/day). "
            f"Limit resets at midnight UTC. "
            f"Skipping {platform.title()} to avoid IP ban."
        )
        logger.warning(msg)
        return False, msg

    if remaining == 1:
        logger.info(
            "%s: Last scan remaining today (%d/%d used).",
            platform.title(), used, limit,
        )

    return True, f"{remaining} scans remaining today"


def record_scan(platform: str) -> None:
    """Record that a scan was performed for a platform."""
    state = _load_state()
    today = _today()

    # Clean old dates (keep only today)
    state = {k: v for k, v in state.items() if k == today}

    if today not in state:
        state[today] = {}

    state[today][platform] = state[today].get(platform, 0) + 1
    _save_state(state)

    limit = get_daily_limit(platform)
    used = state[today][platform]
    logger.info(
        "%s scan recorded: %d/%d used today.",
        platform.title(),
        used,
        limit if limit > 0 else "∞",
    )


def get_all_limits() -> Dict[str, Dict]:
    """
    Return rate limit status for all platforms.

    Used by the /connectors/health API to display limits in the UI.
    """
    result = {}
    for platform in DEFAULT_DAILY_LIMITS:
        limit = get_daily_limit(platform)
        used = get_scans_today(platform)
        result[platform] = {
            "daily_limit": limit if limit > 0 else "unlimited",
            "scans_today": used,
            "remaining": get_remaining_scans(platform),
            "is_limited": limit > 0,
        }
    return result
