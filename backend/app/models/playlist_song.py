"""
PlaylistSong: ordered tracks in a playlist.
Primary key (playlist_id, position) allows stable ordering; each row has song_id and added_at.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.playlist import Playlist
    from app.models.song import Song


class PlaylistSong(Base):
    __tablename__ = "playlist_songs"
    __table_args__ = (
        # Composite PK (playlist_id, position) for ordered tracks per spec
        {"comment": "Ordered playlist tracks; PK (playlist_id, position)"},
    )

    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    song_id: Mapped[int] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    playlist: Mapped["Playlist"] = relationship(
        "Playlist", back_populates="playlist_songs"
    )
    song: Mapped["Song"] = relationship("Song", back_populates="playlist_associations")

    def __repr__(self) -> str:
        return f"<PlaylistSong(playlist_id={self.playlist_id}, position={self.position}, song_id={self.song_id})>"
