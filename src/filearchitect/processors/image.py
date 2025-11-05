"""
Image processor for FileArchitect.

This module handles image file processing including categorization,
organization, and JPEG export.
"""

import fnmatch
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.constants import FileType, ProcessingStatus, RAW_EXTENSIONS
from ..core.exceptions import ProcessingError
from ..utils.datetime import (
    parse_date_with_fallback,
    format_datetime_for_filename,
    get_year_from_date
)
from ..utils.filesystem import copy_file_streaming, copy_file_atomic
from ..core.sidecar import find_sidecar_files, copy_sidecar_files
from .base import BaseProcessor, ProcessingResult
from .metadata import ImageMetadataExtractor


class ImageProcessor(BaseProcessor):
    """
    Processor for image files.

    Handles metadata extraction, categorization, organization, and JPEG export.
    """

    def __init__(self, config: Any):
        """
        Initialize image processor.

        Args:
            config: Configuration object
        """
        super().__init__(config)
        self.metadata_extractor = ImageMetadataExtractor()

    def get_file_type(self) -> FileType:
        """Get the file type this processor handles."""
        return FileType.IMAGE

    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.

        Args:
            file_path: Path to file

        Returns:
            True if processor can handle this file
        """
        from ..core.detector import detect_file_type
        return detect_file_type(file_path) == FileType.IMAGE

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from image file.

        Args:
            file_path: Path to image file

        Returns:
            Dictionary of metadata

        Raises:
            ProcessingError: If extraction fails
        """
        try:
            metadata = self.metadata_extractor.extract_metadata(file_path)

            # Add date from fallback sources if no EXIF date
            if 'date_taken' not in metadata:
                date_taken, date_source = parse_date_with_fallback(
                    filename=file_path.name,
                    folder_path=str(file_path.parent)
                )
                if date_taken:
                    metadata['date_taken'] = date_taken
                    metadata['date_source'] = date_source

            return metadata

        except Exception as e:
            raise ProcessingError(f"Failed to extract metadata from {file_path}: {e}") from e

    def categorize(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        """
        Categorize image file.

        Categories:
        - RAW: RAW format images
        - Edited: Images with editing software in metadata
        - Screenshots: Screenshot patterns
        - Social Media: Social media filename patterns
        - Hidden: Hidden files (AAE, system files)
        - Originals: Camera originals with EXIF
        - Export: Images without camera info
        - Collection: Fallback category

        Args:
            file_path: Path to file
            metadata: File metadata

        Returns:
            Category string
        """
        file_name = file_path.name
        extension = file_path.suffix.lower()

        # 1. Check for RAW format
        if metadata.get('is_raw', False):
            return 'RAW'

        # 2. Check for edited images
        if self._is_edited(metadata):
            return 'Edited'

        # 3. Check for screenshots
        if self._is_screenshot(file_name, metadata):
            return 'Screenshots'

        # 4. Check for social media
        if self._is_social_media(file_name):
            return 'Social Media'

        # 5. Check for hidden files (like .AAE)
        if file_name.startswith('.') or extension == '.aae':
            # Check if there's a corresponding main file
            if self._has_corresponding_file(file_path):
                return 'Hidden'

        # 6. Check for originals (camera photos with EXIF)
        if self._has_camera_info(metadata):
            return 'Originals'

        # 7. Export (images with EXIF date but no camera info)
        if self.metadata_extractor.has_exif_date(metadata):
            return 'Export'

        # 8. Collection (fallback)
        return 'Collection'

    def _is_edited(self, metadata: Dict[str, Any]) -> bool:
        """Check if image was edited."""
        patterns = self.config.detection.edited_software
        return self.metadata_extractor.is_edited(metadata, patterns)

    def _is_screenshot(self, file_name: str, metadata: Dict[str, Any]) -> bool:
        """Check if image is a screenshot."""
        # Check filename patterns
        patterns = self.config.detection.screenshots
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        # Check dimensions (common screenshot resolutions)
        width, height = self.metadata_extractor.get_dimensions(metadata)
        if width > 0 and height > 0:
            # Common screen resolutions
            common_resolutions = [
                (1920, 1080), (2560, 1440), (3840, 2160),  # 16:9
                (1680, 1050), (1920, 1200), (2560, 1600),  # 16:10
                (1440, 900), (2880, 1800),  # 16:10 Mac
                (828, 1792), (1170, 2532), (1284, 2778),  # iPhone
                (1440, 2960), (1440, 3040), (1440, 3200),  # Android
            ]

            # Check if matches common resolution (±10 pixels)
            for res_w, res_h in common_resolutions:
                if (abs(width - res_w) <= 10 and abs(height - res_h) <= 10) or \
                   (abs(width - res_h) <= 10 and abs(height - res_w) <= 10):
                    return True

        return False

    def _is_social_media(self, file_name: str) -> bool:
        """Check if image is from social media."""
        patterns = self.config.detection.social_media_images
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True
        return False

    def _has_corresponding_file(self, file_path: Path) -> bool:
        """Check if hidden file has a corresponding main file."""
        # Look for file with same base name but different extension
        base_name = file_path.stem
        parent = file_path.parent

        for sibling in parent.glob(f"{base_name}.*"):
            if sibling != file_path and not sibling.name.startswith('.'):
                return True

        return False

    def _has_camera_info(self, metadata: Dict[str, Any]) -> bool:
        """Check if metadata has camera information."""
        make, model = self.metadata_extractor.get_camera_info(metadata)
        return bool(make or model)

    def get_destination_path(
        self,
        file_path: Path,
        destination_root: Path,
        metadata: Dict[str, Any],
        category: str
    ) -> Path:
        """
        Generate destination path for image.

        Structure examples:
        - Originals: Images/Originals/[Make - Model]/[Year]/filename.ext
        - Export: Images/Export/[Year]/filename.ext
        - RAW: Images/RAW/[Make - Model]/[Year]/filename.ext
        - Edited: Images/Edited/[Year]/filename.ext
        - Screenshots: Images/Screenshots/filename.ext
        - Social Media: Images/Social Media/filename.ext
        - Collection: Images/Collection/[file-type]/filename.ext
        - Hidden: Images/Hidden/filename.ext

        Args:
            file_path: Source file path
            destination_root: Destination root directory
            metadata: File metadata
            category: File category

        Returns:
            Destination path
        """
        parts = [destination_root, 'Images']

        # Get date for year folder
        date_taken = self.metadata_extractor.get_date_taken(metadata)
        year = get_year_from_date(date_taken) if date_taken else None

        # Get camera info
        make, model = self.metadata_extractor.get_camera_info(metadata)
        camera_folder = f"{make} - {model}" if make and model else (make or model or "Unknown")

        if category == 'Originals':
            parts.extend(['Originals', camera_folder])
            if year:
                parts.append(year)

        elif category == 'Export':
            parts.append('Export')
            if year:
                parts.append(year)

        elif category == 'RAW':
            parts.extend(['RAW', camera_folder])
            if year:
                parts.append(year)

        elif category == 'Edited':
            parts.append('Edited')
            if year:
                parts.append(year)

        elif category == 'Screenshots':
            parts.append('Screenshots')

        elif category == 'Social Media':
            parts.append('Social Media')

        elif category == 'Hidden':
            parts.append('Hidden')

        elif category == 'Collection':
            parts.append('Collection')
            # Organize by file type
            file_type = metadata.get('format', file_path.suffix.lstrip('.'))
            parts.append(file_type)

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
        Process image file (copy to destination).

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

            # Copy sidecar files if any
            copy_sidecar_files(source_path, destination_path)

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
            raise ProcessingError(f"Failed to process image {source_path}: {e}") from e

    def generate_export_filename(
        self,
        source_path: Path,
        metadata: Dict[str, Any],
        sequence_number: Optional[int] = None
    ) -> str:
        """
        Generate filename for exported JPEG.

        Format: yyyy-mm-dd hh-mm-ss[[-NNN]] -- [Make] - [Model] -- [original name].jpg

        Args:
            source_path: Source file path
            metadata: File metadata
            sequence_number: Optional sequence number for burst photos

        Returns:
            Generated filename

        Examples:
            >>> generate_export_filename(Path("DSC_1234.jpg"), metadata)
            '2023-11-05 14-30-45 -- Canon - EOS R5 -- DSC_1234.jpg'
        """
        parts = []

        # Date and time
        date_taken = self.metadata_extractor.get_date_taken(metadata)
        if date_taken:
            date_str = format_datetime_for_filename(date_taken)
            parts.append(date_str)

            # Add sequence number for burst photos
            if sequence_number is not None:
                parts[0] = f"{parts[0]}-{sequence_number:03d}"
        else:
            # Use original filename start if no date
            parts.append(source_path.stem)

        # Camera info
        make, model = self.metadata_extractor.get_camera_info(metadata)
        if make or model:
            camera_str = f"{make} - {model}" if make and model else (make or model)
            parts.append(camera_str)

        # Original name
        parts.append(source_path.stem)

        # Join and add extension
        filename = ' -- '.join(parts) + '.jpg'

        return filename
