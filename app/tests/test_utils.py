from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.utils.auth import (
    AdminUser,
    CurrentUser,
    TokenPayload,
    create_access_token,
    get_current_user,
    require_admin,
)
from app.utils.request_id import RequestIDMiddleware

# ── auth ───────────────────────────────────────────────


def test_create_access_token_default_role() -> None:
    mock_token = "eyJ.abc.def"
    with patch("app.utils.auth.jwt.encode", return_value=mock_token) as mock_encode:
        token = create_access_token(sub="alice", workspace="ws1")

    assert token == mock_token
    mock_encode.assert_called_once()
    payload = mock_encode.call_args[0][0]
    assert payload["sub"] == "alice"
    assert payload["workspace"] == "ws1"
    assert payload["role"] == "user"
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_custom_role() -> None:
    mock_token = "eyJ.xyz.789"
    with patch("app.utils.auth.jwt.encode", return_value=mock_token) as mock_encode:
        token = create_access_token(sub="bob", workspace="ws2", role="admin")

    assert token == mock_token
    payload = mock_encode.call_args[0][0]
    assert payload["role"] == "admin"


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing Authorization header"


@pytest.mark.asyncio
async def test_get_current_user_valid_token() -> None:
    now = datetime.now(UTC)
    creds = HTTPAuthorizationCredentials(credentials="valid.jwt", scheme="Bearer")
    mock_payload = {"sub": "alice", "workspace": "ws1", "role": "user", "exp": now}
    with patch("app.utils.auth.jwt.decode", return_value=mock_payload):
        result = await get_current_user(creds)
    assert result.sub == "alice"
    assert result.workspace == "ws1"
    assert result.role == "user"
    assert result.exp == now


@pytest.mark.asyncio
async def test_get_current_user_expired_token() -> None:
    creds = HTTPAuthorizationCredentials(credentials="expired.jwt", scheme="Bearer")
    with patch("app.utils.auth.jwt.decode", side_effect=pyjwt.ExpiredSignatureError):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expired"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token() -> None:
    creds = HTTPAuthorizationCredentials(credentials="bad.jwt", scheme="Bearer")
    with patch("app.utils.auth.jwt.decode", side_effect=pyjwt.InvalidTokenError):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds)
    assert exc.value.status_code == 401
    assert exc.value.detail.startswith("Invalid token")


@pytest.mark.asyncio
async def test_require_admin_allowed() -> None:
    user = TokenPayload(sub="admin", workspace="ws1", exp=datetime.now(UTC), role="admin")
    result = await require_admin(user)
    assert result is user


@pytest.mark.asyncio
async def test_require_admin_forbidden() -> None:
    user = TokenPayload(sub="user", workspace="ws1", exp=datetime.now(UTC), role="user")
    with pytest.raises(HTTPException) as exc:
        await require_admin(user)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Admin role required"


def test_current_user_type_alias() -> None:
    from typing import Annotated, get_origin

    assert get_origin(CurrentUser) is Annotated


def test_admin_user_type_alias() -> None:
    from typing import Annotated, get_origin

    assert get_origin(AdminUser) is Annotated


# ── rate_limit ─────────────────────────────────────────


def test_limiter_singleton() -> None:
    from slowapi import Limiter

    from app.utils.rate_limit import limiter

    assert isinstance(limiter, Limiter)


def test_limits_populated() -> None:
    from app.utils.rate_limit import LIMITS

    assert "run" in LIMITS
    assert "plan" in LIMITS
    assert "verify" in LIMITS


def test_make_limiter_returns_limiter() -> None:
    from slowapi import Limiter

    from app.utils.rate_limit import _build_limiter

    lim = _build_limiter()
    assert isinstance(lim, Limiter)


def test_make_limiter_populates_limits() -> None:
    from app.utils.rate_limit import _get_limits, limiter

    _ = limiter
    limits = _get_limits()
    assert "run" in limits
    assert "plan" in limits
    assert "verify" in limits


# ── request_id ─────────────────────────────────────────


async def _dummy_view(request: Any) -> Any:
    return PlainTextResponse("ok")


def _make_app() -> Any:
    app = Starlette(
        routes=[Route("/", _dummy_view)],
        middleware=[Middleware(RequestIDMiddleware)],
    )
    return app


def test_request_id_with_header() -> None:
    client = TestClient(_make_app())
    resp = client.get("/", headers={"X-Request-ID": "my-custom-id"})
    assert resp.headers.get("X-Request-ID") == "my-custom-id"


def test_request_id_without_header() -> None:
    client = TestClient(_make_app())
    resp = client.get("/")
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) > 0
