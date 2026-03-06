"""
Database session management and FastAPI dependency.
Uses SQLAlchemy 2.0 style with sync engine/session.
"""
from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import make_url

from app.core.config import ensure_sqlite_directory, get_settings


settings = get_settings()
ensure_sqlite_directory(settings.DATABASE_URL)

db_url = make_url(settings.DATABASE_URL)
engine_kwargs = {
    "pool_pre_ping": True,  # Verify connections before use
    "echo": False,  # Set True for SQL logging during development
}
if db_url.get_backend_name() == "sqlite":
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

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
