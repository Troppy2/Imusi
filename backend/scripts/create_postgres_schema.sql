-- =============================================================================
-- IMUSI PostgreSQL Schema
-- Run this manually if you want to create the schema without SQLAlchemy
-- Normally, the app auto-creates tables on startup via Base.metadata.create_all()
-- =============================================================================

CREATE TABLE IF NOT EXISTS artists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_artists_name ON artists(name);

CREATE TABLE IF NOT EXISTS albums (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    artist_id INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
    year INTEGER,
    artwork_path VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_albums_title ON albums(title);
CREATE INDEX IF NOT EXISTS ix_albums_artist_id ON albums(artist_id);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash VARCHAR(512),
    google_id VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    avatar_url VARCHAR(1024),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_google_id ON users(google_id);

CREATE TABLE IF NOT EXISTS songs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    artist_id INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
    album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
    track_number INTEGER,
    duration FLOAT NOT NULL DEFAULT 0.0,
    file_path VARCHAR(1024) NOT NULL UNIQUE,
    file_format VARCHAR(16) NOT NULL DEFAULT 'mp3',
    artwork_path VARCHAR(512),
    file_size INTEGER,
    bitrate INTEGER,
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    search_vector TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_songs_title ON songs(title);
CREATE INDEX IF NOT EXISTS ix_songs_artist_id ON songs(artist_id);
CREATE INDEX IF NOT EXISTS ix_songs_album_id ON songs(album_id);
CREATE INDEX IF NOT EXISTS ix_songs_is_favorite ON songs(is_favorite);
CREATE INDEX IF NOT EXISTS ix_songs_search_vector ON songs(search_vector);

CREATE TABLE IF NOT EXISTS folders (
    id SERIAL PRIMARY KEY,
    name VARCHAR(512) NOT NULL,
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_folders_parent_id ON folders(parent_id);

CREATE TABLE IF NOT EXISTS playlists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    artwork_path VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS folder_songs (
    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (folder_id, song_id)
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (playlist_id, position)
);

CREATE TABLE IF NOT EXISTS recently_played (
    id SERIAL PRIMARY KEY,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    played_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_recently_played_song_id ON recently_played(song_id);
CREATE INDEX IF NOT EXISTS ix_recently_played_played_at ON recently_played(played_at);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_revoked ON refresh_tokens(user_id, revoked);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_expires_at ON refresh_tokens(user_id, expires_at);
