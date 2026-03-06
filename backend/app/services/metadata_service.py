"""
Metadata extraction from audio files using mutagen.
Returns a structured object with title, artist, album, track_number, duration, artwork.
"""
from pathlib import Path
from typing import Any

import mutagen
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.wave import WAVE

from app.utils.constants import SUPPORTED_AUDIO_EXTENSIONS


class ExtractedMetadata:
    """Structured result of metadata extraction."""

    def __init__(
        self,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        track_number: int | None = None,
        duration: float = 0.0,
        artwork_path: str | None = None,
        file_format: str = "mp3",
    ):
        self.title = title
        self.artist = artist
        self.album = album
        self.track_number = track_number
        self.duration = duration
        self.artwork_path = artwork_path
        self.file_format = file_format

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "track_number": self.track_number,
            "duration": self.duration,
            "artwork_path": self.artwork_path,
            "file_format": self.file_format,
        }


def _get_extension(path: str | Path) -> str:
    return Path(path).suffix.lower()


def _extract_artwork(af: mutagen.File, dest_dir: Path | None = None) -> str | None:
    """
    Extract embedded artwork to a file if possible.
    Returns path to saved artwork file, or None if no artwork or save failed.
    """
    try:
        if hasattr(af, "pictures") and af.pictures:
            pic = af.pictures[0]
            if dest_dir:
                dest_dir.mkdir(parents=True, exist_ok=True)
                ext = ".jpg" if pic.mime and "jpeg" in pic.mime else ".png"
                out_path = dest_dir / f"art_{hash(pic.data) % 2**32}{ext}"
                out_path.write_bytes(pic.data)
                return str(out_path)
        if isinstance(af, ID3):
            for key in ("APIC:Cover", "APIC:", "APIC:cover"):
                if key in af:
                    data = af[key].data
                    if dest_dir and data:
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        out_path = dest_dir / f"art_{hash(data) % 2**32}.jpg"
                        out_path.write_bytes(data)
                        return str(out_path)
                    break
        if isinstance(af, MP4) and "covr" in af:
            data = af["covr"][0]
            if dest_dir and data:
                dest_dir.mkdir(parents=True, exist_ok=True)
                out_path = dest_dir / f"art_{hash(bytes(data)) % 2**32}.jpg"
                out_path.write_bytes(bytes(data))
                return str(out_path)
    except Exception:
        pass
    return None


def extract_metadata(
    file_path: str | Path,
    artwork_output_dir: Path | None = None,
) -> ExtractedMetadata:
    """
    Extract metadata from an audio file using mutagen.
    file_path: absolute path to the audio file.
    artwork_output_dir: optional directory to save extracted artwork; if None, artwork_path in result may still be set for in-memory detection but not persisted.
    Returns ExtractedMetadata with title, artist, album, track_number, duration, artwork_path, file_format.
    """
    path = Path(file_path)
    if not path.is_file():
        return ExtractedMetadata(file_format=_get_extension(path).lstrip(".") or "mp3")

    ext = _get_extension(path)
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        return ExtractedMetadata(file_format=ext.lstrip(".") or "mp3")

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    duration = 0.0
    artwork_path: str | None = None
    file_format = ext.lstrip(".").lower()

    try:
        af = mutagen.File(str(path))
        if af is None:
            return ExtractedMetadata(
                title=path.stem,
                file_format=file_format,
                duration=0.0,
            )
        duration = float(af.info.length) if af.info else 0.0

        if isinstance(af, ID3):
            if "TIT2" in af:
                title = str(af["TIT2"].text[0]).strip() or None
            if "TPE1" in af:
                artist = str(af["TPE1"].text[0]).strip() or None
            if "TALB" in af:
                album = str(af["TALB"].text[0]).strip() or None
            if "TRCK" in af:
                try:
                    track_number = int(str(af["TRCK"].text[0]).split("/")[0].strip())
                except (ValueError, IndexError):
                    pass
            artwork_path = _extract_artwork(af, artwork_output_dir)

        elif isinstance(af, MP4):
            if "\xa9nam" in af:
                title = (af["\xa9nam"][0] or "").strip() or None
            if "\xa9ART" in af:
                artist = (af["\xa9ART"][0] or "").strip() or None
            if "\xa9alb" in af:
                album = (af["\xa9alb"][0] or "").strip() or None
            if "trkn" in af:
                try:
                    track_number = int(af["trkn"][0][0])
                except (IndexError, TypeError):
                    pass
            artwork_path = _extract_artwork(af, artwork_output_dir)

        elif isinstance(af, FLAC):
            if "title" in af:
                title = (af["title"][0] or "").strip() or None
            if "artist" in af:
                artist = (af["artist"][0] or "").strip() or None
            if "album" in af:
                album = (af["album"][0] or "").strip() or None
            if "tracknumber" in af:
                try:
                    track_number = int(af["tracknumber"][0].split("/")[0].strip())
                except (ValueError, IndexError):
                    pass
            artwork_path = _extract_artwork(af, artwork_output_dir)

        else:
            # Generic tags (e.g. WAVE, other formats mutagen supports)
            if hasattr(af, "tags") and af.tags:
                for key, value in af.tags.items():
                    k = (key or "").lower()
                    if "title" in k and not title:
                        title = (str(value[0]) if isinstance(value, list) else str(value)).strip() or None
                    elif "artist" in k and not artist:
                        artist = (str(value[0]) if isinstance(value, list) else str(value)).strip() or None
                    elif "album" in k and not album:
                        album = (str(value[0]) if isinstance(value, list) else str(value)).strip() or None
                    elif "track" in k and track_number is None:
                        try:
                            v = value[0] if isinstance(value, list) else value
                            track_number = int(str(v).split("/")[0].strip())
                        except (ValueError, IndexError):
                            pass
            if not artwork_path and hasattr(af, "pictures"):
                artwork_path = _extract_artwork(af, artwork_output_dir)

        if not title:
            title = path.stem
    except Exception:
        title = path.stem
        duration = 0.0

    return ExtractedMetadata(
        title=title or path.stem,
        artist=artist,
        album=album,
        track_number=track_number,
        duration=duration,
        artwork_path=artwork_path,
        file_format=file_format,
    )
