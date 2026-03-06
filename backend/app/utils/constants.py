"""
Constants for supported audio formats and file extensions.
Used by import service to filter and detect valid audio files.
"""
# File extensions (lowercase) that the app supports for import
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac"}

# MIME / format names for display and metadata
AUDIO_FORMAT_NAMES = {
    ".mp3": "mp3",
    ".wav": "wav",
    ".flac": "flac",
    ".m4a": "m4a",
    ".aac": "aac",
}
