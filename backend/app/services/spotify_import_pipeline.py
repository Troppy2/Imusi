"""
Spotify-to-Local import pipeline orchestrator.
Fetches Spotify playlist metadata → searches YouTube for best match →
downloads audio → tags metadata → stores in /music/[Artist]/[Album]/ → inserts into DB.
"""
import json
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.db.session import SessionLocal
from app.models import Artist, Album, Song, Playlist, PlaylistSong
from app.models.import_job import ImportJob
from app.services.spotify_service import get_spotify_playlist_tracks
from app.services.youtube_service import search_youtube, download_audio, tag_audio_file

logger = get_logger(__name__)

# Thread pool for background download pipelines (max 1 concurrent to avoid hammering YouTube)
_download_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="spotify_dl")


def _get_or_create_artist(db: Session, name: str) -> Artist:
    stmt = select(Artist).where(Artist.name == name)
    artist = db.execute(stmt).scalar_one_or_none()
    if artist:
        return artist
    artist = Artist(name=name)
    db.add(artist)
    db.flush()
    return artist


def _get_or_create_album(
    db: Session, title: str, artist_id: int, artwork_path: str | None = None
) -> Album:
    stmt = select(Album).where(Album.title == title, Album.artist_id == artist_id)
    album = db.execute(stmt).scalar_one_or_none()
    if album:
        return album
    album = Album(title=title, artist_id=artist_id, artwork_path=artwork_path)
    db.add(album)
    db.flush()
    return album


def create_download_job(
    playlist_name: str,
    spotify_playlist_id: str,
) -> str:
    """Create a persistent download job record. Returns job_id."""
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        job = ImportJob(
            job_id=job_id,
            job_type="spotify_download",
            status="pending",
            folder_path=spotify_playlist_id,
            progress=0,
            total=0,
        )
        db.add(job)
        db.commit()
        logger.info("Download job created", extra={"job_id": job_id, "playlist": playlist_name})
    except Exception:
        db.rollback()
        logger.exception("Failed to create download job")
    finally:
        db.close()
    return job_id


def get_download_job_status(job_id: str) -> dict | None:
    """Get job status from DB."""
    db = SessionLocal()
    try:
        stmt = select(ImportJob).where(ImportJob.job_id == job_id)
        job = db.execute(stmt).scalar_one_or_none()
        if not job:
            return None
        return job.to_dict()
    finally:
        db.close()


def _update_job(db: Session, job_id: str, **kwargs) -> None:
    """Update a job record in the database."""
    stmt = select(ImportJob).where(ImportJob.job_id == job_id)
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()


def _run_download_pipeline_sync(
    job_id: str,
    access_token: str,
    spotify_playlist_id: str,
    playlist_name: str,
) -> None:
    """
    Background sync function that runs the full Spotify → YouTube → Local pipeline.
    Uses its own DB session.
    """
    import asyncio

    db = SessionLocal()
    try:
        # Mark job as running
        _update_job(db, job_id, status="running", started_at=datetime.now(timezone.utc))

        # Fetch tracks from Spotify (need to run async function in sync context)
        loop = asyncio.new_event_loop()
        try:
            tracks = loop.run_until_complete(
                get_spotify_playlist_tracks(access_token, spotify_playlist_id)
            )
        finally:
            loop.close()

        if not tracks:
            _update_job(db, job_id, status="failed", error="No tracks found in playlist")
            return

        _update_job(db, job_id, total=len(tracks))

        settings = get_settings()
        music_dir = Path(settings.MUSIC_DOWNLOAD_DIR).expanduser().resolve()

        # Create playlist record
        playlist = db.execute(
            select(Playlist).where(Playlist.name == playlist_name)
        ).scalar_one_or_none()
        if not playlist:
            playlist = Playlist(name=playlist_name)
            db.add(playlist)
            db.flush()

        results = {
            "downloaded": [],
            "failed": [],
            "skipped": [],
        }

        for idx, track in enumerate(tracks):
            try:
                title = track["title"]
                artist_name = track["artist"]
                album_name = track["album"]
                duration_ms = track.get("duration_ms", 0)
                artwork_url = track.get("artwork_url")

                # Check if we already have this track downloaded
                existing = db.execute(
                    select(Song).where(
                        Song.title == title,
                        Song.file_path.notlike("spotify:%"),
                    ).join(Artist, Artist.id == Song.artist_id).where(
                        Artist.name == artist_name,
                    )
                ).scalar_one_or_none()

                if existing:
                    # Already have a local copy — just link to playlist
                    _ensure_playlist_link(db, playlist.id, existing.id, idx + 1)
                    results["skipped"].append(title)
                    _update_job(db, job_id, progress=idx + 1)
                    continue

                # Search YouTube
                search_query = f"{artist_name} - {title} audio"
                candidates = search_youtube(search_query, expected_duration_ms=duration_ms)

                if not candidates:
                    logger.warning("No YouTube results for: %s", search_query)
                    results["failed"].append({"title": title, "reason": "no_youtube_results"})
                    _update_job(db, job_id, progress=idx + 1)
                    continue

                best = candidates[0]

                # Prepare output directory: /music/Artist/Album/
                safe_artist = _sanitize_dirname(artist_name)
                safe_album = _sanitize_dirname(album_name)
                track_dir = music_dir / safe_artist / safe_album
                track_dir.mkdir(parents=True, exist_ok=True)

                # Download
                safe_title = _sanitize_dirname(title)
                downloaded_path = download_audio(
                    youtube_url=best["url"],
                    output_dir=str(track_dir),
                    filename=safe_title,
                )

                if not downloaded_path:
                    results["failed"].append({"title": title, "reason": "download_failed"})
                    _update_job(db, job_id, progress=idx + 1)
                    continue

                # Tag metadata
                tag_audio_file(
                    file_path=downloaded_path,
                    title=title,
                    artist=artist_name,
                    album=album_name,
                    artwork_url=artwork_url,
                )

                # Insert into DB
                artist = _get_or_create_artist(db, artist_name)
                album = _get_or_create_album(db, album_name, artist.id, artwork_path=artwork_url)

                # Get file duration from the downloaded file
                file_duration = _get_file_duration(downloaded_path)

                song = Song(
                    title=title,
                    artist_id=artist.id,
                    album_id=album.id,
                    duration=file_duration if file_duration > 0 else (duration_ms / 1000.0),
                    file_path=str(Path(downloaded_path).resolve()),
                    file_format=Path(downloaded_path).suffix.lstrip('.').lower(),
                    artwork_path=artwork_url,
                )
                db.add(song)
                db.flush()

                _ensure_playlist_link(db, playlist.id, song.id, idx + 1)
                db.commit()

                results["downloaded"].append(title)
                _update_job(db, job_id, progress=idx + 1)

                logger.info(
                    "Downloaded track %d/%d: %s",
                    idx + 1,
                    len(tracks),
                    title,
                )

            except Exception as exc:
                db.rollback()
                logger.exception("Failed to process track: %s", track.get("title", "?"))
                results["failed"].append({
                    "title": track.get("title", "?"),
                    "reason": str(exc),
                })
                _update_job(db, job_id, progress=idx + 1)

        # Mark job complete
        _update_job(
            db,
            job_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            progress=len(tracks),
            result_json=json.dumps(results),
        )

        logger.info(
            "Spotify download pipeline complete",
            extra={
                "job_id": job_id,
                "downloaded": len(results["downloaded"]),
                "failed": len(results["failed"]),
                "skipped": len(results["skipped"]),
            },
        )

    except Exception as exc:
        db.rollback()
        logger.exception("Download pipeline failed", extra={"job_id": job_id})
        try:
            _update_job(db, job_id, status="failed", error=str(exc))
        except Exception:
            pass
    finally:
        db.close()


def _ensure_playlist_link(db: Session, playlist_id: int, song_id: int, position: int) -> None:
    """Add a song to a playlist if not already linked."""
    existing = db.execute(
        select(PlaylistSong).where(
            PlaylistSong.playlist_id == playlist_id,
            PlaylistSong.song_id == song_id,
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(PlaylistSong(playlist_id=playlist_id, song_id=song_id, position=position))
        db.flush()


def _sanitize_dirname(name: str) -> str:
    """Remove characters that are invalid in directory names."""
    import re
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    sanitized = sanitized.strip('. ')
    return sanitized or 'Unknown'


def _get_file_duration(file_path: str) -> float:
    """Get audio file duration in seconds using mutagen."""
    try:
        import mutagen
        audio = mutagen.File(file_path)
        if audio and audio.info:
            return float(audio.info.length)
    except Exception:
        pass
    return 0.0


def schedule_download_pipeline(
    job_id: str,
    access_token: str,
    spotify_playlist_id: str,
    playlist_name: str,
) -> None:
    """Schedule the download pipeline to run in a background thread."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_in_executor(
        _download_executor,
        _run_download_pipeline_sync,
        job_id,
        access_token,
        spotify_playlist_id,
        playlist_name,
    )
