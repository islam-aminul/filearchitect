"""
Base processor for FileArchitect.

This module defines the base class for all file type processors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from ..core.constants import FileType, ProcessingStatus


@dataclass
class ProcessingResult:
    """Result of a file processing operation."""

    success: bool
    source_path: Path
    destination_path: Optional[Path] = None
    status: ProcessingStatus = ProcessingStatus.COMPLETED
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    file_hash: Optional[str] = None
    is_duplicate: bool = False


class BaseProcessor(ABC):
    """
    Abstract base class for file type processors.

    All file type processors (Image, Video, Audio, Document) should inherit
    from this class and implement the required methods.
    """

    def __init__(self, config: Any):
        """
        Initialize processor with configuration.

        Args:
            config: Configuration object
        """
        self.config = config

    @abstractmethod
    def get_file_type(self) -> FileType:
        """
        Get the file type this processor handles.

        Returns:
            FileType enum value
        """
        pass

    @abstractmethod
    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.

        Args:
            file_path: Path to file

        Returns:
            True if processor can handle this file, False otherwise
        """
        pass

    @abstractmethod
    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from file.

        Args:
            file_path: Path to file

        Returns:
            Dictionary of metadata

        Raises:
            ProcessingError: If metadata extraction fails
        """
        pass

    @abstractmethod
    def categorize(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        """
        Categorize file based on metadata and patterns.

        Args:
            file_path: Path to file
            metadata: File metadata

        Returns:
            Category string

        Raises:
            ProcessingError: If categorization fails
        """
        pass

    @abstractmethod
    def get_destination_path(
        self,
        file_path: Path,
        destination_root: Path,
        metadata: Dict[str, Any],
        category: str
    ) -> Path:
        """
        Generate destination path for file.

        Args:
            file_path: Source file path
            destination_root: Destination root directory
            metadata: File metadata
            category: File category

        Returns:
            Destination path

        Raises:
            ProcessingError: If path generation fails
        """
        pass

    @abstractmethod
    def process(
        self,
        source_path: Path,
        destination_path: Path,
        metadata: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Process file (copy, convert, etc.).

        Args:
            source_path: Source file path
            destination_path: Destination file path
            metadata: File metadata

        Returns:
            ProcessingResult object

        Raises:
            ProcessingError: If processing fails
        """
        pass

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate file integrity.

        Args:
            file_path: Path to file

        Returns:
            True if file is valid, False otherwise
        """
        return file_path.exists() and file_path.is_file()

    def get_file_size(self, file_path: Path) -> int:
        """
        Get file size in bytes.

        Args:
            file_path: Path to file

        Returns:
            File size in bytes
        """
        try:
            return file_path.stat().st_size
        except (OSError, FileNotFoundError):
            return 0

    def should_skip(self, file_path: Path) -> bool:
        """
        Check if file should be skipped based on configuration.

        Args:
            file_path: Path to file

        Returns:
            True if file should be skipped, False otherwise
        """
        # Check minimum file size
        if hasattr(self.config, 'min_file_size_bytes'):
            file_size = self.get_file_size(file_path)
            if file_size < self.config.min_file_size_bytes:
                return True

        return False
