"""Common reusable Pydantic schemas."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error payload details."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Consistent error envelope matching docs/API.md specification."""

    error: ErrorDetail


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated list response envelope."""

    total: int
    page: int
    page_size: int
    items: list[T]
