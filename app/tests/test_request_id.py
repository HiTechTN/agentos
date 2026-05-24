"""Tests for RequestIDMiddleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.utils.request_id import RequestIDMiddleware


@pytest.fixture()
def app_with_middleware() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRequestIDMiddleware:
    def test_injects_request_id_header(self, app_with_middleware: FastAPI) -> None:
        client = TestClient(app_with_middleware)
        response = client.get("/ping")
        assert "X-Request-ID" in response.headers

    def test_preserves_client_request_id(self, app_with_middleware: FastAPI) -> None:
        client = TestClient(app_with_middleware)
        response = client.get("/ping", headers={"X-Request-ID": "my-id-123"})
        assert response.headers["X-Request-ID"] == "my-id-123"

    def test_generates_uuid_when_absent(self, app_with_middleware: FastAPI) -> None:
        client = TestClient(app_with_middleware)
        r1 = client.get("/ping")
        r2 = client.get("/ping")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]
