"""
Song-related Pydantic schemas.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.artist import ArtistResponse
from app.schemas.album import AlbumResponse


class SongBase(BaseModel):
    title: str
    artist_id: int
    album_id: int | None = None
    duration: float = 0.0
    file_path: str
    track_number: int | None = None
    file_format: str = "mp3"
    artwork_path: str | None = None
    is_favorite: bool = False


class SongCreate(SongBase):
    pass


class SongResponse(SongBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class SongResponseWithRelations(SongResponse):
    """Song with nested artist and album for detail views."""
    artist: ArtistResponse | None = None
    album: AlbumResponse | None = None


class SongFavoriteUpdate(BaseModel):
    is_favorite: bool


class SongMetadataUpdate(BaseModel):
    title: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    artwork_path: str | None = None
