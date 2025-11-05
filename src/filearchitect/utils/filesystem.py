"""
File system operation utilities for FileArchitect.

This module provides functions for safe file operations including copying,
moving, atomic operations, and file system checks.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Callable
import platform

from ..core.exceptions import FileAccessError, DiskSpaceError


def copy_file_streaming(
    source: Path,
    destination: Path,
    buffer_size: int = 65536,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> None:
    """
    Copy a file with streaming and optional progress callback.

    Args:
        source: Source file path
        destination: Destination file path
        buffer_size: Size of read/write buffer in bytes (default 64KB)
        progress_callback: Optional callback function(bytes_copied, total_bytes)

    Raises:
        FileAccessError: If source cannot be read or destination cannot be written
        DiskSpaceError: If insufficient disk space

    Examples:
        >>> def progress(copied, total):
        ...     print(f"Progress: {copied}/{total} bytes")
        >>> copy_file_streaming(Path("source.txt"), Path("dest.txt"), progress_callback=progress)
    """
    if not source.exists():
        raise FileAccessError(f"Source file does not exist: {source}")

    if not source.is_file():
        raise FileAccessError(f"Source is not a file: {source}")

    # Check if we have enough space
    file_size = source.stat().st_size
    available_space = shutil.disk_usage(destination.parent).free

    if available_space < file_size:
        raise DiskSpaceError(
            f"Insufficient disk space. Need {file_size} bytes, have {available_space} bytes"
        )

    # Ensure destination directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        bytes_copied = 0
        with source.open('rb') as src, destination.open('wb') as dst:
            while True:
                chunk = src.read(buffer_size)
                if not chunk:
                    break

                dst.write(chunk)
                bytes_copied += len(chunk)

                if progress_callback:
                    progress_callback(bytes_copied, file_size)

    except (IOError, OSError) as e:
        # Clean up partial file on error
        if destination.exists():
            destination.unlink()
        raise FileAccessError(f"Failed to copy file: {e}") from e


def move_file_safe(source: Path, destination: Path) -> None:
    """
    Move file safely with fallback to copy+delete on cross-device moves.

    Args:
        source: Source file path
        destination: Destination file path

    Raises:
        FileAccessError: If move fails
    """
    if not source.exists():
        raise FileAccessError(f"Source file does not exist: {source}")

    # Ensure destination directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Try atomic rename first (only works on same filesystem)
        source.rename(destination)
    except OSError:
        # Fallback to copy + delete for cross-device moves
        try:
            copy_file_streaming(source, destination)
            source.unlink()
        except Exception as e:
            # Clean up destination on error
            if destination.exists():
                destination.unlink()
            raise FileAccessError(f"Failed to move file: {e}") from e


def copy_file_atomic(source: Path, destination: Path) -> None:
    """
    Copy file atomically using temp file and rename.

    This ensures that the destination file is either fully written or not present at all,
    preventing partial file writes.

    Args:
        source: Source file path
        destination: Destination file path

    Raises:
        FileAccessError: If copy fails
    """
    if not source.exists():
        raise FileAccessError(f"Source file does not exist: {source}")

    # Ensure destination directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory as destination
    temp_fd, temp_path = tempfile.mkstemp(
        dir=destination.parent,
        prefix=".tmp_",
        suffix=destination.suffix
    )

    try:
        # Close the file descriptor and use Path operations
        os.close(temp_fd)
        temp_file = Path(temp_path)

        # Copy to temp file
        copy_file_streaming(source, temp_file)

        # Atomic rename
        temp_file.rename(destination)

    except Exception as e:
        # Clean up temp file on error
        temp_file = Path(temp_path)
        if temp_file.exists():
            temp_file.unlink()
        raise FileAccessError(f"Atomic copy failed: {e}") from e


def calculate_directory_size(directory: Path) -> int:
    """
    Calculate total size of all files in a directory recursively.

    Args:
        directory: Directory path

    Returns:
        Total size in bytes

    Examples:
        >>> size = calculate_directory_size(Path("/path/to/dir"))
        >>> print(f"Directory size: {size / (1024**3):.2f} GB")
    """
    if not directory.exists():
        return 0

    if directory.is_file():
        return directory.stat().st_size

    total_size = 0
    try:
        for entry in directory.rglob('*'):
            if entry.is_file():
                try:
                    total_size += entry.stat().st_size
                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue
    except (OSError, PermissionError):
        # Skip directories we can't access
        pass

    return total_size


def check_file_permissions(path: Path, require_read: bool = True, require_write: bool = False) -> bool:
    """
    Check if file has required permissions.

    Args:
        path: File path to check
        require_read: Whether read permission is required
        require_write: Whether write permission is required

    Returns:
        True if file has required permissions, False otherwise

    Examples:
        >>> check_file_permissions(Path("file.txt"), require_read=True)
        True
    """
    if not path.exists():
        return False

    try:
        mode = path.stat().st_mode

        if require_read:
            if not os.access(path, os.R_OK):
                return False

        if require_write:
            if not os.access(path, os.W_OK):
                return False

        return True

    except (OSError, PermissionError):
        return False


def is_file_locked(path: Path) -> bool:
    """
    Check if file is locked by another process.

    Args:
        path: File path to check

    Returns:
        True if file is locked, False otherwise

    Note:
        This is a best-effort check and may not be 100% reliable on all platforms.

    Examples:
        >>> is_file_locked(Path("file.txt"))
        False
    """
    if not path.exists():
        return False

    if not path.is_file():
        return False

    # Try to open file in exclusive mode
    try:
        # On Windows, this will fail if file is locked
        if platform.system() == 'Windows':
            # Try to rename to itself (fails if locked on Windows)
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateFileW(
                str(path),
                0x80000000,  # GENERIC_READ
                0,  # No sharing
                None,
                3,  # OPEN_EXISTING
                0,
                None
            )
            if handle == -1:
                return True
            kernel32.CloseHandle(handle)
            return False
        else:
            # On Unix-like systems, try to open for writing
            with path.open('rb+') as f:
                import fcntl
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    return False
                except (IOError, OSError):
                    return True

    except (IOError, OSError, ImportError, AttributeError):
        # If we can't determine, assume not locked
        return False


def create_temp_file(suffix: str = "", prefix: str = "tmp_", directory: Optional[Path] = None) -> Path:
    """
    Create a temporary file and return its path.

    Args:
        suffix: File suffix (e.g., ".jpg")
        prefix: File prefix
        directory: Directory for temp file (default: system temp dir)

    Returns:
        Path to created temporary file

    Examples:
        >>> temp_file = create_temp_file(suffix=".jpg")
        >>> # Use temp_file...
        >>> temp_file.unlink()  # Clean up
    """
    fd, temp_path = tempfile.mkstemp(
        suffix=suffix,
        prefix=prefix,
        dir=directory
    )
    os.close(fd)
    return Path(temp_path)


def create_temp_directory(suffix: str = "", prefix: str = "tmp_", parent: Optional[Path] = None) -> Path:
    """
    Create a temporary directory and return its path.

    Args:
        suffix: Directory suffix
        prefix: Directory prefix
        parent: Parent directory for temp dir (default: system temp dir)

    Returns:
        Path to created temporary directory

    Examples:
        >>> temp_dir = create_temp_directory()
        >>> # Use temp_dir...
        >>> shutil.rmtree(temp_dir)  # Clean up
    """
    temp_path = tempfile.mkdtemp(
        suffix=suffix,
        prefix=prefix,
        dir=parent
    )
    return Path(temp_path)


def safe_delete_file(path: Path, missing_ok: bool = True) -> bool:
    """
    Safely delete a file.

    Args:
        path: File path to delete
        missing_ok: If True, don't raise error if file doesn't exist

    Returns:
        True if file was deleted, False if file didn't exist and missing_ok=True

    Raises:
        FileAccessError: If deletion fails

    Examples:
        >>> safe_delete_file(Path("unwanted.txt"))
        True
    """
    if not path.exists():
        if missing_ok:
            return False
        raise FileAccessError(f"File does not exist: {path}")

    try:
        path.unlink()
        return True
    except (OSError, PermissionError) as e:
        raise FileAccessError(f"Failed to delete file: {e}") from e


def safe_delete_directory(path: Path, missing_ok: bool = True, recursive: bool = False) -> bool:
    """
    Safely delete a directory.

    Args:
        path: Directory path to delete
        missing_ok: If True, don't raise error if directory doesn't exist
        recursive: If True, delete directory and all contents

    Returns:
        True if directory was deleted, False if didn't exist and missing_ok=True

    Raises:
        FileAccessError: If deletion fails

    Examples:
        >>> safe_delete_directory(Path("temp_dir"), recursive=True)
        True
    """
    if not path.exists():
        if missing_ok:
            return False
        raise FileAccessError(f"Directory does not exist: {path}")

    try:
        if recursive:
            shutil.rmtree(path)
        else:
            path.rmdir()
        return True
    except (OSError, PermissionError) as e:
        raise FileAccessError(f"Failed to delete directory: {e}") from e


def remove_empty_directories(root: Path, remove_root: bool = False) -> int:
    """
    Remove all empty directories under root recursively.

    Args:
        root: Root directory to start from
        remove_root: Whether to remove root directory if empty

    Returns:
        Number of directories removed

    Examples:
        >>> count = remove_empty_directories(Path("/path/to/dir"))
        >>> print(f"Removed {count} empty directories")
    """
    if not root.exists() or not root.is_dir():
        return 0

    removed_count = 0

    # Walk bottom-up so we process leaf directories first
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        dir_path = Path(dirpath)

        # Skip root unless remove_root is True
        if dir_path == root and not remove_root:
            continue

        # Check if directory is empty
        try:
            if not any(dir_path.iterdir()):
                dir_path.rmdir()
                removed_count += 1
        except (OSError, PermissionError):
            # Skip directories we can't delete
            continue

    return removed_count


def get_file_count(directory: Path, pattern: str = "*", recursive: bool = True) -> int:
    """
    Count files in a directory.

    Args:
        directory: Directory to count files in
        pattern: Glob pattern to match (default: all files)
        recursive: Whether to count recursively

    Returns:
        Number of files matching pattern

    Examples:
        >>> count = get_file_count(Path("/photos"), pattern="*.jpg")
        >>> print(f"Found {count} JPEG files")
    """
    if not directory.exists() or not directory.is_dir():
        return 0

    try:
        if recursive:
            return sum(1 for _ in directory.rglob(pattern) if _.is_file())
        else:
            return sum(1 for _ in directory.glob(pattern) if _.is_file())
    except (OSError, PermissionError):
        return 0
