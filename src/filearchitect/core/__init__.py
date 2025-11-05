"""
Core utilities and framework for FileArchitect.

This module contains the fundamental building blocks used throughout
the application, including logging, error handling, and utility functions.
"""

from filearchitect.core.exceptions import FileArchitectError
from filearchitect.core.logging import get_logger, setup_logging
from filearchitect.core.constants import FileType, ProcessingStatus, SessionStatus, DateSource
from filearchitect.core.detector import (
    detect_file_type,
    detect_file_type_by_extension,
    detect_file_type_by_content,
    get_mime_type,
    is_supported_file_type,
    classify_file
)
from filearchitect.core.scanner import (
    FileScanner,
    ScanResult,
    ScanStatistics,
    scan_directory,
    get_file_paths
)
from filearchitect.core.sidecar import (
    is_sidecar_file,
    find_sidecar_files,
    pair_files_with_sidecars,
    copy_sidecar_files
)
from filearchitect.core.deduplication import (
    DeduplicationEngine,
    detect_duplicates,
    calculate_space_saved
)

__all__ = [
    "FileArchitectError",
    "get_logger",
    "setup_logging",
    "FileType",
    "ProcessingStatus",
    "SessionStatus",
    "DateSource",
    "detect_file_type",
    "detect_file_type_by_extension",
    "detect_file_type_by_content",
    "get_mime_type",
    "is_supported_file_type",
    "classify_file",
    "FileScanner",
    "ScanResult",
    "ScanStatistics",
    "scan_directory",
    "get_file_paths",
    "is_sidecar_file",
    "find_sidecar_files",
    "pair_files_with_sidecars",
    "copy_sidecar_files",
    "DeduplicationEngine",
    "detect_duplicates",
    "calculate_space_saved",
]
