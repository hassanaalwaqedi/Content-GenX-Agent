"""
Authentication module for the GenX Intelligence Platform.

Provides:
    - JWT-based session management via HttpOnly cookies
    - Single-operator credential validation
    - Rate limiting on login attempts
    - FastAPI dependency for route protection

Usage:
    from auth import auth_router, require_auth

    app.include_router(auth_router)

    @app.get("/protected", dependencies=[Depends(require_auth)])
    async def protected_endpoint(): ...
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (loaded lazily to avoid circular imports)
# ---------------------------------------------------------------------------
_SESSION_LIFETIME_HOURS = 24
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60

# In-memory rate limiter state
_failed_attempts: Dict[str, list] = defaultdict(list)


_cached_fallback_secret: Optional[str] = None


def _get_auth_settings():
    """Load auth settings from config (lazy to avoid import cycles)."""
    global _cached_fallback_secret
    from config import get_settings

    s = get_settings()
    secret = s.genx_auth_secret
    if not secret:
        # Generate a fallback secret ONCE and cache it for the process lifetime.
        # Without this, os.urandom() would produce a new secret on every call,
        # making every previously-issued token immediately invalid.
        if _cached_fallback_secret is None:
            _cached_fallback_secret = os.urandom(32).hex()
            logger.warning(
                "⚠ GENX_AUTH_SECRET not set — using auto-generated secret. "
                "Sessions will NOT survive server restarts."
            )
        secret = _cached_fallback_secret
    return {
        "username": s.genx_admin_username,
        "password": s.genx_admin_password,
        "secret": secret,
    }


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def _create_token(username: str, secret: str) -> str:
    """Create a signed JWT with 24h expiration."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=_SESSION_LIFETIME_HOURS),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT. Returns payload or None on failure."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.debug("Session token expired.")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid session token: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
def _check_rate_limit(client_ip: str) -> bool:
    """
    Check if the client IP is rate-limited.
    Returns True if the request should be BLOCKED.
    """
    now = time.time()
    # Clean old entries (older than lockout window)
    _failed_attempts[client_ip] = [
        t for t in _failed_attempts[client_ip]
        if now - t < _LOCKOUT_SECONDS
    ]
    return len(_failed_attempts[client_ip]) >= _MAX_FAILED_ATTEMPTS


def _record_failed_attempt(client_ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    _failed_attempts[client_ip].append(time.time())


def _clear_failed_attempts(client_ip: str) -> None:
    """Clear failed attempts on successful login."""
    _failed_attempts.pop(client_ip, None)


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
_COOKIE_NAME = "genx_session"


def _is_production() -> bool:
    """Detect if running in production (HTTPS / cross-origin)."""
    return bool(os.environ.get("PRODUCTION") or os.environ.get("AWS_EXECUTION_ENV"))


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the session cookie with security flags."""
    prod = _is_production()
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="none" if prod else "lax",
        secure=prod,
        max_age=_SESSION_LIFETIME_HOURS * 3600,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear the session cookie."""
    prod = _is_production()
    response.delete_cookie(
        key=_COOKIE_NAME,
        httponly=True,
        samesite="none" if prod else "lax",
        secure=prod,
        path="/",
    )


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class AuthStatus(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    expires_at: Optional[str] = None
    token: Optional[str] = None  # JWT returned in body for cross-origin clients


# ---------------------------------------------------------------------------
# FastAPI dependency: require_auth
# ---------------------------------------------------------------------------
async def require_auth(
    request: Request,
    genx_session: Optional[str] = Cookie(None),
) -> Dict[str, Any]:
    """
    FastAPI dependency that validates auth via:
      1. Authorization: Bearer <token> header (cross-origin / production)
      2. genx_session cookie (same-origin / development)
    """
    settings = _get_auth_settings()
    token = None

    # 1. Check Authorization header first
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Fallback to cookie
    if not token and genx_session:
        token = genx_session

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    payload = _decode_token(token, settings["secret"])

    if payload is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    return payload


# ---------------------------------------------------------------------------
# Auth router
# ---------------------------------------------------------------------------
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/login", response_model=AuthStatus)
async def login(body: LoginRequest, request: Request, response: Response):
    """
    Authenticate the operator and set a session cookie.
    Rate-limited: 5 failed attempts → 60s lockout.
    """
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit check
    if _check_rate_limit(client_ip):
        logger.warning("⛔ Login rate-limited for IP: %s", client_ip)
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please wait 60 seconds.",
        )

    settings = _get_auth_settings()

    # Validate credentials configured
    if not settings["username"] or not settings["password"]:
        logger.error("Auth credentials not configured in .env")
        raise HTTPException(
            status_code=500,
            detail="Authentication not configured. Set GENX_ADMIN_USERNAME and GENX_ADMIN_PASSWORD in .env",
        )

    # Timing-safe credential comparison
    username_match = hmac.compare_digest(
        body.username.encode("utf-8"),
        settings["username"].encode("utf-8"),
    )
    password_match = hmac.compare_digest(
        body.password.encode("utf-8"),
        settings["password"].encode("utf-8"),
    )

    if not (username_match and password_match):
        _record_failed_attempt(client_ip)
        remaining = _MAX_FAILED_ATTEMPTS - len(_failed_attempts.get(client_ip, []))
        logger.warning(
            "⚠ Failed login attempt from %s (user: %s, %d attempts remaining)",
            client_ip, body.username, max(remaining, 0),
        )
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # Success
    _clear_failed_attempts(client_ip)
    token = _create_token(body.username, settings["secret"])
    _set_auth_cookie(response, token)

    # Calculate expiry for response
    exp_time = datetime.now(timezone.utc) + timedelta(hours=_SESSION_LIFETIME_HOURS)

    logger.info("✔ Successful login from %s (user: %s)", client_ip, body.username)

    return AuthStatus(
        authenticated=True,
        username=body.username,
        expires_at=exp_time.isoformat(),
        token=token,
    )


@auth_router.post("/logout", response_model=AuthStatus)
async def logout(response: Response):
    """Clear the session cookie and log out."""
    _clear_auth_cookie(response)
    return AuthStatus(authenticated=False)


@auth_router.get("/me", response_model=AuthStatus)
async def me(
    request: Request,
    genx_session: Optional[str] = Cookie(None),
):
    """
    Check current authentication status.
    Accepts Bearer token or session cookie.
    """
    settings = _get_auth_settings()
    token = None

    # Check Authorization header first
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # Fallback to cookie
    if not token and genx_session:
        token = genx_session

    if not token:
        return AuthStatus(authenticated=False)

    payload = _decode_token(token, settings["secret"])

    if payload is None:
        return AuthStatus(authenticated=False)

    exp_time = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
    return AuthStatus(
        authenticated=True,
        username=payload.get("sub"),
        expires_at=exp_time.isoformat(),
    )
