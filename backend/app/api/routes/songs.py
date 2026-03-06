"""
Songs API: GET /songs (paginated), GET /songs/{id}, PATCH metadata/favorite.
Business logic lives in services; routes only orchestrate and serialize.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.pagination import PaginatedParams, PaginatedResponse, get_pagination_params
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging_config import get_logger
from app.db.session import get_db
from app.db.pagination_helper import build_paginated_response
from app.models import Album, Artist, Song
from app.schemas.song import SongFavoriteUpdate, SongMetadataUpdate, SongResponseWithRelations

router = APIRouter()
logger = get_logger(__name__)


def _get_song_with_relations(db: Session, song_id: int) -> Song:
    stmt = (
        select(Song)
        .options(selectinload(Song.artist), selectinload(Song.album))
        .where(Song.id == song_id)
    )
    song = db.execute(stmt).scalar_one_or_none()
    if not song:
        raise NotFoundError("Song not found", resource="song", resource_id=song_id)
    return song


def _normalize_non_empty(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise BadRequestError(f"{field_name} cannot be empty", details={"field": field_name})
    return normalized


def _get_or_create_artist(db: Session, artist_name: str) -> Artist:
    stmt = select(Artist).where(func.lower(Artist.name) == artist_name.lower())
    artist = db.execute(stmt).scalar_one_or_none()
    if artist:
        return artist

    artist = Artist(name=artist_name)
    db.add(artist)
    db.flush()
    return artist


def _get_or_create_album(db: Session, album_name: str, artist_id: int) -> Album:
    stmt = select(Album).where(
        func.lower(Album.title) == album_name.lower(),
        Album.artist_id == artist_id,
    )
    album = db.execute(stmt).scalar_one_or_none()
    if album:
        return album

    album = Album(title=album_name, artist_id=artist_id)
    db.add(album)
    db.flush()
    return album


@router.get("", response_model=PaginatedResponse[SongResponseWithRelations])
def list_songs(
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
    favorites_only: bool = Query(default=False),
):
    """
    List songs with pagination.
    Example response: {"items": [...], "total": 42, "page": 1, "page_size": 20, "pages": 3}
    """
    total_stmt = select(func.count()).select_from(Song)
    if favorites_only:
        total_stmt = total_stmt.where(Song.is_favorite.is_(True))
    total = db.execute(total_stmt).scalar_one_or_none() or 0
    offset = (pagination.page - 1) * pagination.page_size
    stmt = select(Song).options(selectinload(Song.artist), selectinload(Song.album))
    if favorites_only:
        stmt = stmt.where(Song.is_favorite.is_(True))
    stmt = stmt.order_by(Song.id).offset(offset).limit(pagination.page_size)
    items = list(db.execute(stmt).scalars().all())
    return build_paginated_response(list(items), total, pagination)


@router.get("/{song_id}", response_model=SongResponseWithRelations)
def get_song(song_id: int, db: Session = Depends(get_db)):
    """
    Get a single song by id with artist and album nested.
    """
    return _get_song_with_relations(db, song_id)


@router.patch("/{song_id}/favorite", response_model=SongResponseWithRelations)
def update_song_favorite(song_id: int, body: SongFavoriteUpdate, db: Session = Depends(get_db)):
    song = _get_song_with_relations(db, song_id)
    song.is_favorite = body.is_favorite
    db.commit()
    return _get_song_with_relations(db, song_id)


@router.patch("/{song_id}/metadata", response_model=SongResponseWithRelations)
def update_song_metadata(song_id: int, body: SongMetadataUpdate, db: Session = Depends(get_db)):
    """
    Update editable metadata fields for a song.
    """
    song = _get_song_with_relations(db, song_id)
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return song

    if "title" in payload:
        song.title = _normalize_non_empty(payload.get("title"), "title") or song.title

    if "artist_name" in payload:
        artist_name = _normalize_non_empty(payload.get("artist_name"), "artist_name")
        if artist_name:
            artist = _get_or_create_artist(db, artist_name)
            song.artist_id = artist.id
            if "album_name" not in payload:
                song.album_id = None

    if "album_name" in payload:
        album_name_raw = payload.get("album_name")
        if album_name_raw is None:
            song.album_id = None
        else:
            album_name = album_name_raw.strip()
            if not album_name:
                song.album_id = None
            else:
                album = _get_or_create_album(db, album_name, song.artist_id)
                song.album_id = album.id

    if "artwork_path" in payload:
        artwork_path = payload.get("artwork_path")
        song.artwork_path = artwork_path.strip() if isinstance(artwork_path, str) and artwork_path.strip() else None

    db.commit()
    return _get_song_with_relations(db, song_id)
