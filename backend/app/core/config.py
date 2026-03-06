"""
Application configuration.
Loads from environment variables for flexibility (Docker, local, etc.).
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url


DEFAULT_GLOBAL_SONGS_DIR = Path(__file__).resolve().parents[2] / "songs"
DEFAULT_SQLITE_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "imusi.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_DB_PATH.as_posix()}"


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database (override with DATABASE_URL env var for PostgreSQL in production)
    DATABASE_URL: str = DEFAULT_DATABASE_URL

    # Environment
    ENVIRONMENT: str = "development"

    # Optional Redis (for future caching)
    REDIS_URL: str | None = None

    # CORS - allow React Native and local dev
    CORS_ORIGINS: list[str] = ["*"]

    # API
    API_V1_PREFIX: str = "/api/v1"
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_EXEMPT_PATHS: list[str] = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/stream",
    ]
    AUTH_RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT_REQUESTS: int = 5
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AUTH_RATE_LIMIT_PATHS: list[str] = [
        "/api/v1/auth/login",
        "/api/v1/auth/google",
        "/api/v1/auth/signup",
    ]

    # Auth
    JWT_SECRET: str | None = None
    JWT_REFRESH_SECRET: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "imusi-backend"
    JWT_AUDIENCE: str = "imusi-mobile"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OAuth (Google)
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # OAuth (Spotify)
    SPOTIFY_CLIENT_ID: str | None = None
    SPOTIFY_CLIENT_SECRET: str | None = None

    # Library import
    AUTO_IMPORT_GLOBAL_SONGS_ON_STARTUP: bool = True
    GLOBAL_SONGS_DIR: str = str(DEFAULT_GLOBAL_SONGS_DIR)
    GLOBAL_SONGS_WATCH_ENABLED: bool = True
    GLOBAL_SONGS_WATCH_INTERVAL_SECONDS: int = 5

    # Spotify-to-Local download pipeline
    MUSIC_DOWNLOAD_DIR: str = str(Path(__file__).resolve().parents[2] / "music")
    DOWNLOAD_AUDIO_FORMAT: str = "mp3"
    DOWNLOAD_AUDIO_QUALITY: str = "192"

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


def ensure_sqlite_directory(database_url: str) -> None:
    """Create parent directory for SQLite file DBs if it does not exist."""
    db_url = make_url(database_url)
    if db_url.get_backend_name() != "sqlite":
        return

    db_path = db_url.database
    if not db_path or db_path == ":memory:":
        return

    Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
