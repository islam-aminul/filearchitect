"""
Document processor for FileArchitect.

This module handles document file processing including categorization
and organization.
"""

from pathlib import Path
from typing import Dict, Any

from ..core.constants import FileType, ProcessingStatus
from ..core.exceptions import ProcessingError
from ..utils.filesystem import copy_file_atomic
from .base import BaseProcessor, ProcessingResult


class DocumentProcessor(BaseProcessor):
    """
    Processor for document files.

    Handles categorization and organization of documents.
    """

    def __init__(self, config: Any):
        """
        Initialize document processor.

        Args:
            config: Configuration object
        """
        super().__init__(config)

    def get_file_type(self) -> FileType:
        """Get the file type this processor handles."""
        return FileType.DOCUMENT

    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.

        Args:
            file_path: Path to file

        Returns:
            True if processor can handle this file
        """
        from ..core.detector import detect_file_type
        return detect_file_type(file_path) == FileType.DOCUMENT

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from document file.

        Args:
            file_path: Path to document file

        Returns:
            Dictionary of metadata
        """
        metadata = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix.lower(),
        }

        # Get file size
        try:
            metadata['file_size'] = file_path.stat().st_size
        except (OSError, FileNotFoundError):
            metadata['file_size'] = 0

        return metadata

    def categorize(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        """
        Categorize document file by type.

        Categories based on extension:
        - PDF: PDF documents
        - Text: Text files (.txt, .rtf, .md)
        - Word: Word documents (.doc, .docx, .odt)
        - Excel: Spreadsheets (.xls, .xlsx, .ods, .csv)
        - PowerPoint: Presentations (.ppt, .pptx, .odp)
        - Code: Source code files
        - Other: Other documents

        Args:
            file_path: Path to file
            metadata: File metadata

        Returns:
            Category string
        """
        extension = file_path.suffix.lower()

        # PDF
        if extension == '.pdf':
            return 'PDF'

        # Text
        elif extension in {'.txt', '.rtf', '.md', '.markdown'}:
            return 'Text'

        # Word
        elif extension in {'.doc', '.docx', '.odt'}:
            return 'Word'

        # Excel
        elif extension in {'.xls', '.xlsx', '.ods', '.csv'}:
            return 'Excel'

        # PowerPoint
        elif extension in {'.ppt', '.pptx', '.odp'}:
            return 'PowerPoint'

        # Code files
        elif extension in {
            '.py', '.js', '.java', '.cpp', '.c', '.h', '.cs', '.php',
            '.html', '.css', '.xml', '.json', '.yaml', '.yml',
            '.sql', '.sh', '.bat', '.ps1', '.rb', '.go', '.rs', '.swift',
            '.kt', '.ts', '.jsx', '.tsx', '.vue', '.r', '.m', '.pl'
        }:
            return 'Code'

        # Other
        else:
            return 'Other'

    def get_destination_path(
        self,
        file_path: Path,
        destination_root: Path,
        metadata: Dict[str, Any],
        category: str
    ) -> Path:
        """
        Generate destination path for document.

        Structure:
        - Documents/[Category]/filename.ext

        Args:
            file_path: Source file path
            destination_root: Destination root directory
            metadata: File metadata
            category: File category

        Returns:
            Destination path
        """
        parts = [destination_root, 'Documents', category]

        # Add filename
        dest_dir = Path(*parts)
        dest_path = dest_dir / file_path.name

        return dest_path

    def process(
        self,
        source_path: Path,
        destination_path: Path,
        metadata: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Process document file (copy to destination).

        Args:
            source_path: Source file path
            destination_path: Destination file path
            metadata: File metadata

        Returns:
            ProcessingResult object

        Raises:
            ProcessingError: If processing fails
        """
        try:
            # Ensure destination directory exists
            destination_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            copy_file_atomic(source_path, destination_path)

            # Create result
            result = ProcessingResult(
                success=True,
                source_path=source_path,
                destination_path=destination_path,
                status=ProcessingStatus.COMPLETED,
                category=metadata.get('category'),
                metadata=metadata
            )

            return result

        except Exception as e:
            raise ProcessingError(f"Failed to process document {source_path}: {e}") from e
