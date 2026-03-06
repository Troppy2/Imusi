"""
Stream API: GET /stream/{song_id}
Serves audio files with Range request support for mobile streaming.
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from app.db.session import get_db
from app.models import Song, RecentlyPlayed

router = APIRouter()
logger = get_logger(__name__)

MIME_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
}


@router.get("/{song_id}")
def stream_song(song_id: int, db: Session = Depends(get_db)):
    """Stream an audio file by song ID. Supports HTTP Range requests."""
    stmt = select(Song).where(Song.id == song_id)
    song = db.execute(stmt).scalar_one_or_none()
    if not song:
        raise NotFoundError("Song not found", resource="song", resource_id=song_id)

    file_path = Path(song.file_path)
    if not file_path.is_file():
        raise NotFoundError("Audio file not found on disk", resource="file", resource_id=song_id)

    # Track play history for home recommendations/recently-played UI.
    try:
        db.add(RecentlyPlayed(song_id=song.id))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to persist recently played event", extra={"song_id": song_id})

    media_type = MIME_TYPES.get(song.file_format, "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )
