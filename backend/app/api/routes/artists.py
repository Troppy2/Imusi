"""
Artists API: GET /artists (paginated), GET /artists/{id}
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func

from app.core.pagination import PaginatedParams, PaginatedResponse, get_pagination_params
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.db.pagination_helper import paginate_query, build_paginated_response
from app.models import Artist, Song
from app.schemas.artist import ArtistResponse
from app.schemas.song import SongResponseWithRelations

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ArtistResponse])
def list_artists(
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List artists with pagination.
    Example response: {"items": [...], "total": 10, "page": 1, "page_size": 20, "pages": 1}
    """
    total, items = paginate_query(
        db, Artist, pagination.page, pagination.page_size, order_by=Artist.id
    )
    return build_paginated_response(list(items), total, pagination)


@router.get("/{artist_id}", response_model=ArtistResponse)
def get_artist(artist_id: int, db: Session = Depends(get_db)):
    """
    Get a single artist by id.
    """
    stmt = select(Artist).where(Artist.id == artist_id)
    artist = db.execute(stmt).scalar_one_or_none()
    if not artist:
        raise NotFoundError("Artist not found", resource="artist", resource_id=artist_id)
    return artist


@router.get("/{artist_id}/songs", response_model=PaginatedResponse[SongResponseWithRelations])
def get_artist_songs(
    artist_id: int,
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List songs for an artist with pagination.
    """
    artist_exists = db.execute(select(Artist.id).where(Artist.id == artist_id)).scalar_one_or_none()
    if not artist_exists:
        raise NotFoundError("Artist not found", resource="artist", resource_id=artist_id)

    total = (
        db.execute(select(func.count()).select_from(Song).where(Song.artist_id == artist_id)).scalar_one_or_none()
        or 0
    )
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Song)
        .options(selectinload(Song.artist), selectinload(Song.album))
        .where(Song.artist_id == artist_id)
        .order_by(Song.track_number, Song.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return build_paginated_response(items, total, pagination)
