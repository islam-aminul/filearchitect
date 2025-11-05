"""
Utility modules for FileArchitect.

This package contains various utility functions and classes for
path handling, file operations, date parsing, and more.
"""

from filearchitect.utils.path import sanitize_filename, resolve_conflict
from filearchitect.utils.hash import calculate_file_hash
from filearchitect.utils.datetime import (
    parse_exif_date,
    parse_filename_date,
    parse_folder_date,
    parse_date_with_fallback,
    format_datetime_for_filename,
    validate_date,
)
from filearchitect.utils.filesystem import (
    copy_file_streaming,
    move_file_safe,
    copy_file_atomic,
    calculate_directory_size,
    check_file_permissions,
    is_file_locked,
    safe_delete_file,
    safe_delete_directory,
    remove_empty_directories,
)

__all__ = [
    "sanitize_filename",
    "resolve_conflict",
    "calculate_file_hash",
    "parse_exif_date",
    "parse_filename_date",
    "parse_folder_date",
    "parse_date_with_fallback",
    "format_datetime_for_filename",
    "validate_date",
    "copy_file_streaming",
    "move_file_safe",
    "copy_file_atomic",
    "calculate_directory_size",
    "check_file_permissions",
    "is_file_locked",
    "safe_delete_file",
    "safe_delete_directory",
    "remove_empty_directories",
]
