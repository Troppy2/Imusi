"""
Recently played API.
Provides a compact overview for home-screen sections.
"""
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import RecentlyPlayed, Song, Album, PlaylistSong
from app.schemas.artist import ArtistResponse
from app.schemas.album import AlbumResponseWithArtist
from app.schemas.playlist import PlaylistResponse
from app.schemas.song import SongResponseWithRelations

router = APIRouter()


class RecentlyPlayedOverview(BaseModel):
    songs: list[SongResponseWithRelations]
    artists: list[ArtistResponse]
    albums: list[AlbumResponseWithArtist]
    playlists: list[PlaylistResponse]


@router.get("/overview", response_model=RecentlyPlayedOverview)
def get_recently_played_overview(
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Return recent songs plus deduplicated artists, albums, and playlists.
    """
    stmt = (
        select(RecentlyPlayed)
        .options(
            selectinload(RecentlyPlayed.song)
            .selectinload(Song.artist),
            selectinload(RecentlyPlayed.song)
            .selectinload(Song.album)
            .selectinload(Album.artist),
            selectinload(RecentlyPlayed.song)
            .selectinload(Song.playlist_associations)
            .selectinload(PlaylistSong.playlist),
        )
        .order_by(RecentlyPlayed.played_at.desc())
        .limit(limit * 25)
    )
    rows = list(db.execute(stmt).scalars().all())

    songs = []
    artists = []
    albums = []
    playlists = []
    seen_song_ids: set[int] = set()
    seen_artist_ids: set[int] = set()
    seen_album_ids: set[int] = set()
    seen_playlist_ids: set[int] = set()

    for entry in rows:
        song = entry.song
        if song is None:
            continue

        if song.id not in seen_song_ids and len(songs) < limit:
            songs.append(song)
            seen_song_ids.add(song.id)

        if song.artist and song.artist.id not in seen_artist_ids and len(artists) < limit:
            artists.append(song.artist)
            seen_artist_ids.add(song.artist.id)

        if song.album and song.album.id not in seen_album_ids and len(albums) < limit:
            albums.append(song.album)
            seen_album_ids.add(song.album.id)

        for assoc in song.playlist_associations:
            playlist = assoc.playlist
            if playlist and playlist.id not in seen_playlist_ids and len(playlists) < limit:
                playlists.append(playlist)
                seen_playlist_ids.add(playlist.id)
                break

        if (
            len(songs) >= limit
            and len(artists) >= limit
            and len(albums) >= limit
            and len(playlists) >= limit
        ):
            break

    return RecentlyPlayedOverview(
        songs=[SongResponseWithRelations.model_validate(s) for s in songs],
        artists=[ArtistResponse.model_validate(a) for a in artists],
        albums=[AlbumResponseWithArtist.model_validate(a) for a in albums],
        playlists=[PlaylistResponse.model_validate(p) for p in playlists],
    )
