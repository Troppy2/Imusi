"""
RecentlyPlayed: listening history for a song.
Index on played_at for "recently played" queries and pruning old entries.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecentlyPlayed(Base):
    __tablename__ = "recently_played"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    song_id: Mapped[int] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    song: Mapped["Song"] = relationship("Song", back_populates="recently_played_entries")

    def __repr__(self) -> str:
        return f"<RecentlyPlayed(id={self.id}, song_id={self.song_id}, played_at={self.played_at})>"
