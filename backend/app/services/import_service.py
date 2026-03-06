"""
Import service: import single files or folders into the library.
Detects supported formats, extracts metadata, inserts artist/album/song and prevents duplicates.
"""
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.logging_config import get_logger
from app.models import Artist, Album, Song, Folder, FolderSong
from app.utils.constants import SUPPORTED_AUDIO_EXTENSIONS, AUDIO_FORMAT_NAMES
from app.services.metadata_service import extract_metadata, ExtractedMetadata

logger = get_logger(__name__)


def _get_or_create_artist(db: Session, name: str) -> Artist:
    """Get existing artist by name or create one. Prevents duplicate artists."""
    stmt = select(Artist).where(Artist.name == name)
    artist = db.execute(stmt).scalar_one_or_none()
    if artist:
        return artist
    artist = Artist(name=name)
    db.add(artist)
    db.flush()  # Get id without committing
    return artist


def _get_or_create_album(
    db: Session, title: str, artist_id: int, year: int | None = None, artwork_path: str | None = None
) -> Album:
    """Get existing album by title+artist or create one."""
    stmt = select(Album).where(Album.title == title, Album.artist_id == artist_id)
    album = db.execute(stmt).scalar_one_or_none()
    if album:
        return album
    album = Album(
        title=title,
        artist_id=artist_id,
        year=year,
        artwork_path=artwork_path,
    )
    db.add(album)
    db.flush()
    return album


def _song_exists_by_path(db: Session, file_path: str) -> bool:
    stmt = select(Song.id).where(Song.file_path == file_path)
    return db.execute(stmt).scalar_one_or_none() is not None


def _get_song_by_path(db: Session, file_path: str) -> Song | None:
    stmt = select(Song).where(Song.file_path == file_path)
    return db.execute(stmt).scalar_one_or_none()


def _folder_song_link_exists(db: Session, folder_id: int, song_id: int) -> bool:
    stmt = select(FolderSong).where(FolderSong.folder_id == folder_id, FolderSong.song_id == song_id)
    return db.execute(stmt).scalar_one_or_none() is not None


def _build_song_from_metadata(
    meta: ExtractedMetadata,
    file_path: str,
    artist_id: int,
    album_id: int | None,
) -> Song:
    """Create a Song model instance from extracted metadata (does not add to session)."""
    return Song(
        title=meta.title or Path(file_path).stem,
        artist_id=artist_id,
        album_id=album_id,
        duration=meta.duration,
        file_path=file_path,
        track_number=meta.track_number,
        file_format=meta.file_format,
        artwork_path=meta.artwork_path,
    )


def import_single_file(
    db: Session,
    file_path: str,
    artwork_output_dir: Path | None = None,
) -> Song | None:
    """
    Import a single audio file: detect format, extract metadata, insert artist/album/song.
    Returns the Song model if imported, None if skipped (unsupported format or duplicate).
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        logger.debug("Import skipped: file not found", extra={"file_path": file_path})
        return None
    ext = path.suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        logger.debug("Import skipped: unsupported format", extra={"file_path": file_path, "ext": ext})
        return None

    abs_path = str(path)
    if _song_exists_by_path(db, abs_path):
        logger.debug("Import skipped: duplicate file_path", extra={"file_path": abs_path})
        return None

    meta = extract_metadata(path, artwork_output_dir=artwork_output_dir)
    artist_name = meta.artist or "Unknown Artist"
    artist = _get_or_create_artist(db, artist_name)

    album_id: int | None = None
    if meta.album:
        album = _get_or_create_album(
            db,
            meta.album,
            artist.id,
            artwork_path=meta.artwork_path,
        )
        album_id = album.id

    file_format = AUDIO_FORMAT_NAMES.get(ext, meta.file_format)
    song = _build_song_from_metadata(meta, abs_path, artist.id, album_id)
    song.file_format = file_format
    db.add(song)
    db.flush()
    return song


def import_folder(
    db: Session,
    folder_path: str,
    artwork_output_dir: Path | None = None,
    create_folder_record: bool = True,
) -> tuple[list[Song], Folder | None]:
    """
    Recursively scan folder_path for supported audio files and import each.
    Optionally create a Folder record and link imported songs to it via FolderSong.
    Returns (list of imported Song models, Folder or None).
    """
    root = Path(folder_path).resolve()
    if not root.is_dir():
        return [], None

    imported: list[Song] = []
    folder_record: Folder | None = None
    if create_folder_record:
        # Get or create folder by path name
        name = root.name
        stmt = select(Folder).where(Folder.name == name, Folder.parent_id.is_(None))
        folder_record = db.execute(stmt).scalar_one_or_none()
        if not folder_record:
            folder_record = Folder(name=name, parent_id=None)
            db.add(folder_record)
            db.flush()

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            continue
        abs_path = str(path.resolve())
        try:
            song = import_single_file(db, abs_path, artwork_output_dir=artwork_output_dir)
            if song:
                imported.append(song)
            if folder_record:
                existing_song = song or _get_song_by_path(db, abs_path)
                if existing_song and not _folder_song_link_exists(db, folder_record.id, existing_song.id):
                    db.add(FolderSong(folder_id=folder_record.id, song_id=existing_song.id))
        except Exception:
            logger.warning("Import skipped: error processing file", extra={"file_path": abs_path})
            continue

    if create_folder_record and folder_record:
        db.flush()
    return imported, folder_record
