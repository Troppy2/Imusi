"""
Background watcher for GLOBAL_SONGS_DIR.
Polls the directory for added/removed audio files and syncs DB records.
"""
from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
from typing import Iterable

from sqlalchemy import select

from app.core.logging_config import get_logger
from app.db.session import SessionLocal
from app.models import Folder, FolderSong, Song
from app.services.import_service import import_single_file
from app.utils.constants import SUPPORTED_AUDIO_EXTENSIONS

logger = get_logger(__name__)

_watcher_thread: Thread | None = None
_watcher_stop_event: Event | None = None


def _iter_audio_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return []
    return (
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    )


def _snapshot_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for path in _iter_audio_files(root):
        try:
            paths.add(str(path.resolve()))
        except OSError:
            continue
    return paths


def _get_or_create_root_folder(db, root: Path) -> Folder:
    folder_name = root.name
    folder = db.execute(
        select(Folder).where(Folder.name == folder_name, Folder.parent_id.is_(None))
    ).scalar_one_or_none()
    if folder:
        return folder
    folder = Folder(name=folder_name, parent_id=None)
    db.add(folder)
    db.flush()
    return folder


def _ensure_folder_link(db, folder_id: int, song_id: int) -> None:
    existing = db.execute(
        select(FolderSong).where(FolderSong.folder_id == folder_id, FolderSong.song_id == song_id)
    ).scalar_one_or_none()
    if not existing:
        db.add(FolderSong(folder_id=folder_id, song_id=song_id))


def _sync_changes_once(root: Path, known_paths: set[str]) -> set[str]:
    current_paths = _snapshot_paths(root)
    added = sorted(current_paths - known_paths)
    removed = sorted(known_paths - current_paths)
    if not added and not removed:
        return known_paths

    db = SessionLocal()
    try:
        imported_count = 0
        removed_count = 0
        folder: Folder | None = None
        if added:
            folder = _get_or_create_root_folder(db, root)

        for file_path in added:
            song = import_single_file(db, file_path)
            if song:
                imported_count += 1
                if folder:
                    _ensure_folder_link(db, folder.id, song.id)
                continue
            if folder:
                existing_song_id = db.execute(
                    select(Song.id).where(Song.file_path == file_path)
                ).scalar_one_or_none()
                if existing_song_id is not None:
                    _ensure_folder_link(db, folder.id, existing_song_id)

        for file_path in removed:
            existing_song = db.execute(
                select(Song).where(Song.file_path == file_path)
            ).scalar_one_or_none()
            if existing_song is not None:
                db.delete(existing_song)
                removed_count += 1

        db.commit()
        logger.info(
            "Global songs watcher synced changes",
            extra={
                "root": str(root),
                "added_detected": len(added),
                "removed_detected": len(removed),
                "imported_count": imported_count,
                "removed_count": removed_count,
            },
        )
        return current_paths
    except Exception:
        db.rollback()
        logger.exception("Global songs watcher sync failed", extra={"root": str(root)})
        return known_paths
    finally:
        db.close()


def _watch_loop(root: Path, interval_seconds: int, stop_event: Event) -> None:
    logger.info(
        "Global songs watcher started",
        extra={"root": str(root), "interval_seconds": interval_seconds},
    )
    known_paths = _snapshot_paths(root)
    while not stop_event.wait(interval_seconds):
        known_paths = _sync_changes_once(root, known_paths)
    logger.info("Global songs watcher stopped", extra={"root": str(root)})


def start_global_songs_watcher(root_path: str, interval_seconds: int = 5) -> None:
    global _watcher_thread, _watcher_stop_event

    root = Path(root_path).expanduser().resolve()
    if not root.is_dir():
        logger.info(
            "Global songs watcher not started: directory not found",
            extra={"root": str(root)},
        )
        return

    if _watcher_thread and _watcher_thread.is_alive():
        logger.info("Global songs watcher already running", extra={"root": str(root)})
        return

    stop_event = Event()
    thread = Thread(
        target=_watch_loop,
        args=(root, max(1, interval_seconds), stop_event),
        daemon=True,
        name="global_songs_watcher",
    )
    _watcher_stop_event = stop_event
    _watcher_thread = thread
    thread.start()


def stop_global_songs_watcher(timeout_seconds: int = 5) -> None:
    global _watcher_thread, _watcher_stop_event
    if not _watcher_thread or not _watcher_thread.is_alive():
        _watcher_thread = None
        _watcher_stop_event = None
        return

    if _watcher_stop_event:
        _watcher_stop_event.set()
    _watcher_thread.join(timeout=timeout_seconds)
    _watcher_thread = None
    _watcher_stop_event = None
