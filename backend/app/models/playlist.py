"""
Playlist model: user-created list of songs.
Order is preserved via PlaylistSong.position. updated_at for cache invalidation.
"""
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdCreatedUpdatedMixin

if TYPE_CHECKING:
    from app.models.playlist_song import PlaylistSong


class Playlist(Base, IdCreatedUpdatedMixin):
    __tablename__ = "playlists"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    playlist_songs: Mapped[list["PlaylistSong"]] = relationship(
        "PlaylistSong",
        back_populates="playlist",
        cascade="all, delete-orphan",
        order_by="PlaylistSong.position",
    )

    def __repr__(self) -> str:
        return f"<Playlist(id={self.id}, name={self.name!r})>"
