"""
Database session management and FastAPI dependency.
Uses SQLAlchemy 2.0 style with sync engine/session.
Supports both SQLite (local dev) and PostgreSQL (production).
"""
from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import make_url

from app.core.config import ensure_sqlite_directory, get_settings


settings = get_settings()

_raw_url = settings.DATABASE_URL

# Render and some providers use "postgres://" which SQLAlchemy 2.0 doesn't accept
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)

ensure_sqlite_directory(_raw_url)

db_url = make_url(_raw_url)
engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": False,
}

if db_url.get_backend_name() == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL connection pool settings for production
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_engine(_raw_url, **engine_kwargs)

if db_url.get_backend_name() == "sqlite":
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        """Enable foreign key constraints for SQLite connections."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Ensures session is closed after request (even on exception).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
