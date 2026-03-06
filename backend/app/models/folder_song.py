"""
FolderSong: join table between Folder and Song.
Composite PK (folder_id, song_id). Tracks added_at for display/sync.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FolderSong(Base):
    __tablename__ = "folder_songs"
    __table_args__ = (
        # Composite PK per spec
        {"comment": "Join table: folder_id + song_id unique per folder"},
    )

    folder_id: Mapped[int] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"), primary_key=True
    )
    song_id: Mapped[int] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    folder: Mapped["Folder"] = relationship("Folder", back_populates="folder_songs")
    song: Mapped["Song"] = relationship("Song", back_populates="folder_associations")

    def __repr__(self) -> str:
        return f"<FolderSong(folder_id={self.folder_id}, song_id={self.song_id})>"
