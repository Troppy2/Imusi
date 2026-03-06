"""
Folders API: POST /folders, GET /folders (paginated), GET /folders/{id}, POST /folders/{id}/songs
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.pagination import PaginatedParams, PaginatedResponse, get_pagination_params
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.db.pagination_helper import paginate_query, build_paginated_response
from app.models import Folder, FolderSong, Song
from app.schemas.folder import FolderCreate, FolderResponse, FolderResponseWithSongs
from app.schemas.song import SongResponseWithRelations

router = APIRouter()


class AddSongToFolderBody(BaseModel):
    song_id: int


@router.post("", response_model=FolderResponse)
def create_folder(body: FolderCreate, db: Session = Depends(get_db)):
    """
    Create a new folder (optionally with parent_id for nesting).
    """
    folder = Folder(name=body.name, parent_id=body.parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("", response_model=PaginatedResponse[FolderResponse])
def list_folders(
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List folders with pagination.
    Example response: {"items": [...], "total": 5, "page": 1, "page_size": 20, "pages": 1}
    """
    total, items = paginate_query(
        db, Folder, pagination.page, pagination.page_size, order_by=Folder.id
    )
    return build_paginated_response(list(items), total, pagination)


@router.get("/{folder_id}", response_model=FolderResponseWithSongs)
def get_folder(folder_id: int, db: Session = Depends(get_db)):
    """
    Get folder by id with list of songs in it.
    """
    stmt = select(Folder).where(Folder.id == folder_id)
    folder = db.execute(stmt).scalar_one_or_none()
    if not folder:
        raise NotFoundError("Folder not found", resource="folder", resource_id=folder_id)
    songs = [fs.song for fs in folder.folder_songs]
    return FolderResponseWithSongs(
        **FolderResponse.model_validate(folder).model_dump(),
        songs=[s for s in songs if s is not None],
    )


@router.get("/{folder_id}/songs", response_model=PaginatedResponse[SongResponseWithRelations])
def get_folder_songs(
    folder_id: int,
    db: Session = Depends(get_db),
    pagination: PaginatedParams = Depends(get_pagination_params),
):
    """
    List songs in a folder with pagination.
    """
    folder_exists = db.execute(select(Folder.id).where(Folder.id == folder_id)).scalar_one_or_none()
    if not folder_exists:
        raise NotFoundError("Folder not found", resource="folder", resource_id=folder_id)

    total = (
        db.execute(
            select(func.count()).select_from(FolderSong).where(FolderSong.folder_id == folder_id)
        ).scalar_one_or_none()
        or 0
    )
    offset = (pagination.page - 1) * pagination.page_size
    stmt = (
        select(Song)
        .options(selectinload(Song.artist), selectinload(Song.album))
        .join(FolderSong, FolderSong.song_id == Song.id)
        .where(FolderSong.folder_id == folder_id)
        .order_by(FolderSong.added_at, Song.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = list(db.execute(stmt).scalars().all())
    return build_paginated_response(items, total, pagination)


@router.post("/{folder_id}/songs")
def add_song_to_folder(
    folder_id: int, body: AddSongToFolderBody, db: Session = Depends(get_db)
):
    """
    Add a song to a folder (many-to-many). Idempotent: if already linked, returns success.
    """
    folder = db.execute(select(Folder).where(Folder.id == folder_id)).scalar_one_or_none()
    if not folder:
        raise NotFoundError("Folder not found", resource="folder", resource_id=folder_id)
    song = db.execute(select(Song).where(Song.id == body.song_id)).scalar_one_or_none()
    if not song:
        raise NotFoundError("Song not found", resource="song", resource_id=body.song_id)
    existing = db.execute(
        select(FolderSong).where(
            FolderSong.folder_id == folder_id, FolderSong.song_id == body.song_id
        )
    ).scalar_one_or_none()
    if existing:
        return {"folder_id": folder_id, "song_id": body.song_id, "added": False}
    link = FolderSong(folder_id=folder_id, song_id=body.song_id)
    db.add(link)
    db.commit()
    return {"folder_id": folder_id, "song_id": body.song_id, "added": True}
