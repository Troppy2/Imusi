"""
Search service: case-insensitive search across songs, artists, albums.
Returns structured result with songs, artists, albums lists.
"""
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Song, Artist, Album


def search(
    db: Session,
    q: str,
    limit_per_type: int = 20,
) -> dict[str, list]:
    """
    Search songs (title), artists (name), albums (title) using SQLAlchemy .ilike().
    Returns {"songs": [...], "artists": [...], "albums": [...]}.
    """
    pattern = f"%{q}%" if q else "%"

    songs_stmt = (
        select(Song)
        .options(selectinload(Song.artist), selectinload(Song.album))
        .where(Song.title.ilike(pattern))
        .limit(limit_per_type)
    )
    artists_stmt = (
        select(Artist)
        .where(Artist.name.ilike(pattern))
        .limit(limit_per_type)
    )
    albums_stmt = (
        select(Album)
        .options(selectinload(Album.artist))
        .where(Album.title.ilike(pattern))
        .limit(limit_per_type)
    )

    songs = list(db.execute(songs_stmt).scalars().all())
    artists = list(db.execute(artists_stmt).scalars().all())
    albums = list(db.execute(albums_stmt).scalars().all())

    return {"songs": songs, "artists": artists, "albums": albums}
