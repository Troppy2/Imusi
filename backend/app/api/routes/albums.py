"""
Albums API: GET /albums (paginated), GET /albums/{id}
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func

from app.core.pagination import PaginatedParams, PaginatedResponse, get_pagination_params
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.db.pagination_helper import build_paginated_response
from app.models import Album, Song
from app.schemas.album import AlbumResponseWithArtist
from app.schemas.song import SongResponseWithRelations

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AlbumResponseWithArtist])
def list_albums(
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List albums with pagination.
    Example response: {"items": [...], "total": 15, "page": 1, "page_size": 20, "pages": 1}
    """
    total = db.execute(select(func.count()).select_from(Album)).scalar_one_or_none() or 0
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Album)
        .options(selectinload(Album.artist))
        .order_by(Album.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return build_paginated_response(list(items), total, pagination)


@router.get("/{album_id}", response_model=AlbumResponseWithArtist)
def get_album(album_id: int, db: Session = Depends(get_db)):
    """
    Get a single album by id with nested artist.
    """
    stmt = select(Album).options(selectinload(Album.artist)).where(Album.id == album_id)
    album = db.execute(stmt).scalar_one_or_none()
    if not album:
        raise NotFoundError("Album not found", resource="album", resource_id=album_id)
    return album


@router.get("/{album_id}/songs", response_model=PaginatedResponse[SongResponseWithRelations])
def get_album_songs(
    album_id: int,
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List songs in an album with pagination.
    """
    album_exists = db.execute(select(Album.id).where(Album.id == album_id)).scalar_one_or_none()
    if not album_exists:
        raise NotFoundError("Album not found", resource="album", resource_id=album_id)

    total = (
        db.execute(select(func.count()).select_from(Song).where(Song.album_id == album_id)).scalar_one_or_none()
        or 0
    )
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Song)
        .options(selectinload(Song.artist), selectinload(Song.album))
        .where(Song.album_id == album_id)
        .order_by(Song.track_number, Song.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return build_paginated_response(items, total, pagination)
