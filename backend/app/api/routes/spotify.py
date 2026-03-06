"""
Spotify integration routes: OAuth token exchange, list playlists, import playlist metadata,
and download playlist tracks as local audio files.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging_config import get_logger
from app.db.session import get_db
from app.models import Artist, Album, Playlist, PlaylistSong, Song
from app.services.spotify_service import (
    exchange_spotify_code,
    get_spotify_playlists,
    get_spotify_playlist_tracks,
    refresh_spotify_token,
)
from app.services.spotify_import_pipeline import (
    create_download_job,
    get_download_job_status,
    schedule_download_pipeline,
)

logger = get_logger(__name__)
router = APIRouter()


class SpotifyAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class SpotifyTokenRefreshRequest(BaseModel):
    refresh_token: str


class SpotifyImportRequest(BaseModel):
    access_token: str
    spotify_playlist_id: str
    playlist_name: str
    artwork_url: str | None = None


class SpotifyListRequest(BaseModel):
    access_token: str


class SpotifyDownloadRequest(BaseModel):
    """Request body to start downloading a Spotify playlist as local audio files."""
    access_token: str
    spotify_playlist_id: str
    playlist_name: str


@router.post("/auth/token")
async def spotify_token_exchange(body: SpotifyAuthRequest):
    """Exchange a Spotify authorization code for access + refresh tokens."""
    try:
        tokens = await exchange_spotify_code(body.code, body.redirect_uri)
        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type"),
        }
    except Exception as exc:
        logger.warning("Spotify token exchange failed: %s", exc)
        raise BadRequestError("Failed to authenticate with Spotify") from exc


@router.post("/auth/refresh")
async def spotify_token_refresh(body: SpotifyTokenRefreshRequest):
    """Refresh a Spotify access token."""
    try:
        tokens = await refresh_spotify_token(body.refresh_token)
        return {
            "access_token": tokens.get("access_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type"),
        }
    except Exception as exc:
        logger.warning("Spotify token refresh failed: %s", exc)
        raise BadRequestError("Failed to refresh Spotify token") from exc


@router.post("/playlists")
async def list_spotify_playlists(body: SpotifyListRequest):
    """List the user's Spotify playlists."""
    try:
        playlists = await get_spotify_playlists(body.access_token)
        return {"playlists": playlists}
    except Exception as exc:
        logger.warning("Spotify playlist fetch failed: %s", exc)
        raise BadRequestError("Failed to fetch Spotify playlists") from exc


@router.post("/import")
async def import_spotify_playlist(body: SpotifyImportRequest, db: Session = Depends(get_db)):
    """
    Import a Spotify playlist into the Imusi database.
    Creates playlist, artists, albums, and song references.
    Songs are metadata-only (no audio files) with a spotify: file_path marker.
    """
    try:
        tracks = await get_spotify_playlist_tracks(body.access_token, body.spotify_playlist_id)
    except Exception as exc:
        logger.warning("Spotify track fetch failed: %s", exc)
        raise BadRequestError("Failed to fetch playlist tracks from Spotify") from exc

    if not tracks:
        raise BadRequestError("Playlist is empty or could not be read")

    # Check for duplicate import by looking for playlists with the same name
    # that already have spotify-sourced songs
    existing_playlist = db.execute(
        select(Playlist).where(Playlist.name == body.playlist_name)
    ).scalar_one_or_none()

    if existing_playlist:
        # Check if it has spotify tracks already
        spotify_song_count = db.execute(
            select(func.count())
            .select_from(PlaylistSong)
            .join(Song, Song.id == PlaylistSong.song_id)
            .where(
                PlaylistSong.playlist_id == existing_playlist.id,
                Song.file_path.like("spotify:%"),
            )
        ).scalar_one_or_none() or 0

        if spotify_song_count > 0:
            return {
                "playlist_id": existing_playlist.id,
                "imported_count": 0,
                "skipped": True,
                "message": f"Playlist '{body.playlist_name}' was already imported",
            }

    # Create the playlist
    playlist = Playlist(name=body.playlist_name, artwork_path=body.artwork_url)
    db.add(playlist)
    db.flush()

    imported_count = 0
    for position, track in enumerate(tracks, start=1):
        spotify_file_path = f"spotify:{track['spotify_track_id']}"

        # Find or create artist
        artist_name = track["artist"]
        artist = db.execute(
            select(Artist).where(Artist.name == artist_name)
        ).scalar_one_or_none()
        if not artist:
            artist = Artist(name=artist_name)
            db.add(artist)
            db.flush()

        # Find or create album
        album_name = track["album"]
        album = db.execute(
            select(Album).where(Album.title == album_name, Album.artist_id == artist.id)
        ).scalar_one_or_none()
        if not album:
            album = Album(
                title=album_name,
                artist_id=artist.id,
                artwork_path=track.get("artwork_url"),
            )
            db.add(album)
            db.flush()

        # Find or create song (keyed by spotify file_path)
        song = db.execute(
            select(Song).where(Song.file_path == spotify_file_path)
        ).scalar_one_or_none()
        if not song:
            song = Song(
                title=track["title"],
                artist_id=artist.id,
                album_id=album.id,
                duration=track["duration_ms"] / 1000.0,
                file_path=spotify_file_path,
                file_format="spotify",
                artwork_path=track.get("artwork_url"),
            )
            db.add(song)
            db.flush()

        # Add to playlist (skip if already there)
        existing_link = db.execute(
            select(PlaylistSong).where(
                PlaylistSong.playlist_id == playlist.id,
                PlaylistSong.song_id == song.id,
            )
        ).scalar_one_or_none()
        if not existing_link:
            db.add(PlaylistSong(playlist_id=playlist.id, song_id=song.id, position=position))
            imported_count += 1

    db.commit()
    db.refresh(playlist)

    logger.info(
        "Spotify playlist imported: %s (%d tracks)",
        body.playlist_name,
        imported_count,
    )

    return {
        "playlist_id": playlist.id,
        "imported_count": imported_count,
        "skipped": False,
        "message": f"Imported {imported_count} tracks into '{body.playlist_name}'",
    }


# ─── Spotify-to-Local Download Pipeline ─────────────────────────────────────


@router.post("/download")
async def start_spotify_download(body: SpotifyDownloadRequest):
    """
    Start downloading a Spotify playlist as local audio files.
    Returns 202 Accepted with a job_id for polling progress.
    Pipeline: Spotify metadata → YouTube search → audio download → metadata tagging → DB insert.
    """
    if not body.access_token or not body.spotify_playlist_id:
        raise BadRequestError("access_token and spotify_playlist_id are required")

    job_id = create_download_job(body.playlist_name, body.spotify_playlist_id)
    schedule_download_pipeline(
        job_id=job_id,
        access_token=body.access_token,
        spotify_playlist_id=body.spotify_playlist_id,
        playlist_name=body.playlist_name,
    )

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "accepted",
            "message": f"Download pipeline started for '{body.playlist_name}'. Poll /spotify/download/status/{job_id} for progress.",
        },
    )


@router.get("/download/status/{job_id}")
def get_spotify_download_status(job_id: str):
    """
    Get the status and progress of a Spotify download job.
    Returns 404 if job_id is unknown.
    """
    job = get_download_job_status(job_id)
    if not job:
        raise NotFoundError("Download job not found", resource="download_job", resource_id=job_id)
    return job
