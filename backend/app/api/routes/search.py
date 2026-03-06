"""
Search API: GET /search?q=...
Returns songs, artists, albums matching the query (ILIKE).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.session import get_db
from app.services.search_service import search
from app.schemas.song import SongResponseWithRelations
from app.schemas.artist import ArtistResponse
from app.schemas.album import AlbumResponseWithArtist

router = APIRouter()
logger = get_logger(__name__)


@router.get("")
def search_all(
    q: str = "",
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    Search across songs (title), artists (name), albums (title).
    Example: GET /search?q=rock
    Example response: {"songs": [...], "artists": [...], "albums": [...]}
    """
    logger.info("Search requested", extra={"q": q, "limit": limit})
    result = search(db, q, limit_per_type=limit)
    return {
        "songs": [SongResponseWithRelations.model_validate(s) for s in result["songs"]],
        "artists": [ArtistResponse.model_validate(a) for a in result["artists"]],
        "albums": [AlbumResponseWithArtist.model_validate(a) for a in result["albums"]],
    }
