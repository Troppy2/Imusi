"""
Album-related Pydantic schemas.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.artist import ArtistResponse


class AlbumBase(BaseModel):
    title: str
    artist_id: int
    year: int | None = None
    artwork_path: str | None = None


class AlbumResponse(AlbumBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class AlbumResponseWithArtist(AlbumResponse):
    """Album with nested artist for detail views."""
    artist: ArtistResponse | None = None
