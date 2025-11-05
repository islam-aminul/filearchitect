"""
Database data models for FileArchitect.

This module defines data classes for database entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..core.constants import FileType, ProcessingStatus, SessionStatus, DateSource


@dataclass
class Session:
    """Represents an organization session."""

    session_id: str
    source_path: str
    destination_path: str
    status: SessionStatus
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    files_scanned: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_error: int = 0
    duplicates_found: int = 0
    bytes_processed: int = 0
    bytes_total: int = 0
    config_snapshot: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class FileRecord:
    """Represents a file record in the database."""

    session_id: str
    source_path: str
    file_hash: str
    file_size: int
    file_type: FileType
    file_extension: str
    status: ProcessingStatus
    id: Optional[int] = None
    destination_path: Optional[str] = None
    category: Optional[str] = None
    date_taken: Optional[datetime] = None
    date_source: Optional[DateSource] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    metadata_json: Optional[str] = None
    error_message: Optional[str] = None
    processed_at: datetime = field(default_factory=datetime.now)


@dataclass
class FileMapping:
    """Represents a file mapping for undo functionality."""

    session_id: str
    source_path: str
    destination_path: str
    operation: str  # 'copy', 'move', 'export'
    id: Optional[int] = None
    file_hash: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate files."""

    file_hash: str
    file_extension: str
    id: Optional[int] = None
    original_file_id: Optional[int] = None
    duplicate_count: int = 0
    first_seen_at: datetime = field(default_factory=datetime.now)
    last_seen_at: datetime = field(default_factory=datetime.now)


@dataclass
class CacheEntry:
    """Represents a cache entry for file metadata."""

    file_path: str
    id: Optional[int] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    file_mtime: Optional[float] = None
    metadata_json: Optional[str] = None
    cached_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)


@dataclass
class SessionStatistics:
    """Statistics for a session."""

    session_id: str
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    error_files: int = 0
    duplicate_files: int = 0
    total_bytes: int = 0
    processed_bytes: int = 0
    images: int = 0
    videos: int = 0
    audio: int = 0
    documents: int = 0
    duration_seconds: float = 0.0
    avg_speed_files_per_sec: float = 0.0
    avg_speed_bytes_per_sec: float = 0.0


@dataclass
class DuplicateInfo:
    """Information about a duplicate file."""

    file_hash: str
    file_extension: str
    original_path: Optional[str]
    duplicate_paths: list[str] = field(default_factory=list)
    file_size: int = 0
    space_saved: int = 0
