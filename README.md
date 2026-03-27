# IMUSI

A self-hosted music streaming app. Import your own music library, stream from your server, and import playlists from Spotify — all from a clean mobile interface.
* Side note: Theres some peak Clairo songs in songs/
## Architecture

```
Imusi/
├── backend/          # FastAPI REST API + SQLite/PostgreSQL
├── mobile/           # React Native (Expo) mobile app
└── songs/            # Drop music files here for auto-import
```

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, SQLite (dev) / PostgreSQL (prod)
**Mobile:** React Native 0.81, Expo 54, TypeScript, NativeWind (Tailwind), Zustand

## Features

- Stream your personal music library from any device
- Auto-import songs from a local directory (with file watcher)
- Browse by songs, albums, artists, playlists, and folders
- Full playback controls with queue management
- Search across your entire library
- Recently played tracking
- Spotify playlist import (metadata-only or full download via YouTube)
- JWT authentication with Google OAuth support
- Skeleton loading states and pull-to-refresh

## Quick Start

### Backend

```bash
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (defaults work for local dev)

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

Drop music files (MP3, FLAC, M4A, WAV, OGG, AAC) into the `songs/` directory and they'll be auto-imported on startup.

### Mobile

```bash
cd mobile

# Install dependencies
npm install

# Start Expo dev server
npx expo start
```

Scan the QR code with Expo Go, or build an APK:

```bash
# Development build (local backend)
eas build --platform android --profile development

# Preview build (cloud backend)
eas build --platform android --profile preview
```

## Environment Variables

### Backend (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./data/imusi.db` | Database connection string |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `JWT_SECRET` | — | Secret for signing access tokens |
| `JWT_REFRESH_SECRET` | — | Secret for signing refresh tokens |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID (optional) |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret (optional) |
| `SPOTIFY_CLIENT_ID` | — | Spotify OAuth client ID (optional) |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify OAuth client secret (optional) |
| `GLOBAL_SONGS_DIR` | `./songs` | Directory to auto-import music from |
| `MUSIC_DOWNLOAD_DIR` | `./music` | Where Spotify downloads are stored |
| `DOWNLOAD_AUDIO_FORMAT` | `mp3` | Audio format for downloads |
| `DOWNLOAD_AUDIO_QUALITY` | `192` | Audio quality in kbps |

### Mobile (via EAS build profiles)

| Variable | Description |
|----------|-------------|
| `EXPO_PUBLIC_API_URL` | Backend API base URL (set in `eas.json`) |
| `EXPO_PUBLIC_SPOTIFY_CLIENT_ID` | Spotify client ID for OAuth flow |

## API Endpoints

All endpoints are prefixed with `/api/v1`.

| Group | Endpoints |
|-------|-----------|
| **Auth** | `POST /auth/signup`, `POST /auth/login`, `POST /auth/google`, `POST /auth/refresh` |
| **Songs** | `GET /songs`, `GET /songs/:id`, `POST /songs/:id/favorite` |
| **Albums** | `GET /albums`, `GET /albums/:id` |
| **Artists** | `GET /artists`, `GET /artists/:id` |
| **Playlists** | `GET /playlists`, `POST /playlists`, `GET /playlists/:id`, `PUT /playlists/:id`, `DELETE /playlists/:id` |
| **Folders** | `GET /folders` |
| **Search** | `GET /search?q=...` |
| **Stream** | `GET /stream/:id` |
| **Recently Played** | `GET /recently-played`, `POST /recently-played` |
| **Import** | `POST /import/folder`, `GET /import/status/:job_id` |
| **Spotify** | `POST /spotify/auth/token`, `POST /spotify/auth/refresh`, `POST /spotify/playlists`, `POST /spotify/import`, `POST /spotify/download`, `GET /spotify/download/status/:job_id` |

## Spotify Integration

To enable Spotify import:

1. Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Add redirect URI: `imusi://` (matches the app's URL scheme)
3. Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in backend `.env`
4. Set `EXPO_PUBLIC_SPOTIFY_CLIENT_ID` in mobile environment

Two import modes:
- **Metadata import** — Creates playlist with track references (no audio files, instant)
- **Download pipeline** — Searches YouTube for each track, downloads audio, tags metadata, stores locally (background job)

## Project Structure

### Backend

```
backend/app/
├── api/routes/        # FastAPI route handlers
├── core/              # Config, security, logging, retry logic
├── db/                # SQLAlchemy session & base model
├── dependencies/      # FastAPI dependency injection (auth)
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic request/response schemas
├── services/          # Business logic (auth, import, search, Spotify, YouTube)
└── utils/             # Constants and helpers
```

### Mobile

```
mobile/src/
├── components/        # Reusable UI (SongCard, Artwork, Skeleton, MiniPlayer, etc.)
├── config/            # API configuration
├── hooks/             # Custom hooks (useSyncPlayer)
├── navigation/        # React Navigation (tabs + stack)
├── screens/           # Screen components (Home, Songs, Player, SpotifyImport, etc.)
├── services/          # API client, auth, player, Spotify service
├── store/             # Zustand stores (player, auth, account, pinned)
├── types/             # TypeScript type definitions
└── utils/             # Helpers (formatDuration, shuffle, debounce)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile Framework | React Native 0.81 + Expo 54 |
| Styling | NativeWind (Tailwind CSS) |
| State Management | Zustand |
| Navigation | React Navigation 7 |
| Audio Playback | expo-av |
| Animations | react-native-reanimated |
| HTTP Client | Axios (with JWT interceptor) |
| Backend Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT + Argon2 password hashing |
| Audio Metadata | mutagen |
| YouTube Downloads | yt-dlp |
| Deployment | Render (backend), EAS Build (mobile) |

## License

Private project.
