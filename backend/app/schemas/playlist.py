"""
Playlist-related Pydantic schemas.
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.song import SongResponse


class PlaylistBase(BaseModel):
    name: str
    artwork_path: str | None = None


class PlaylistCreate(PlaylistBase):
    name: str | None = None


class PlaylistResponse(PlaylistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    song_count: int | None = None


class PlaylistUpdate(BaseModel):
    name: str | None = None
    artwork_path: str | None = None


class PlaylistSongAdd(BaseModel):
    """Body for adding a song to a playlist."""
    song_id: int
    position: int | None = None  # If omitted, append at end


class PlaylistResponseWithSongs(PlaylistResponse):
    """Playlist with ordered list of songs."""
    songs: list[SongResponse] = []
