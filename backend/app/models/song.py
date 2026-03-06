"""
Song model: represents a single audio file.
Indexed on title, artist_id, album_id. file_path unique.
Optional search_vector helper column for denormalized search text.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdCreatedUpdatedMixin

if TYPE_CHECKING:
    from app.models.artist import Artist
    from app.models.album import Album
    from app.models.folder import Folder
    from app.models.playlist import Playlist
    from app.models.recently_played import RecentlyPlayed


class Song(Base, IdCreatedUpdatedMixin):
    __tablename__ = "songs"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    artist_id: Mapped[int] = mapped_column(
        ForeignKey("artists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    album_id: Mapped[int | None] = mapped_column(
        ForeignKey("albums.id", ondelete="SET NULL"), nullable=True, index=True
    )
    track_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # seconds
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False, default="mp3")
    artwork_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)  # kbps
    imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Search helper column (optional denormalized text)
    search_vector: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    artist: Mapped["Artist"] = relationship("Artist", back_populates="songs")
    album: Mapped["Album | None"] = relationship("Album", back_populates="songs")
    folder_associations: Mapped[list["FolderSong"]] = relationship(
        "FolderSong", back_populates="song", cascade="all, delete-orphan"
    )
    playlist_associations: Mapped[list["PlaylistSong"]] = relationship(
        "PlaylistSong", back_populates="song", cascade="all, delete-orphan"
    )
    recently_played_entries: Mapped[list["RecentlyPlayed"]] = relationship(
        "RecentlyPlayed", back_populates="song", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Song(id={self.id}, title={self.title!r})>"
