"""Compatibility middleware for the versioned API path."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware


class V1PathPrefixMiddleware(BaseHTTPMiddleware):
    """Serve existing routes under both ``/`` and ``/v1`` during migration."""

    async def dispatch(self, request, call_next):
        path = request.scope["path"]
        if path == "/v1" or path.startswith("/v1/"):
            rewritten = path[len("/v1") :] or "/"
            request.scope["path"] = rewritten
            request.scope["raw_path"] = rewritten.encode("utf-8")
        return await call_next(request)
