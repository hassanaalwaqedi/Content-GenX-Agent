import pytest
from pydantic import ValidationError

from core.config import Settings


def test_cors_rejects_wildcard_origins() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS origins"):
        Settings(
            _env_file=None,
            cors_allowed_origins=["*"],
            genx_auth_secret="a" * 32,
        )


def test_configured_admin_requires_a_persistent_auth_secret() -> None:
    with pytest.raises(ValidationError, match="GENX_AUTH_SECRET is required"):
        Settings(
            _env_file=None,
            genx_admin_username="admin",
            genx_admin_password="not-used-by-the-test",
            genx_auth_secret="",
        )


def test_cors_normalizes_explicit_origins() -> None:
    settings = Settings(
        _env_file=None,
        cors_allowed_origins=[" http://localhost:5173/ "],
        genx_auth_secret="a" * 32,
    )
    assert settings.cors_allowed_origins == ["http://localhost:5173"]
