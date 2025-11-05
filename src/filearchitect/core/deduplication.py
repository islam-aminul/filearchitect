"""
Deduplication engine for FileArchitect.

This module provides hash-based deduplication with extension category grouping.
Files are considered duplicates if they have the same hash and belong to the
same extension category (e.g., .jpg and .png are in the same category).
"""

from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from ..core.constants import FileType
from ..utils.hash import calculate_file_hash
from ..database.manager import DatabaseManager
from ..core.exceptions import FileAccessError


@dataclass
class DuplicateInfo:
    """Information about a duplicate file."""

    original_path: Path
    original_id: int
    duplicate_paths: List[Path]
    file_hash: str
    file_size: int
    extension_category: str
    space_saved: int  # Total space that would be saved by removing duplicates


class DeduplicationEngine:
    """
    Hash-based deduplication engine with database integration.

    Examples:
        >>> engine = DeduplicationEngine(db_manager)
        >>> is_dup, original = engine.check_duplicate(Path("photo.jpg"), "abc123", ".jpg")
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize deduplication engine.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self._hash_cache: Dict[str, str] = {}  # Path -> Hash mapping

    def calculate_and_cache_hash(
        self,
        file_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Calculate file hash and cache it in database.

        Args:
            file_path: Path to file
            progress_callback: Optional progress callback for large files

        Returns:
            File hash (SHA-256)

        Raises:
            FileAccessError: If file cannot be read

        Examples:
            >>> engine = DeduplicationEngine(db_manager)
            >>> hash_val = engine.calculate_and_cache_hash(Path("photo.jpg"))
        """
        file_path_str = str(file_path)

        # Check memory cache first
        if file_path_str in self._hash_cache:
            return self._hash_cache[file_path_str]

        # Check database cache
        try:
            file_mtime = file_path.stat().st_mtime
            cached_hash = self.db_manager.get_cached_hash(file_path_str, file_mtime)

            if cached_hash:
                self._hash_cache[file_path_str] = cached_hash
                return cached_hash

        except (OSError, Exception):
            pass

        # Calculate hash
        try:
            file_hash = calculate_file_hash(file_path, progress_callback)

            # Cache in database
            try:
                file_size = file_path.stat().st_size
                file_mtime = file_path.stat().st_mtime
                self.db_manager.cache_file_hash(
                    file_path_str,
                    file_hash,
                    file_size,
                    file_mtime
                )
            except Exception:
                pass

            # Cache in memory
            self._hash_cache[file_path_str] = file_hash

            return file_hash

        except Exception as e:
            raise FileAccessError(f"Failed to calculate hash for {file_path}: {e}") from e

    def check_duplicate(
        self,
        file_path: Path,
        file_hash: Optional[str] = None,
        file_extension: Optional[str] = None
    ) -> tuple[bool, Optional[int]]:
        """
        Check if file is a duplicate.

        Args:
            file_path: Path to file
            file_hash: Optional pre-calculated hash
            file_extension: Optional file extension (with dot)

        Returns:
            Tuple of (is_duplicate, original_file_id)

        Examples:
            >>> engine = DeduplicationEngine(db_manager)
            >>> is_dup, orig_id = engine.check_duplicate(Path("photo.jpg"))
        """
        # Get hash if not provided
        if file_hash is None:
            try:
                file_hash = self.calculate_and_cache_hash(file_path)
            except FileAccessError:
                return False, None

        # Get extension if not provided
        if file_extension is None:
            file_extension = file_path.suffix.lower()

        # Check in database
        original_id = self.db_manager.check_duplicate(file_hash, file_extension)

        return original_id is not None, original_id

    def register_file(
        self,
        file_path: Path,
        file_hash: str,
        file_extension: str,
        file_id: int
    ) -> None:
        """
        Register a file in the deduplication system.

        Creates or updates duplicate group.

        Args:
            file_path: Path to file
            file_hash: File hash
            file_extension: File extension
            file_id: Database file ID

        Examples:
            >>> engine.register_file(Path("photo.jpg"), "abc123", ".jpg", 1)
        """
        # Check if this is a duplicate
        is_duplicate, original_id = self.check_duplicate(
            file_path,
            file_hash,
            file_extension
        )

        if is_duplicate:
            # Update existing duplicate group
            self.db_manager.create_or_update_duplicate_group(
                file_hash,
                file_extension,
                original_id
            )
        else:
            # Create new duplicate group with this file as original
            self.db_manager.create_or_update_duplicate_group(
                file_hash,
                file_extension,
                file_id
            )

    def find_duplicates_in_list(
        self,
        file_paths: List[Path],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, List[Path]]:
        """
        Find duplicates within a list of files.

        Args:
            file_paths: List of file paths to check
            progress_callback: Optional progress callback(current, total)

        Returns:
            Dictionary mapping hash to list of duplicate file paths

        Examples:
            >>> files = [Path("photo1.jpg"), Path("photo2.jpg"), Path("photo3.jpg")]
            >>> duplicates = engine.find_duplicates_in_list(files)
            >>> # Returns {"abc123": [Path("photo1.jpg"), Path("photo2.jpg")]}
        """
        hash_to_paths: Dict[str, List[Path]] = {}
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            try:
                file_hash = self.calculate_and_cache_hash(file_path)

                if file_hash not in hash_to_paths:
                    hash_to_paths[file_hash] = []

                hash_to_paths[file_hash].append(file_path)

                if progress_callback:
                    progress_callback(i + 1, total)

            except FileAccessError:
                continue

        # Filter to only include actual duplicates (hash with 2+ files)
        duplicates = {
            hash_val: paths
            for hash_val, paths in hash_to_paths.items()
            if len(paths) > 1
        }

        return duplicates

    def get_duplicate_statistics(self) -> Dict[str, int]:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with statistics

        Examples:
            >>> stats = engine.get_duplicate_statistics()
            >>> print(f"Total duplicates: {stats['total_duplicates']}")
        """
        # This would query the database for statistics
        # For now, return empty dict as placeholder
        return {
            'total_duplicates': 0,
            'space_saved': 0,
            'duplicate_groups': 0
        }

    def clear_cache(self) -> None:
        """
        Clear the in-memory hash cache.

        Examples:
            >>> engine.clear_cache()
        """
        self._hash_cache.clear()


def detect_duplicates(
    file_paths: List[Path],
    db_manager: Optional[DatabaseManager] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, List[Path]]:
    """
    Convenience function to detect duplicates in a list of files.

    Args:
        file_paths: List of file paths
        db_manager: Optional database manager for caching
        progress_callback: Optional progress callback

    Returns:
        Dictionary mapping hash to list of duplicate paths

    Examples:
        >>> files = [Path("photo1.jpg"), Path("photo2.jpg")]
        >>> duplicates = detect_duplicates(files)
    """
    if db_manager:
        engine = DeduplicationEngine(db_manager)
        return engine.find_duplicates_in_list(file_paths, progress_callback)
    else:
        # Without database, use simple dict
        hash_to_paths: Dict[str, List[Path]] = {}
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            try:
                file_hash = calculate_file_hash(file_path)

                if file_hash not in hash_to_paths:
                    hash_to_paths[file_hash] = []

                hash_to_paths[file_hash].append(file_path)

                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception:
                continue

        # Filter to only duplicates
        return {
            h: p for h, p in hash_to_paths.items() if len(p) > 1
        }


def calculate_space_saved(duplicate_groups: Dict[str, List[Path]]) -> int:
    """
    Calculate total space that would be saved by removing duplicates.

    Keeps the first file in each group and calculates space saved from others.

    Args:
        duplicate_groups: Dictionary mapping hash to list of paths

    Returns:
        Total space saved in bytes

    Examples:
        >>> duplicates = {"abc": [Path("file1.jpg"), Path("file2.jpg")]}
        >>> space = calculate_space_saved(duplicates)
    """
    total_saved = 0

    for file_paths in duplicate_groups.values():
        if len(file_paths) < 2:
            continue

        # Get size of first file (the one we'd keep)
        try:
            file_size = file_paths[0].stat().st_size

            # Calculate space saved from duplicates
            # (We save space for n-1 duplicates)
            total_saved += file_size * (len(file_paths) - 1)

        except (OSError, FileNotFoundError):
            continue

    return total_saved


def group_duplicates_by_extension(
    duplicate_groups: Dict[str, List[Path]]
) -> Dict[str, Dict[str, List[Path]]]:
    """
    Group duplicates by file extension.

    Args:
        duplicate_groups: Dictionary mapping hash to list of paths

    Returns:
        Nested dictionary: extension -> hash -> paths

    Examples:
        >>> duplicates = {"abc": [Path("file1.jpg"), Path("file2.png")]}
        >>> by_ext = group_duplicates_by_extension(duplicates)
    """
    by_extension: Dict[str, Dict[str, List[Path]]] = {}

    for file_hash, paths in duplicate_groups.items():
        for path in paths:
            ext = path.suffix.lower()

            if ext not in by_extension:
                by_extension[ext] = {}

            if file_hash not in by_extension[ext]:
                by_extension[ext][file_hash] = []

            by_extension[ext][file_hash].append(path)

    return by_extension


def rank_duplicates(duplicate_paths: List[Path]) -> List[Path]:
    """
    Rank duplicate files to determine which to keep.

    Ranking criteria (in order):
    1. Shortest path (likely original location)
    2. Earliest modification time
    3. Lexicographic order

    Args:
        duplicate_paths: List of duplicate file paths

    Returns:
        Sorted list with best candidate first

    Examples:
        >>> paths = [Path("/backup/photo.jpg"), Path("/photos/photo.jpg")]
        >>> ranked = rank_duplicates(paths)
        >>> # Returns [Path("/photos/photo.jpg"), Path("/backup/photo.jpg")]
    """
    def rank_key(path: Path) -> tuple:
        try:
            # Get modification time
            mtime = path.stat().st_mtime
        except (OSError, FileNotFoundError):
            mtime = float('inf')

        # Return tuple for sorting: (path_length, mtime, str_path)
        return (len(str(path)), mtime, str(path))

    return sorted(duplicate_paths, key=rank_key)
