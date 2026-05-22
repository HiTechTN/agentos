"""Unified API response format."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int


class Meta(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = "5.0.0"
    pagination: PaginationMeta | None = None


class APIError(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class APIResponse(BaseModel[T]):
    data: T | None = None
    meta: Meta
    errors: list[APIError] = Field(default_factory=list)

    @classmethod
    def ok(cls, data: T, request_id: str = "", **meta_kwargs: Any) -> APIResponse[T]:
        return cls(data=data, meta=Meta(request_id=request_id, **meta_kwargs))

    @classmethod
    def fail(cls, errors: list[APIError], request_id: str = "") -> APIResponse[None]:
        return cls(data=None, meta=Meta(request_id=request_id), errors=errors)
