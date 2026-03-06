"""
SQLAlchemy models for IMUSI.
Import Base and all models here so Alembic can discover them.
"""
from app.db.base import Base, IdCreatedUpdatedMixin
from app.models.artist import Artist
from app.models.album import Album
from app.models.song import Song
from app.models.folder import Folder
from app.models.folder_song import FolderSong
from app.models.playlist import Playlist
from app.models.playlist_song import PlaylistSong
from app.models.recently_played import RecentlyPlayed
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.import_job import ImportJob

__all__ = [
    "Base",
    "IdCreatedUpdatedMixin",
    "Artist",
    "Album",
    "Song",
    "Folder",
    "FolderSong",
    "Playlist",
    "PlaylistSong",
    "RecentlyPlayed",
    "User",
    "RefreshToken",
    "ImportJob",
]
