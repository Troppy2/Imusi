"""
Artist model: represents a music artist.
Relationships: one-to-many with Album and Song.
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdCreatedUpdatedMixin


class Artist(Base, IdCreatedUpdatedMixin):
    __tablename__ = "artists"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Relationships
    albums: Mapped[list["Album"]] = relationship(
        "Album", back_populates="artist", cascade="all, delete-orphan"
    )
    songs: Mapped[list["Song"]] = relationship(
        "Song", back_populates="artist", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Artist(id={self.id}, name={self.name!r})>"
