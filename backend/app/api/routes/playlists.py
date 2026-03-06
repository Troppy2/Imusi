"""
Playlists API: POST /playlists, GET /playlists (paginated), GET /playlists/{id}, POST /playlists/{id}/songs
"""
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func

from app.core.pagination import PaginatedParams, PaginatedResponse, get_pagination_params
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.db.pagination_helper import paginate_query, build_paginated_response
from app.models import Album, Playlist, PlaylistSong, Song
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistResponse,
    PlaylistResponseWithSongs,
    PlaylistSongAdd,
    PlaylistUpdate,
)
from app.schemas.song import SongResponseWithRelations

router = APIRouter()
DEFAULT_PLAYLIST_PREFIX = "Playlist #"
DEFAULT_PLAYLIST_RE = re.compile(r"^Playlist #(\d{3})$")


def _normalize_playlist_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    return value


def _next_default_playlist_name(db: Session) -> str:
    names = db.execute(select(Playlist.name).where(Playlist.name.like(f"{DEFAULT_PLAYLIST_PREFIX}%"))).scalars().all()
    max_number = 0
    for name in names:
        match = DEFAULT_PLAYLIST_RE.match(name or "")
        if not match:
            continue
        max_number = max(max_number, int(match.group(1)))
    return f"{DEFAULT_PLAYLIST_PREFIX}{max_number + 1:03d}"


def _playlist_song_count(db: Session, playlist_id: int) -> int:
    return (
        db.execute(
            select(func.count()).select_from(PlaylistSong).where(PlaylistSong.playlist_id == playlist_id)
        ).scalar_one_or_none()
        or 0
    )


@router.post("", response_model=PlaylistResponse)
def create_playlist(body: PlaylistCreate, db: Session = Depends(get_db)):
    """
    Create a new playlist.
    """
    name = _normalize_playlist_name(body.name)
    if not name:
        name = _next_default_playlist_name(db)
    playlist = Playlist(name=name, artwork_path=body.artwork_path)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return PlaylistResponse(
        **PlaylistResponse.model_validate(playlist).model_dump(),
        song_count=0,
    )


@router.get("", response_model=PaginatedResponse[PlaylistResponse])
def list_playlists(
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List playlists with pagination.
    Example response: {"items": [...], "total": 3, "page": 1, "page_size": 20, "pages": 1}
    """
    total, items = paginate_query(
        db, Playlist, pagination.page, pagination.page_size, order_by=Playlist.id
    )
    playlist_ids = [playlist.id for playlist in items]
    song_counts: dict[int, int] = {}
    if playlist_ids:
        rows = db.execute(
            select(PlaylistSong.playlist_id, func.count())
            .where(PlaylistSong.playlist_id.in_(playlist_ids))
            .group_by(PlaylistSong.playlist_id)
        ).all()
        song_counts = {playlist_id: count for playlist_id, count in rows}

    payload = [
        PlaylistResponse(
            **PlaylistResponse.model_validate(playlist).model_dump(),
            song_count=song_counts.get(playlist.id, 0),
        )
        for playlist in items
    ]
    return build_paginated_response(payload, total, pagination)


@router.get("/{playlist_id}", response_model=PlaylistResponseWithSongs)
def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """
    Get playlist by id with ordered list of songs.
    """
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    playlist = db.execute(stmt).scalar_one_or_none()
    if not playlist:
        raise NotFoundError("Playlist not found", resource="playlist", resource_id=playlist_id)
    songs = [ps.song for ps in playlist.playlist_songs if ps.song]
    return PlaylistResponseWithSongs(
        **PlaylistResponse.model_validate(playlist).model_dump(),
        song_count=len(songs),
        songs=songs,
    )


@router.patch("/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(playlist_id: int, body: PlaylistUpdate, db: Session = Depends(get_db)):
    playlist = db.execute(select(Playlist).where(Playlist.id == playlist_id)).scalar_one_or_none()
    if not playlist:
        raise NotFoundError("Playlist not found", resource="playlist", resource_id=playlist_id)

    payload = body.model_dump(exclude_unset=True)
    if "name" in payload:
        normalized = _normalize_playlist_name(payload["name"])
        if not normalized:
            raise BadRequestError("Playlist name cannot be empty", details={"field": "name"})
        playlist.name = normalized

    if "artwork_path" in payload:
        artwork = payload["artwork_path"]
        playlist.artwork_path = artwork.strip() if isinstance(artwork, str) and artwork.strip() else None

    db.commit()
    db.refresh(playlist)
    return PlaylistResponse(
        **PlaylistResponse.model_validate(playlist).model_dump(),
        song_count=_playlist_song_count(db, playlist.id),
    )


@router.get("/{playlist_id}/songs", response_model=PaginatedResponse[SongResponseWithRelations])
def get_playlist_songs(
    playlist_id: int,
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List songs in a playlist with pagination, preserving playlist order.
    """
    playlist_exists = db.execute(select(Playlist.id).where(Playlist.id == playlist_id)).scalar_one_or_none()
    if not playlist_exists:
        raise NotFoundError("Playlist not found", resource="playlist", resource_id=playlist_id)

    total = (
        db.execute(
            select(func.count()).select_from(PlaylistSong).where(PlaylistSong.playlist_id == playlist_id)
        ).scalar_one_or_none()
        or 0
    )
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Song)
        .options(selectinload(Song.artist), selectinload(Song.album))
        .join(PlaylistSong, PlaylistSong.song_id == Song.id)
        .where(PlaylistSong.playlist_id == playlist_id)
        .order_by(PlaylistSong.position)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return build_paginated_response(items, total, pagination)


@router.post("/{playlist_id}/songs")
def add_song_to_playlist(
    playlist_id: int, body: PlaylistSongAdd, db: Session = Depends(get_db)
):
    """
    Add a song to a playlist with optional position. If position omitted, append at end.
    """
    playlist = db.execute(
        select(Playlist).where(Playlist.id == playlist_id)
    ).scalar_one_or_none()
    if not playlist:
        raise NotFoundError("Playlist not found", resource="playlist", resource_id=playlist_id)
    song = db.execute(
        select(Song)
        .options(selectinload(Song.album))
        .where(Song.id == body.song_id)
    ).scalar_one_or_none()
    if not song:
        raise NotFoundError("Song not found", resource="song", resource_id=body.song_id)
    if body.position is not None:
        position = body.position
    else:
        max_pos = db.execute(
            select(func.coalesce(func.max(PlaylistSong.position), 0)).where(
                PlaylistSong.playlist_id == playlist_id
            )
        ).scalar_one_or_none() or 0
        position = max_pos + 1
    existing = db.execute(
        select(PlaylistSong).where(
            PlaylistSong.playlist_id == playlist_id, PlaylistSong.song_id == body.song_id
        )
    ).scalar_one_or_none()
    if existing:
        return {"playlist_id": playlist_id, "song_id": body.song_id, "position": existing.position}
    link = PlaylistSong(playlist_id=playlist_id, song_id=body.song_id, position=position)
    db.add(link)

    if not playlist.artwork_path:
        album_artwork = song.album.artwork_path if isinstance(song.album, Album) else None
        playlist.artwork_path = song.artwork_path or album_artwork

    db.commit()
    db.refresh(link)
    return {"playlist_id": playlist_id, "song_id": body.song_id, "position": position}
