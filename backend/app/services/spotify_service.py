"""
Spotify API integration service.
Handles OAuth token exchange and playlist fetching from the Spotify Web API.
All HTTP calls use retry with exponential backoff for resilience.
"""
import httpx

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.core.retry import async_retry

logger = get_logger(__name__)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


@async_retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0, retryable_exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException))
async def exchange_spotify_code(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for Spotify access + refresh tokens."""
    settings = get_settings()
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise ValueError("Spotify client credentials not configured")

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.SPOTIFY_CLIENT_ID,
                "client_secret": settings.SPOTIFY_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected response format from Spotify token endpoint")
        return data


@async_retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0, retryable_exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException))
async def refresh_spotify_token(refresh_token: str) -> dict:
    """Refresh a Spotify access token."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.SPOTIFY_CLIENT_ID,
                "client_secret": settings.SPOTIFY_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected response format from Spotify token endpoint")
        return data


@async_retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0, retryable_exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException))
async def get_spotify_playlists(access_token: str) -> list[dict]:
    """Fetch the current user's playlists from Spotify."""
    playlists: list[dict] = []
    url = f"{SPOTIFY_API_BASE}/me/playlists?limit=50"

    async with httpx.AsyncClient(timeout=15) as client:
        while url:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                break
            for item in data.get("items", []):
                if not item:
                    continue
                images = item.get("images", [])
                playlists.append({
                    "spotify_id": item.get("id", ""),
                    "name": item.get("name", "Untitled"),
                    "description": item.get("description"),
                    "image_url": images[0]["url"] if images else None,
                    "track_count": item.get("tracks", {}).get("total", 0),
                    "owner": item.get("owner", {}).get("display_name"),
                })
            url = data.get("next")

    return playlists


@async_retry(max_attempts=3, base_delay=1.0, backoff_factor=2.0, retryable_exceptions=(httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException))
async def get_spotify_playlist_tracks(access_token: str, playlist_id: str) -> list[dict]:
    """Fetch all tracks from a Spotify playlist."""
    tracks: list[dict] = []
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks?limit=100&fields=items(track(id,name,duration_ms,artists(name),album(name,images))),next"

    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                break
            for item in data.get("items", []):
                track = item.get("track") if item else None
                if not track or not track.get("id"):
                    continue
                album = track.get("album", {})
                album_images = album.get("images", [])
                artists = track.get("artists", [])
                tracks.append({
                    "spotify_track_id": track["id"],
                    "title": track.get("name", "Unknown"),
                    "artist": artists[0]["name"] if artists else "Unknown Artist",
                    "album": album.get("name", "Unknown Album"),
                    "duration_ms": track.get("duration_ms", 0),
                    "artwork_url": album_images[0]["url"] if album_images else None,
                })

            url = data.get("next")

    return tracks
