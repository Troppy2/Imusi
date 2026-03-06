# IMUSI Database Schema (SQLite)

## Core tables

- `artists`
- `albums`
- `songs`
- `folders`
- `folder_songs`
- `playlists`
- `playlist_songs`
- `recently_played`
- `users`
- `refresh_tokens`

## Key relationships

- `albums.artist_id -> artists.id`
- `songs.artist_id -> artists.id`
- `songs.album_id -> albums.id` (`SET NULL` on delete)
- `folder_songs.folder_id -> folders.id`
- `folder_songs.song_id -> songs.id`
- `playlist_songs.playlist_id -> playlists.id`
- `playlist_songs.song_id -> songs.id`
- `recently_played.song_id -> songs.id`
- `refresh_tokens.user_id -> users.id`

## Notes

- `playlist_songs` uses composite PK: `(playlist_id, position)` for ordered tracks.
- `songs.file_path` is unique.
- `songs.search_vector` is a nullable text helper field (optional denormalized search text).
- SQLite foreign keys are enabled via `PRAGMA foreign_keys=ON` in DB session setup.
- `users.email` is unique and indexed.
- `refresh_tokens` stores only SHA-256 token hashes (`token_hash`), never raw refresh tokens.
- `refresh_tokens` includes indexes for lookup by `user_id`, `expires_at`, and revocation checks.

## Migrations

```bash
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "description"
```
