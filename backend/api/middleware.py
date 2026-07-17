"""HTTP middleware shared by the API service."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class RequestProtectionMiddleware(BaseHTTPMiddleware):
    """Add request IDs, structured request logs, and a local rate limit.

    This intentionally uses only process memory so local development and the
    single-container deployment remain dependency-free. Deployments with
    multiple API replicas should move this policy to the edge or a shared
    store such as Redis.
    """

    _EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/health"}

    def __init__(self, app, *, max_requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _client_key(request: Request) -> str:
        """Use the connected peer IP; proxy headers are not trusted by default."""
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._requests[client_key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.max_requests:
                return True
            timestamps.append(now)
            return False

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()

        if request.url.path not in self._EXEMPT_PATHS and self._is_rate_limited(self._client_key(request)):
            logger.warning(
                "rate_limited",
                extra={
                    "event": "rate_limited",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 429,
                },
            )
            response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again shortly."},
            )
            response.headers["Retry-After"] = str(self.window_seconds)
        else:
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete",
            extra={
                "event": "request_complete",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
            },
        )
        return response
