"""
File hashing utilities for FileArchitect.

This module provides functions for calculating file hashes
using streaming to handle large files efficiently.
"""

import hashlib
from pathlib import Path
from typing import Callable, Optional

from filearchitect.core.constants import HASH_BUFFER_SIZE


def calculate_file_hash(
    file_path: Path,
    algorithm: str = "sha256",
    buffer_size: int = HASH_BUFFER_SIZE,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """
    Calculate hash of a file using streaming.

    Args:
        file_path: Path to file to hash
        algorithm: Hash algorithm to use (sha256, md5, sha1, etc.)
        buffer_size: Size of buffer for reading file (bytes)
        progress_callback: Optional callback function(bytes_read, total_bytes)

    Returns:
        Hexadecimal hash string

    Raises:
        FileNotFoundError: If file does not exist
        OSError: If file cannot be read
        ValueError: If algorithm is not supported
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    file_size = file_path.stat().st_size
    bytes_read = 0

    with file_path.open("rb") as f:
        while True:
            chunk = f.read(buffer_size)
            if not chunk:
                break

            hasher.update(chunk)
            bytes_read += len(chunk)

            if progress_callback:
                progress_callback(bytes_read, file_size)

    return hasher.hexdigest()


def verify_file_hash(
    file_path: Path,
    expected_hash: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify a file's hash matches the expected value.

    Args:
        file_path: Path to file to verify
        expected_hash: Expected hash value (hexadecimal)
        algorithm: Hash algorithm to use

    Returns:
        True if hash matches, False otherwise
    """
    try:
        actual_hash = calculate_file_hash(file_path, algorithm)
        return actual_hash.lower() == expected_hash.lower()
    except (FileNotFoundError, OSError, ValueError):
        return False
