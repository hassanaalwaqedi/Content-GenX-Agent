from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import auth


def test_operator_can_log_in_and_access_a_protected_route(monkeypatch) -> None:
    auth._failed_attempts.clear()
    monkeypatch.setattr(
        auth,
        "_get_auth_settings",
        lambda: {"username": "operator", "password": "correct-password", "secret": "s" * 32},
    )
    app = FastAPI()
    app.include_router(auth.auth_router)

    @app.get("/protected", dependencies=[Depends(auth.require_auth)])
    async def protected():
        return {"ok": True}

    client = TestClient(app)
    failed = client.post("/auth/login", json={"username": "operator", "password": "wrong"})
    login = client.post("/auth/login", json={"username": "operator", "password": "correct-password"})
    allowed = client.get("/protected")

    assert failed.status_code == 401
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    assert allowed.status_code == 200
    assert allowed.json() == {"ok": True}
