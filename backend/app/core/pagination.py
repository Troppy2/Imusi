"""
Pagination: shared params (page, page_size) and response schema for list endpoints.
"""
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedParams(BaseModel):
    """Query params for paginated list endpoints. Use as a FastAPI dependency."""

    page: int = Field(1, ge=1, description="1-based page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page (max 100)")


def get_pagination_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
) -> PaginatedParams:
    """FastAPI dependency: reads page, page_size from query and returns validated params."""
    return PaginatedParams(page=page, page_size=page_size)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response: items, total count, page, page_size."""

    items: list[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    pages: int = Field(..., ge=0, description="Total number of pages")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
