"""
File scanner for FileArchitect.

This module provides recursive directory scanning with filtering and
progress tracking capabilities.
"""

import fnmatch
from pathlib import Path
from typing import Generator, Callable, Optional, List, Set
from dataclasses import dataclass

from ..core.constants import FileType
from ..core.exceptions import FileAccessError
from .detector import detect_file_type, is_supported_file_type


@dataclass
class ScanResult:
    """Result of a file scan operation."""

    file_path: Path
    file_size: int
    file_type: FileType
    is_accessible: bool
    error: Optional[str] = None


@dataclass
class ScanStatistics:
    """Statistics from a scan operation."""

    total_files: int = 0
    total_size: int = 0
    files_by_type: dict = None
    skipped_files: int = 0
    error_files: int = 0
    directories_scanned: int = 0

    def __post_init__(self):
        if self.files_by_type is None:
            self.files_by_type = {
                FileType.IMAGE: 0,
                FileType.VIDEO: 0,
                FileType.AUDIO: 0,
                FileType.DOCUMENT: 0,
                FileType.UNKNOWN: 0
            }


class FileScanner:
    """
    Recursive file scanner with filtering and progress tracking.

    Examples:
        >>> scanner = FileScanner(Path("/source"))
        >>> for result in scanner.scan():
        ...     print(result.file_path)
    """

    def __init__(
        self,
        root_path: Path,
        skip_folders: Optional[List[str]] = None,
        skip_files: Optional[List[str]] = None,
        include_hidden: bool = False,
        follow_symlinks: bool = False
    ):
        """
        Initialize file scanner.

        Args:
            root_path: Root directory to scan
            skip_folders: List of folder patterns to skip (glob patterns)
            skip_files: List of file patterns to skip (glob patterns)
            include_hidden: Whether to include hidden files/folders
            follow_symlinks: Whether to follow symbolic links
        """
        self.root_path = root_path
        self.skip_folders = skip_folders or []
        self.skip_files = skip_files or []
        self.include_hidden = include_hidden
        self.follow_symlinks = follow_symlinks
        self.statistics = ScanStatistics()
        self._scanned_paths: Set[Path] = set()  # To avoid infinite loops

    def should_skip_folder(self, folder: Path) -> bool:
        """
        Check if folder should be skipped.

        Args:
            folder: Folder path to check

        Returns:
            True if folder should be skipped, False otherwise
        """
        folder_name = folder.name

        # Skip hidden folders unless include_hidden is True
        if not self.include_hidden and folder_name.startswith('.'):
            return True

        # Check against skip patterns
        for pattern in self.skip_folders:
            if fnmatch.fnmatch(folder_name, pattern):
                return True

        return False

    def should_skip_file(self, file: Path) -> bool:
        """
        Check if file should be skipped.

        Args:
            file: File path to check

        Returns:
            True if file should be skipped, False otherwise
        """
        file_name = file.name

        # Skip hidden files unless include_hidden is True
        if not self.include_hidden and file_name.startswith('.'):
            return True

        # Check against skip patterns
        for pattern in self.skip_files:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        return False

    def scan(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        filter_supported_only: bool = False
    ) -> Generator[ScanResult, None, None]:
        """
        Scan directory recursively and yield file results.

        Args:
            progress_callback: Optional callback function(files_scanned, total_size)
            filter_supported_only: If True, only yield supported file types

        Yields:
            ScanResult objects for each file found

        Examples:
            >>> scanner = FileScanner(Path("/photos"))
            >>> for result in scanner.scan():
            ...     if result.is_accessible:
            ...         print(f"{result.file_path}: {result.file_size} bytes")
        """
        if not self.root_path.exists():
            raise FileAccessError(f"Root path does not exist: {self.root_path}")

        if not self.root_path.is_dir():
            raise FileAccessError(f"Root path is not a directory: {self.root_path}")

        # Use iterative approach to avoid recursion depth issues
        dirs_to_scan = [self.root_path]

        while dirs_to_scan:
            current_dir = dirs_to_scan.pop(0)

            # Check for infinite loops (symlinks)
            try:
                resolved = current_dir.resolve()
                if resolved in self._scanned_paths:
                    continue
                self._scanned_paths.add(resolved)
            except (OSError, RuntimeError):
                continue

            self.statistics.directories_scanned += 1

            try:
                for entry in current_dir.iterdir():
                    try:
                        # Handle directories
                        if entry.is_dir(follow_symlinks=self.follow_symlinks):
                            if not self.should_skip_folder(entry):
                                dirs_to_scan.append(entry)
                            continue

                        # Handle files
                        if not entry.is_file(follow_symlinks=self.follow_symlinks):
                            continue

                        if self.should_skip_file(entry):
                            self.statistics.skipped_files += 1
                            continue

                        # Get file info
                        file_size = entry.stat().st_size
                        is_accessible = True
                        error = None

                        try:
                            file_type = detect_file_type(entry, use_content=False)
                        except Exception as e:
                            file_type = FileType.UNKNOWN
                            error = str(e)

                        # Filter if requested
                        if filter_supported_only and file_type == FileType.UNKNOWN:
                            self.statistics.skipped_files += 1
                            continue

                        # Create result
                        result = ScanResult(
                            file_path=entry,
                            file_size=file_size,
                            file_type=file_type,
                            is_accessible=is_accessible,
                            error=error
                        )

                        # Update statistics
                        self.statistics.total_files += 1
                        self.statistics.total_size += file_size
                        self.statistics.files_by_type[file_type] += 1

                        if error:
                            self.statistics.error_files += 1

                        # Call progress callback
                        if progress_callback:
                            progress_callback(
                                self.statistics.total_files,
                                self.statistics.total_size
                            )

                        yield result

                    except (OSError, PermissionError) as e:
                        # Skip files we can't access
                        self.statistics.error_files += 1
                        continue

            except (OSError, PermissionError):
                # Skip directories we can't access
                continue

    def scan_to_list(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        filter_supported_only: bool = False
    ) -> List[ScanResult]:
        """
        Scan directory and return list of all results.

        Args:
            progress_callback: Optional callback function(files_scanned, total_size)
            filter_supported_only: If True, only return supported file types

        Returns:
            List of ScanResult objects

        Examples:
            >>> scanner = FileScanner(Path("/photos"))
            >>> results = scanner.scan_to_list()
            >>> print(f"Found {len(results)} files")
        """
        return list(self.scan(progress_callback, filter_supported_only))

    def get_statistics(self) -> ScanStatistics:
        """
        Get scan statistics.

        Returns:
            ScanStatistics object

        Examples:
            >>> scanner = FileScanner(Path("/photos"))
            >>> list(scanner.scan())  # Perform scan
            >>> stats = scanner.get_statistics()
            >>> print(f"Total files: {stats.total_files}")
        """
        return self.statistics

    def count_files(self) -> int:
        """
        Count files without yielding results (faster for large directories).

        Returns:
            Total number of files

        Examples:
            >>> scanner = FileScanner(Path("/photos"))
            >>> count = scanner.count_files()
            >>> print(f"Total: {count} files")
        """
        count = 0
        for _ in self.scan():
            count += 1
        return count

    def estimate_total_size(self) -> int:
        """
        Estimate total size of all files.

        Returns:
            Total size in bytes

        Examples:
            >>> scanner = FileScanner(Path("/photos"))
            >>> size = scanner.estimate_total_size()
            >>> print(f"Total: {size / (1024**3):.2f} GB")
        """
        total_size = 0
        for result in self.scan():
            total_size += result.file_size
        return total_size


def scan_directory(
    root_path: Path,
    skip_folders: Optional[List[str]] = None,
    skip_files: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    filter_supported_only: bool = False
) -> tuple[List[ScanResult], ScanStatistics]:
    """
    Convenience function to scan directory and return results with statistics.

    Args:
        root_path: Root directory to scan
        skip_folders: List of folder patterns to skip
        skip_files: List of file patterns to skip
        progress_callback: Optional progress callback
        filter_supported_only: If True, only return supported file types

    Returns:
        Tuple of (results list, statistics)

    Examples:
        >>> results, stats = scan_directory(Path("/photos"))
        >>> print(f"Found {stats.total_files} files")
    """
    scanner = FileScanner(root_path, skip_folders, skip_files)
    results = scanner.scan_to_list(progress_callback, filter_supported_only)
    statistics = scanner.get_statistics()

    return results, statistics


def get_file_paths(
    root_path: Path,
    file_type: Optional[FileType] = None,
    skip_folders: Optional[List[str]] = None,
    skip_files: Optional[List[str]] = None
) -> List[Path]:
    """
    Get list of file paths, optionally filtered by type.

    Args:
        root_path: Root directory to scan
        file_type: Optional file type filter
        skip_folders: List of folder patterns to skip
        skip_files: List of file patterns to skip

    Returns:
        List of file paths

    Examples:
        >>> images = get_file_paths(Path("/photos"), FileType.IMAGE)
        >>> print(f"Found {len(images)} images")
    """
    scanner = FileScanner(root_path, skip_folders, skip_files)
    paths = []

    for result in scanner.scan():
        if file_type is None or result.file_type == file_type:
            paths.append(result.file_path)

    return paths


def get_file_count_by_type(root_path: Path) -> dict:
    """
    Get count of files by type.

    Args:
        root_path: Root directory to scan

    Returns:
        Dictionary mapping FileType to count

    Examples:
        >>> counts = get_file_count_by_type(Path("/photos"))
        >>> print(f"Images: {counts[FileType.IMAGE]}")
    """
    scanner = FileScanner(root_path)
    list(scanner.scan())  # Perform scan
    return scanner.get_statistics().files_by_type
