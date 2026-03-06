"""
Album model: represents an album, linked to an artist.
Relationships: belongs to Artist, has many Songs.
"""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdCreatedUpdatedMixin

if TYPE_CHECKING:
    from app.models.artist import Artist
    from app.models.song import Song


class Album(Base, IdCreatedUpdatedMixin):
    __tablename__ = "albums"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    artist: Mapped["Artist"] = relationship("Artist", back_populates="albums")
    songs: Mapped[list["Song"]] = relationship(
        "Song",
        back_populates="album",
        cascade="all, delete-orphan",
        order_by="Song.track_number",
    )

    def __repr__(self) -> str:
        return f"<Album(id={self.id}, title={self.title!r})>"
