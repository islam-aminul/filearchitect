"""
Path manipulation utilities for FileArchitect.

This module provides functions for path handling, sanitization,
conflict resolution, and cross-platform compatibility.
"""

import re
from pathlib import Path
from typing import Optional


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename by removing or replacing invalid characters.

    Args:
        filename: Original filename to sanitize
        replacement: Character to use for replacing invalid characters

    Returns:
        Sanitized filename safe for all platforms
    """
    # Characters that are invalid on Windows
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'

    # Replace invalid characters
    sanitized = re.sub(invalid_chars, replacement, filename)

    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(". ")

    # Ensure filename is not empty
    if not sanitized:
        sanitized = "unnamed"

    # Truncate if too long (255 is common limit)
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        max_name_length = 255 - len(ext) - 1 if ext else 255
        sanitized = f"{name[:max_name_length]}.{ext}" if ext else name[:255]

    return sanitized


def resolve_conflict(
    destination_path: Path, start_index: int = 1, separator: str = "--"
) -> Path:
    """
    Resolve filename conflicts by appending a sequence number.

    Args:
        destination_path: Original destination path
        start_index: Starting index for sequence numbering
        separator: Separator between filename and sequence number

    Returns:
        Non-conflicting path with sequence number if needed

    Example:
        If 'photo.jpg' exists, returns 'photo--1.jpg'
        If 'photo--1.jpg' also exists, returns 'photo--2.jpg'
    """
    if not destination_path.exists():
        return destination_path

    stem = destination_path.stem
    suffix = destination_path.suffix
    parent = destination_path.parent

    index = start_index
    while True:
        new_name = f"{stem}{separator}{index}{suffix}"
        new_path = parent / new_name

        if not new_path.exists():
            return new_path

        index += 1


def ensure_directory(path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists

    Raises:
        PermissionError: If directory cannot be created due to permissions
        OSError: If directory creation fails for other reasons
    """
    path.mkdir(parents=True, exist_ok=True)


def get_available_space(path: Path) -> int:
    """
    Get available disk space at the specified path.

    Args:
        path: Path to check (file or directory)

    Returns:
        Available space in bytes

    Raises:
        OSError: If disk space cannot be determined
    """
    import shutil

    stat = shutil.disk_usage(path)
    return stat.free


def is_path_accessible(path: Path, mode: str = "r") -> bool:
    """
    Check if a path is accessible with the specified mode.

    Args:
        path: Path to check
        mode: Access mode ('r' for read, 'w' for write, 'rw' for both)

    Returns:
        True if path is accessible, False otherwise
    """
    if not path.exists():
        return False

    try:
        if "r" in mode:
            # Test read access
            if path.is_file():
                path.open("rb").close()
            elif path.is_dir():
                list(path.iterdir())

        if "w" in mode:
            # Test write access
            if path.is_file():
                path.open("ab").close()
            elif path.is_dir():
                test_file = path / ".write_test"
                test_file.touch()
                test_file.unlink()

        return True
    except (PermissionError, OSError):
        return False


def get_relative_path(path: Path, base: Path) -> Optional[Path]:
    """
    Get relative path from base to path.

    Args:
        path: Target path
        base: Base path

    Returns:
        Relative path, or None if paths are not related
    """
    try:
        return path.relative_to(base)
    except ValueError:
        return None
