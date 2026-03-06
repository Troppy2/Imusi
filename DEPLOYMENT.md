# IMUSI - Cloud Deployment & Android Build Guide

## Architecture Overview

```
┌─────────────────┐     HTTPS      ┌─────────────────┐     PostgreSQL    ┌─────────────────┐
│  Android App    │ ──────────────> │  FastAPI Backend │ ───────────────> │  Neon Database   │
│  (Expo/RN)      │                 │  (Render)        │                  │  (PostgreSQL)    │
└─────────────────┘                 └─────────────────┘                  └─────────────────┘
```

---

## 1. Database Setup (Neon PostgreSQL)

### Create Database

1. Sign up at [neon.tech](https://neon.tech)
2. Create a new project named `imusi`
3. Copy the connection string (looks like):
   ```
   postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/imusi?sslmode=require
   ```

### Automatic Schema Creation

The backend automatically creates all tables on startup via `Base.metadata.create_all()`. No manual SQL needed.

### Migrate Existing SQLite Data (Optional)

If you have existing data in SQLite that you want to move to PostgreSQL:

```bash
cd backend

# Dry run first
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite "sqlite:///./data/imusi.db" \
  --postgres "postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/imusi?sslmode=require" \
  --dry-run

# Actual migration
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite "sqlite:///./data/imusi.db" \
  --postgres "postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/imusi?sslmode=require"
```

---

## 2. Backend Deployment (Render)

### Option A: Deploy via Render Dashboard

1. Go to [render.com](https://render.com) and create a new **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`

4. Add environment variables in the Render dashboard:

   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | Your Neon PostgreSQL connection string |
   | `JWT_SECRET` | Generate: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
   | `JWT_REFRESH_SECRET` | Generate another random secret |
   | `ENVIRONMENT` | `production` |
   | `AUTO_IMPORT_GLOBAL_SONGS_ON_STARTUP` | `false` |
   | `GLOBAL_SONGS_WATCH_ENABLED` | `false` |
   | `RATE_LIMIT_ENABLED` | `true` |
   | `LOG_LEVEL` | `INFO` |

5. Deploy!

### Option B: Deploy via Blueprint

```bash
# From repo root
render blueprint apply
```

This uses `backend/render.yaml` to auto-configure the service.

### Option C: Deploy with Docker (Railway / Fly.io)

```bash
cd backend
docker build -t imusi-backend .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e JWT_SECRET="your-secret" \
  -e JWT_REFRESH_SECRET="your-refresh-secret" \
  -e ENVIRONMENT="production" \
  -e AUTO_IMPORT_GLOBAL_SONGS_ON_STARTUP="false" \
  -e GLOBAL_SONGS_WATCH_ENABLED="false" \
  imusi-backend
```

### Verify Deployment

```bash
curl https://your-imusi-backend.onrender.com/health
# Should return: {"status": "ok", "version": "1.0.0"}

curl https://your-imusi-backend.onrender.com/docs
# Opens Swagger UI
```

---

## 3. Android APK Build

### Prerequisites

```bash
npm install -g eas-cli
cd mobile
eas login  # Login to your Expo account
```

### Update Backend URL

Edit `mobile/eas.json` and replace `https://your-imusi-backend.onrender.com` with your actual deployed backend URL in the `preview` and `production` build profiles.

Also update `mobile/src/config/api.ts`:
- Set `PROD_API_URL` to your deployed backend URL

### Build APK

```bash
cd mobile

# Development build (connects to local backend)
eas build --platform android --profile development

# Preview build (connects to cloud backend, APK for testing)
eas build --platform android --profile preview

# Production build (connects to cloud backend)
eas build --platform android --profile production
```

### Local Build (no EAS cloud)

```bash
cd mobile

# Generate native Android project
npx expo prebuild --platform android

# Build APK locally (requires Android SDK)
cd android
./gradlew assembleRelease

# APK will be at: android/app/build/outputs/apk/release/app-release.apk
```

### Install APK on Device

```bash
# Via ADB
adb install app-release.apk

# Or download from EAS build dashboard
```

---

## 4. Environment Configuration Summary

### Backend (.env)
```env
DATABASE_URL=postgresql://user:pass@host/imusi?sslmode=require
ENVIRONMENT=production
JWT_SECRET=<random-64-char-secret>
JWT_REFRESH_SECRET=<another-random-64-char-secret>
AUTO_IMPORT_GLOBAL_SONGS_ON_STARTUP=false
GLOBAL_SONGS_WATCH_ENABLED=false
RATE_LIMIT_ENABLED=true
LOG_LEVEL=INFO
```

### Mobile (eas.json env)
```
EXPO_PUBLIC_API_URL=https://your-imusi-backend.onrender.com/api/v1
```

---

## 5. API Endpoints

All endpoints are under `/api/v1/`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/signup` | Create account |
| POST | `/auth/login` | Login |
| POST | `/auth/refresh` | Refresh token |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Current user |
| GET | `/songs` | List songs (paginated) |
| GET | `/songs/:id` | Get song |
| PATCH | `/songs/:id/favorite` | Toggle favorite |
| PATCH | `/songs/:id/metadata` | Update metadata |
| GET | `/artists` | List artists |
| GET | `/artists/:id/songs` | Artist songs |
| GET | `/albums` | List albums |
| GET | `/albums/:id/songs` | Album songs |
| GET | `/folders` | List folders |
| GET | `/folders/:id/songs` | Folder songs |
| GET | `/playlists` | List playlists |
| POST | `/playlists` | Create playlist |
| GET | `/playlists/:id/songs` | Playlist songs |
| POST | `/playlists/:id/songs` | Add song to playlist |
| GET | `/search?q=` | Search all |
| GET | `/stream/:id` | Stream audio |
| GET | `/recently-played/overview` | Recent plays |
| POST | `/import/folder` | Import folder |
| GET | `/health` | Health check |

---

## 6. Troubleshooting

### Backend won't start on Render
- Check that `DATABASE_URL` is set correctly
- Ensure `JWT_SECRET` and `JWT_REFRESH_SECRET` are set
- Check Render logs for specific errors

### Database connection fails
- Verify Neon database is active (free tier pauses after inactivity)
- Ensure `?sslmode=require` is in the connection string
- Check IP allowlist if configured

### APK won't connect to backend
- Verify `EXPO_PUBLIC_API_URL` in eas.json matches your deployed URL
- Ensure HTTPS is used (Android blocks cleartext HTTP by default)
- Check that CORS allows your app's requests

### Build fails
- Run `npx expo-doctor` to check for compatibility issues
- Ensure `eas-cli` is up to date: `npm install -g eas-cli`
