"""Tests for unified APIResponse envelope."""

from __future__ import annotations

from typing import Any

from app.schemas.responses import APIError, APIResponse, PaginationMeta


class TestAPIResponseOk:
    def test_ok_sets_data(self) -> None:
        r: APIResponse[str] = APIResponse.ok("hello")
        assert r.data == "hello"
        assert r.errors == []

    def test_ok_generates_request_id(self) -> None:
        r = APIResponse.ok("x")
        assert len(r.meta.request_id) > 0

    def test_ok_with_custom_request_id(self) -> None:
        r = APIResponse.ok("x", request_id="my-req")
        assert r.meta.request_id == "my-req"

    def test_ok_with_pagination(self) -> None:
        p = PaginationMeta(page=1, per_page=10, total=100, pages=10)
        r: APIResponse[Any] = APIResponse.ok([], pagination=p)
        assert r.meta.pagination is not None
        assert r.meta.pagination.total == 100


class TestAPIResponseFail:
    def test_fail_sets_errors(self) -> None:
        err = APIError(code="E001", message="Something failed")
        r = APIResponse.fail([err])
        assert r.data is None
        assert len(r.errors) == 1
        assert r.errors[0].code == "E001"

    def test_fail_with_field(self) -> None:
        err = APIError(code="VAL", message="Invalid", field="email")
        r = APIResponse.fail([err])
        assert r.errors[0].field == "email"
