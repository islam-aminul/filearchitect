"""
Disk space management for FileArchitect.

This module handles disk space checking, monitoring, and alerts to prevent
running out of space during file processing.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import shutil
import logging

from ..core.exceptions import InsufficientSpaceError

logger = logging.getLogger(__name__)


@dataclass
class SpaceInfo:
    """Disk space information."""
    path: Path
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float

    @property
    def total_gb(self) -> float:
        """Total space in GB."""
        return self.total_bytes / (1024 ** 3)

    @property
    def used_gb(self) -> float:
        """Used space in GB."""
        return self.used_bytes / (1024 ** 3)

    @property
    def free_gb(self) -> float:
        """Free space in GB."""
        return self.free_bytes / (1024 ** 3)

    def __repr__(self) -> str:
        return (
            f"SpaceInfo({self.free_gb:.2f}GB free / "
            f"{self.total_gb:.2f}GB total, {self.percent_used:.1f}% used)"
        )


class SpaceManager:
    """
    Manages disk space monitoring and alerts.

    Provides pre-flight checks, continuous monitoring, and low-space alerts.
    """

    # Default thresholds
    DEFAULT_MIN_FREE_GB = 5.0  # Minimum 5GB free space
    DEFAULT_BUFFER_PERCENT = 10  # 10% buffer for safety
    DEFAULT_EXPORT_OVERHEAD = 0.3  # 30% overhead for image exports

    def __init__(
        self,
        min_free_gb: float = DEFAULT_MIN_FREE_GB,
        buffer_percent: float = DEFAULT_BUFFER_PERCENT,
        export_overhead: float = DEFAULT_EXPORT_OVERHEAD
    ):
        """
        Initialize space manager.

        Args:
            min_free_gb: Minimum free space in GB (default: 5.0)
            buffer_percent: Buffer percentage for safety (default: 10)
            export_overhead: Overhead for image exports (default: 0.3)
        """
        self.min_free_gb = min_free_gb
        self.buffer_percent = buffer_percent
        self.export_overhead = export_overhead

    def get_space_info(self, path: Path) -> SpaceInfo:
        """
        Get disk space information for a path.

        Args:
            path: Path to check

        Returns:
            SpaceInfo object

        Raises:
            OSError: If path is not accessible
        """
        try:
            stat = shutil.disk_usage(str(path))
            return SpaceInfo(
                path=path,
                total_bytes=stat.total,
                used_bytes=stat.used,
                free_bytes=stat.free,
                percent_used=(stat.used / stat.total) * 100 if stat.total > 0 else 0
            )
        except OSError as e:
            logger.error(f"Error getting space info for {path}: {e}")
            raise

    def check_available_space(
        self,
        destination: Path,
        required_bytes: int,
        include_exports: bool = False
    ) -> Dict[str, Any]:
        """
        Check if there is enough space at destination.

        Args:
            destination: Destination path
            required_bytes: Required space in bytes
            include_exports: Include export overhead calculation

        Returns:
            Dictionary with check results:
            {
                'sufficient': bool,
                'space_info': SpaceInfo,
                'required_gb': float,
                'available_gb': float,
                'deficit_gb': float (if insufficient)
            }

        Raises:
            OSError: If path is not accessible
        """
        space_info = self.get_space_info(destination)

        # Calculate required space with overhead
        required_with_buffer = required_bytes

        # Add export overhead if needed
        if include_exports:
            required_with_buffer += int(required_bytes * self.export_overhead)

        # Add safety buffer
        required_with_buffer += int(required_bytes * (self.buffer_percent / 100))

        # Convert to GB
        required_gb = required_with_buffer / (1024 ** 3)

        # Check against minimum free space
        min_required_bytes = max(
            required_with_buffer,
            int(self.min_free_gb * (1024 ** 3))
        )

        sufficient = space_info.free_bytes >= min_required_bytes
        available_gb = space_info.free_gb

        result = {
            'sufficient': sufficient,
            'space_info': space_info,
            'required_gb': required_gb,
            'available_gb': available_gb,
            'min_free_gb': self.min_free_gb
        }

        if not sufficient:
            deficit_bytes = min_required_bytes - space_info.free_bytes
            result['deficit_gb'] = deficit_bytes / (1024 ** 3)
            logger.warning(
                f"Insufficient space: need {required_gb:.2f}GB, "
                f"have {available_gb:.2f}GB (deficit: {result['deficit_gb']:.2f}GB)"
            )

        return result

    def check_preflight(
        self,
        destination: Path,
        total_source_bytes: int,
        include_exports: bool = False
    ) -> bool:
        """
        Perform pre-flight space check.

        Args:
            destination: Destination path
            total_source_bytes: Total size of source files
            include_exports: Include export overhead calculation

        Returns:
            True if sufficient space

        Raises:
            InsufficientSpaceError: If insufficient space
            OSError: If path is not accessible
        """
        result = self.check_available_space(
            destination,
            total_source_bytes,
            include_exports
        )

        if not result['sufficient']:
            raise InsufficientSpaceError(
                f"Insufficient disk space at {destination}. "
                f"Need {result['required_gb']:.2f}GB "
                f"(including {self.buffer_percent}% buffer), "
                f"but only {result['available_gb']:.2f}GB available. "
                f"Deficit: {result['deficit_gb']:.2f}GB"
            )

        logger.info(
            f"Pre-flight check passed: {result['available_gb']:.2f}GB available, "
            f"{result['required_gb']:.2f}GB required"
        )
        return True

    def is_low_space(self, path: Path) -> bool:
        """
        Check if space is running low.

        Args:
            path: Path to check

        Returns:
            True if space is below minimum threshold
        """
        try:
            space_info = self.get_space_info(path)
            is_low = space_info.free_gb < self.min_free_gb

            if is_low:
                logger.warning(
                    f"Low space warning: {space_info.free_gb:.2f}GB free "
                    f"(threshold: {self.min_free_gb:.2f}GB)"
                )

            return is_low

        except OSError as e:
            logger.error(f"Error checking space: {e}")
            return False

    def get_space_warning_message(self, path: Path) -> Optional[str]:
        """
        Get space warning message if space is low.

        Args:
            path: Path to check

        Returns:
            Warning message or None
        """
        try:
            space_info = self.get_space_info(path)

            if space_info.free_gb < self.min_free_gb:
                return (
                    f"Low disk space at {path}!\n"
                    f"Free: {space_info.free_gb:.2f}GB / "
                    f"Total: {space_info.total_gb:.2f}GB\n"
                    f"Processing may be paused if space falls below "
                    f"{self.min_free_gb:.2f}GB."
                )

            return None

        except OSError:
            return None

    def estimate_space_needed(
        self,
        file_sizes: Dict[str, int],
        include_exports: bool = False
    ) -> Dict[str, Any]:
        """
        Estimate space needed for processing.

        Args:
            file_sizes: Dictionary of file type to total size
                e.g., {'images': 1000000, 'videos': 2000000}
            include_exports: Include export overhead for images

        Returns:
            Dictionary with estimates:
            {
                'source_size_gb': float,
                'export_overhead_gb': float,
                'buffer_gb': float,
                'total_needed_gb': float
            }
        """
        # Calculate source size
        total_bytes = sum(file_sizes.values())
        source_gb = total_bytes / (1024 ** 3)

        # Calculate export overhead (only for images)
        export_bytes = 0
        if include_exports and 'images' in file_sizes:
            export_bytes = int(file_sizes['images'] * self.export_overhead)
        export_gb = export_bytes / (1024 ** 3)

        # Calculate buffer
        buffer_bytes = int((total_bytes + export_bytes) * (self.buffer_percent / 100))
        buffer_gb = buffer_bytes / (1024 ** 3)

        # Total needed
        total_needed_bytes = total_bytes + export_bytes + buffer_bytes
        total_needed_gb = total_needed_bytes / (1024 ** 3)

        return {
            'source_size_gb': source_gb,
            'export_overhead_gb': export_gb,
            'buffer_gb': buffer_gb,
            'total_needed_gb': total_needed_gb,
            'breakdown': {
                'source': source_gb,
                'exports': export_gb,
                'buffer': buffer_gb
            }
        }

    def format_space_info(self, space_info: SpaceInfo) -> str:
        """
        Format space info as human-readable string.

        Args:
            space_info: SpaceInfo object

        Returns:
            Formatted string
        """
        return (
            f"Disk Space at {space_info.path}:\n"
            f"  Total: {space_info.total_gb:.2f} GB\n"
            f"  Used: {space_info.used_gb:.2f} GB ({space_info.percent_used:.1f}%)\n"
            f"  Free: {space_info.free_gb:.2f} GB\n"
        )

    def format_estimate(self, estimate: Dict[str, Any]) -> str:
        """
        Format space estimate as human-readable string.

        Args:
            estimate: Estimate dictionary from estimate_space_needed()

        Returns:
            Formatted string
        """
        return (
            f"Space Estimate:\n"
            f"  Source files: {estimate['source_size_gb']:.2f} GB\n"
            f"  Export overhead: {estimate['export_overhead_gb']:.2f} GB\n"
            f"  Safety buffer: {estimate['buffer_gb']:.2f} GB\n"
            f"  Total needed: {estimate['total_needed_gb']:.2f} GB\n"
        )
