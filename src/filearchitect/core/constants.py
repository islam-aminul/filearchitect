"""
Application-wide constants for FileArchitect.

This module defines constants used throughout the application.
"""

from enum import Enum

# Version
VERSION = "1.0.0"

# Application name
APP_NAME = "FileArchitect"
APP_AUTHOR = "FileArchitect Team"

# File size thresholds
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB
LOW_SPACE_THRESHOLD = 5 * 1024 * 1024 * 1024  # 5 GB

# Performance settings
DEFAULT_THREAD_COUNT = 4
MAX_THREAD_COUNT = 16
HASH_BUFFER_SIZE = 65536  # 64 KB

# Progress settings
PROGRESS_UPDATE_INTERVAL = 0.2  # seconds
BATCH_SIZE = 100  # Files to process before flushing progress

# Database settings
DATABASE_NAME = "filearchitect.db"
DATABASE_TIMEOUT = 30.0  # seconds

# Configuration
CONFIG_DIR = "conf"
CONFIG_FILE = "config.json"
PROGRESS_FILE = "progress.json"
DB_DIR = "db"
LOGS_DIR = "logs"

# Image export settings
DEFAULT_JPEG_QUALITY = 85
DEFAULT_MAX_WIDTH = 3840  # 4K width
DEFAULT_MAX_HEIGHT = 2160  # 4K height


class FileType(Enum):
    """Enumeration of file types supported by FileArchitect."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class ProcessingStatus(Enum):
    """Enumeration of file processing statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"
    ERROR = "error"


class SessionStatus(Enum):
    """Enumeration of session statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"
    UNDONE = "undone"


class DateSource(Enum):
    """Enumeration of date sources for file organization."""

    EXIF = "exif"
    FILENAME = "filename"
    FOLDER = "folder"
    INFERRED = "inferred"
    NONE = "none"


# Supported file extensions by type
IMAGE_EXTENSIONS = {
    # Standard formats
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
    # Modern formats
    ".heic", ".heif", ".avif", ".jxl",
    # RAW formats
    ".cr2", ".nef", ".arw", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
    ".mpg", ".mpeg", ".3gp", ".3g2", ".mts", ".m2ts",
}

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma",
    ".amr", ".aiff", ".ape",
}

DOCUMENT_EXTENSIONS = {
    # PDF
    ".pdf",
    # Text
    ".txt", ".rtf", ".md", ".markdown",
    # Office
    ".doc", ".docx", ".odt",
    ".xls", ".xlsx", ".ods", ".csv",
    ".ppt", ".pptx", ".odp",
    # Code (common)
    ".py", ".js", ".java", ".cpp", ".c", ".h", ".cs", ".php",
    ".html", ".css", ".xml", ".json", ".yaml", ".yml",
    ".sql", ".sh", ".bat", ".ps1",
}

# Sidecar file extensions
SIDECAR_EXTENSIONS = {
    ".xmp",  # Adobe metadata
    ".aae",  # Apple photo edits
    ".thm",  # Thumbnail files
    ".srt",  # Subtitles
    ".sub",  # Subtitles
    ".lrc",  # Lyrics
}

# RAW file extensions
RAW_EXTENSIONS = {
    ".cr2", ".cr3",  # Canon
    ".nef", ".nrw",  # Nikon
    ".arw", ".srf", ".sr2",  # Sony
    ".dng",  # Adobe/Universal
    ".raf",  # Fujifilm
    ".orf",  # Olympus
    ".rw2",  # Panasonic
    ".pef",  # Pentax
    ".srw",  # Samsung
    ".raw",  # Generic
}
