"""
Optional seed script for development: inserts 3 artists, 3 albums, 10 songs.
Run from backend directory: python -m scripts.seed_data
Requires: DATABASE_URL set, migrations applied (alembic upgrade head).
"""
import os
import sys

# Add backend root to path so app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Artist, Album, Song


def seed() -> None:
    db = SessionLocal()
    try:
        # Skip if we already have artists
        existing = db.execute(select(Artist.id).limit(1)).scalar_one_or_none()
        if existing is not None:
            print("Seed already applied (artists exist). Skipping.")
            return

        # 3 artists
        a1 = Artist(name="The Midnight")
        a2 = Artist(name="Kavinsky")
        a3 = Artist(name="FM-84")
        db.add_all([a1, a2, a3])
        db.flush()

        # 3 albums
        al1 = Album(title="Endless Summer", artist_id=a1.id, year=2016)
        al2 = Album(title="OutRun", artist_id=a2.id, year=2013)
        al3 = Album(title="Atlas", artist_id=a3.id, year=2016)
        db.add_all([al1, al2, al3])
        db.flush()

        # 10 songs across artists/albums
        songs_data = [
            ("Sunset", a1.id, al1.id, 1, 245.0, "/music/midnight/sunset.mp3", "mp3", 320),
            ("Days of Thunder", a1.id, al1.id, 2, 312.0, "/music/midnight/days.mp3", "mp3", 320),
            ("Nighthawks", a1.id, al1.id, 3, 298.0, "/music/midnight/nighthawks.mp3", "mp3", 320),
            ("Crystalline", a1.id, al1.id, 4, 267.0, "/music/midnight/crystalline.mp3", "mp3", 320),
            ("Pacific Coast Highway", a1.id, al1.id, 5, 301.0, "/music/midnight/pch.mp3", "mp3", 320),
            ("Nightcall", a2.id, al2.id, 1, 258.0, "/music/kavinsky/nightcall.mp3", "mp3", 320),
            ("Roadgame", a2.id, al2.id, 2, 244.0, "/music/kavinsky/roadgame.mp3", "mp3", 320),
            ("Testarossa Autodrive", a2.id, al2.id, 3, 223.0, "/music/kavinsky/testarossa.mp3", "mp3", 320),
            ("Wild Ones", a3.id, al3.id, 1, 276.0, "/music/fm84/wild_ones.mp3", "mp3", 320),
            ("Running in the Night", a3.id, al3.id, 2, 262.0, "/music/fm84/running.mp3", "mp3", 320),
        ]
        for title, artist_id, album_id, track_num, duration, path, fmt, bitrate in songs_data:
            size = (bitrate * 1000 * duration / 8) if bitrate else None  # approximate bytes
            s = Song(
                title=title,
                artist_id=artist_id,
                album_id=album_id,
                track_number=track_num,
                duration=duration,
                file_path=path,
                file_format=fmt,
                file_size=int(size) if size else None,
                bitrate=bitrate,
            )
            db.add(s)

        db.commit()
        print("Seed complete: 3 artists, 3 albums, 10 songs.")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
