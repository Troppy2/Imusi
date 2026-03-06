"""
Folder model: hierarchical folders for manual song groupings.
Relationships: self-referential parent/children, many-to-many with Song via FolderSong.
"""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdCreatedUpdatedMixin

if TYPE_CHECKING:
    from app.models.folder_song import FolderSong


class Folder(Base, IdCreatedUpdatedMixin):
    __tablename__ = "folders"

    name: Mapped[str] = mapped_column(String(512), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"), nullable=True, index=True
    )

    parent: Mapped["Folder | None"] = relationship(
        "Folder", remote_side="Folder.id", back_populates="children"
    )
    children: Mapped[list["Folder"]] = relationship(
        "Folder", back_populates="parent", cascade="all, delete-orphan"
    )
    folder_songs: Mapped[list["FolderSong"]] = relationship(
        "FolderSong", back_populates="folder", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Folder(id={self.id}, name={self.name!r})>"
