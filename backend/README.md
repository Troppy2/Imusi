# IMUSI Backend

Backend API for IMUSI (local music player), using FastAPI + SQLAlchemy + Alembic with SQLite.

## Stack

- FastAPI
- SQLite
- SQLAlchemy 2.0
- Alembic
- Pydantic
- mutagen
- Passlib (Argon2/bcrypt)
- PyJWT

## Run locally

1. Install dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Optional `.env` override:

```env
DATABASE_URL=sqlite:///C:/path/to/imusi.db
JWT_SECRET=replace-with-32-plus-char-random-secret
JWT_REFRESH_SECRET=replace-with-different-32-plus-char-random-secret
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

Default database path is `backend/data/imusi.db`.
See `backend/.env.example` for all auth/security settings.

3. Run migrations:

```bash
alembic upgrade head
```

4. Start API:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Docs: `http://localhost:8000/docs`

## Docker

```bash
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

`docker-compose.yml` mounts `./data` into `/app/data`, so the SQLite DB persists on the host.

## Migrations

- Apply all: `alembic upgrade head`
- Rollback one: `alembic downgrade -1`
- Create new: `alembic revision --autogenerate -m "description"`

## Authentication API

Base path: `/api/v1/auth`

- `POST /signup` -> email/password account creation + tokens
- `POST /login` -> email/password login + tokens
- `POST /google` -> Google OAuth code exchange + tokens
- `POST /refresh` -> refresh token rotation + new access token
- `POST /logout` -> revoke refresh token
- `GET /me` -> current user (Bearer required)

### Security defaults

- Password hashing: Argon2 (with bcrypt fallback via Passlib)
- Access token lifetime: 15 minutes
- Refresh token lifetime: 30 days (configurable)
- Refresh token storage: SHA-256 hash only
- Auth brute-force protection: 5 attempts/minute per IP for auth endpoints
- Non-auth API routes require Bearer access token

Detailed architecture and flow guide: `backend/docs/AUTH_SECURITY.md`.

## Seed data

```bash
python -m scripts.seed_data
```

## Global songs auto-sync

By default, the backend imports songs from `backend/songs` at startup and keeps that folder synced while the server is running.

- Add a supported file into `backend/songs` (or subfolders): it is auto-imported.
- Remove a previously imported file from that folder: it is removed from the library.

Environment variables:

- `GLOBAL_SONGS_DIR` (default: `backend/songs`)
- `AUTO_IMPORT_GLOBAL_SONGS_ON_STARTUP` (default: `true`)
- `GLOBAL_SONGS_WATCH_ENABLED` (default: `true`)
- `GLOBAL_SONGS_WATCH_INTERVAL_SECONDS` (default: `5`)
