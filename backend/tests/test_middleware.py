from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware import RequestProtectionMiddleware


def test_request_protection_adds_ids_and_limits_clients() -> None:
    app = FastAPI()
    app.add_middleware(
        RequestProtectionMiddleware,
        max_requests=2,
        window_seconds=60,
    )

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    client = TestClient(app)
    first = client.get("/protected")
    second = client.get("/protected")
    blocked = client.get("/protected")

    assert first.status_code == 200
    assert first.headers["X-Request-ID"]
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.headers["X-Request-ID"]
