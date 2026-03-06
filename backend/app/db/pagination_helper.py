"""
Database helpers for paginated queries: count total and return slice.
"""
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.pagination import PaginatedParams, PaginatedResponse


def paginate_query(
    db: Session,
    model: type,
    page: int,
    page_size: int,
    order_by=None,
) -> tuple[int, list]:
    """
    Run a paginated select on a model. Returns (total, items).
    order_by: optional column to order by (e.g. Model.id or Model.created_at).
    """
    count_stmt = select(func.count()).select_from(model)
    total = db.execute(count_stmt).scalar_one_or_none() or 0

    offset = (page - 1) * page_size
    stmt = select(model).offset(offset).limit(page_size)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    items = list(db.execute(stmt).scalars().all())
    return total, items


def build_paginated_response(
    items: list,
    total: int,
    params: PaginatedParams,
) -> PaginatedResponse:
    """Build a PaginatedResponse from items, total, and pagination params."""
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
