"""Unified API response envelope for all AgentOS endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int


class ResponseMeta(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = "7.2.2"
    pagination: PaginationMeta | None = None


class APIError(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class APIResponse(BaseModel, Generic[T]):  # noqa: UP046
    data: T | None = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
    errors: list[APIError] = Field(default_factory=list)

    @classmethod
    def ok(
        cls,
        data: T,
        request_id: str | None = None,
        pagination: PaginationMeta | None = None,
    ) -> APIResponse[T]:
        meta = ResponseMeta(
            request_id=request_id or str(uuid.uuid4()),
            pagination=pagination,
        )
        return cls(data=data, meta=meta)

    @classmethod
    def fail(
        cls,
        errors: list[APIError],
        request_id: str | None = None,
    ) -> APIResponse[None]:
        meta = ResponseMeta(request_id=request_id or str(uuid.uuid4()))
        return cls(data=None, meta=meta, errors=errors)  # type: ignore[return-value]
