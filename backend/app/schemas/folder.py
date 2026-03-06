"""
Folder-related Pydantic schemas.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.song import SongResponse


class FolderBase(BaseModel):
    name: str
    parent_id: int | None = None


class FolderCreate(FolderBase):
    pass


class FolderResponse(FolderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class FolderResponseWithChildren(FolderResponse):
    """Folder with nested children (tree view)."""
    children: list["FolderResponseWithChildren"] = []


class FolderResponseWithSongs(FolderResponse):
    """Folder with list of songs (for folder detail)."""
    songs: list[SongResponse] = []


# Allow recursive model
FolderResponseWithChildren.model_rebuild()
