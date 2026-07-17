"""Application logging helpers with optional JSON output."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Render log records as a compact, machine-readable JSON object."""

    _EXTRA_FIELDS = (
        "event",
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(settings: Any) -> None:
    """Configure the process root logger without adding duplicate handlers."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    formatter: logging.Formatter
    if getattr(settings, "log_json", True):
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(settings.log_format)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        root.addHandler(handler)

    for handler in root.handlers:
        handler.setFormatter(formatter)

    # Silence noisy transport logs while retaining errors.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
