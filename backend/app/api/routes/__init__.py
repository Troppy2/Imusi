"""
API route modules.
Routes delegate to services; no business logic in handlers.
"""
from fastapi import APIRouter

from app.api.routes import (
    auth_routes,
    songs,
    artists,
    albums,
    import_routes,
    folders,
    playlists,
    recently_played,
    search,
    spotify,
    stream,
)

api_router = APIRouter()

api_router.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])
api_router.include_router(songs.router, prefix="/songs", tags=["songs"])
api_router.include_router(artists.router, prefix="/artists", tags=["artists"])
api_router.include_router(albums.router, prefix="/albums", tags=["albums"])
api_router.include_router(import_routes.router, prefix="/import", tags=["import"])
api_router.include_router(folders.router, prefix="/folders", tags=["folders"])
api_router.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
api_router.include_router(recently_played.router, prefix="/recently-played", tags=["recently-played"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(spotify.router, prefix="/spotify", tags=["spotify"])
