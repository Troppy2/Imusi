"""
YouTube search and audio download service using yt-dlp.
Provides: search for best matching track, download audio, tag metadata.
"""
import json
import re
import shutil
from pathlib import Path
from typing import Any

from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in file paths."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    sanitized = sanitized.strip('. ')
    return sanitized or 'Unknown'


def _title_similarity(a: str, b: str) -> float:
    """Simple normalized word-overlap similarity between two strings."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _duration_score(expected_ms: int, actual_seconds: float) -> float:
    """Score 0-1 based on how close durations are. 1.0 = exact match."""
    if expected_ms <= 0 or actual_seconds <= 0:
        return 0.5
    expected_s = expected_ms / 1000.0
    diff = abs(expected_s - actual_seconds)
    if diff < 3:
        return 1.0
    if diff < 10:
        return 0.8
    if diff < 30:
        return 0.5
    return max(0.0, 1.0 - diff / expected_s)


def search_youtube(query: str, expected_duration_ms: int = 0, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Search YouTube for audio matching the query. Returns ranked candidates.

    Each result dict has: url, title, duration, channel, score
    """
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed. Install with: pip install yt-dlp")
        return []

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': 'ytsearch' + str(max_results),
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)
            if not result:
                return []

            entries = result.get('entries', [])
            if not entries:
                return []

            candidates = []
            for entry in entries:
                if not entry:
                    continue
                title = entry.get('title', '')
                duration = entry.get('duration') or 0
                url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                channel = entry.get('channel') or entry.get('uploader') or ''

                title_sim = _title_similarity(query, title)
                dur_score = _duration_score(expected_duration_ms, duration) if expected_duration_ms > 0 else 0.5
                # Weight: 60% title similarity, 40% duration match
                combined_score = title_sim * 0.6 + dur_score * 0.4

                candidates.append({
                    'url': url,
                    'title': title,
                    'duration': duration,
                    'channel': channel,
                    'score': round(combined_score, 3),
                })

            candidates.sort(key=lambda c: c['score'], reverse=True)
            return candidates

    except Exception as exc:
        logger.exception("YouTube search failed for query: %s", query)
        return []


def download_audio(
    youtube_url: str,
    output_dir: str,
    filename: str = 'audio',
    audio_format: str | None = None,
    audio_quality: str | None = None,
) -> str | None:
    """
    Download audio from a YouTube URL.
    Returns the path to the downloaded file, or None on failure.
    """
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed")
        return None

    settings = get_settings()
    fmt = audio_format or settings.DOWNLOAD_AUDIO_FORMAT
    quality = audio_quality or settings.DOWNLOAD_AUDIO_QUALITY

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    safe_filename = _sanitize_filename(filename)
    output_template = str(output_path / f'{safe_filename}.%(ext)s')

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': fmt,
            'preferredquality': quality,
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            if not info:
                return None

            # yt-dlp may change the extension after conversion
            expected_file = output_path / f'{safe_filename}.{fmt}'
            if expected_file.is_file():
                return str(expected_file)

            # Fallback: find any file matching the safe filename
            for f in output_path.iterdir():
                if f.stem == safe_filename and f.is_file():
                    return str(f)

            return None

    except Exception as exc:
        logger.exception("YouTube download failed for URL: %s", youtube_url)
        return None


def tag_audio_file(
    file_path: str,
    title: str,
    artist: str,
    album: str = 'Unknown Album',
    artwork_url: str | None = None,
) -> bool:
    """
    Embed metadata tags (title, artist, album) into an audio file using mutagen.
    Optionally downloads and embeds artwork from artwork_url.
    Returns True on success.
    """
    try:
        import mutagen
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
        from mutagen.mp4 import MP4

        path = Path(file_path)
        if not path.is_file():
            logger.warning("Cannot tag: file not found %s", file_path)
            return False

        ext = path.suffix.lower()

        if ext == '.mp3':
            try:
                tags = ID3(str(path))
            except mutagen.id3.ID3NoHeaderError:
                tags = ID3()

            tags.add(TIT2(encoding=3, text=[title]))
            tags.add(TPE1(encoding=3, text=[artist]))
            tags.add(TALB(encoding=3, text=[album]))

            # Download and embed artwork
            if artwork_url:
                artwork_data = _download_artwork(artwork_url)
                if artwork_data:
                    tags.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,  # Cover (front)
                        desc='Cover',
                        data=artwork_data,
                    ))

            tags.save(str(path))
            return True

        elif ext in ('.m4a', '.mp4', '.aac'):
            audio = MP4(str(path))
            audio['\xa9nam'] = [title]
            audio['\xa9ART'] = [artist]
            audio['\xa9alb'] = [album]

            if artwork_url:
                artwork_data = _download_artwork(artwork_url)
                if artwork_data:
                    from mutagen.mp4 import MP4Cover
                    audio['covr'] = [MP4Cover(artwork_data, imageformat=MP4Cover.FORMAT_JPEG)]

            audio.save()
            return True

        else:
            logger.info("Tagging not supported for format: %s", ext)
            return False

    except Exception as exc:
        logger.exception("Failed to tag audio file: %s", file_path)
        return False


def _download_artwork(url: str) -> bytes | None:
    """Download artwork image from a URL. Returns raw bytes or None."""
    try:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
    except Exception:
        logger.debug("Failed to download artwork from %s", url)
        return None
