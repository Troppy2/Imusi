"""
SQLAlchemy declarative base and metadata.
All models inherit from this base for consistent table creation.
Provides IdCreatedUpdatedMixin for common id, created_at, updated_at fields.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models (2.0 style)."""
    pass


class IdCreatedUpdatedMixin:
    """
    Mixin for tables with single-column PK and audit timestamps.
    Use for: artists, albums, songs, folders, playlists.
    """
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
