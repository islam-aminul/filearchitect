"""
Image metadata extraction for FileArchitect.

This module provides EXIF and other metadata extraction from image files.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.constants import DateSource, RAW_EXTENSIONS
from ..core.exceptions import MetadataError
from ..utils.datetime import parse_exif_date

# Try to import image libraries
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import piexif
    PIEXIF_AVAILABLE = True
except ImportError:
    PIEXIF_AVAILABLE = False

try:
    import rawpy
    RAWPY_AVAILABLE = True
except ImportError:
    RAWPY_AVAILABLE = False


class ImageMetadataExtractor:
    """
    Extract metadata from image files including EXIF data.

    Supports standard formats (JPEG, PNG, etc.) and RAW formats.
    """

    def __init__(self):
        """Initialize metadata extractor."""
        self.pil_available = PIL_AVAILABLE
        self.piexif_available = PIEXIF_AVAILABLE
        self.rawpy_available = RAWPY_AVAILABLE

    def is_raw_format(self, file_path: Path) -> bool:
        """
        Check if file is a RAW format.

        Args:
            file_path: Path to file

        Returns:
            True if RAW format, False otherwise
        """
        extension = file_path.suffix.lower()
        return extension in RAW_EXTENSIONS

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from image file.

        Args:
            file_path: Path to image file

        Returns:
            Dictionary of metadata

        Raises:
            MetadataError: If extraction fails
        """
        if not file_path.exists():
            raise MetadataError(f"File does not exist: {file_path}")

        metadata = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix.lower(),
            'is_raw': self.is_raw_format(file_path),
        }

        # Try RAW extraction first if applicable
        if metadata['is_raw'] and self.rawpy_available:
            try:
                raw_metadata = self._extract_raw_metadata(file_path)
                metadata.update(raw_metadata)
                return metadata
            except Exception:
                pass  # Fall through to PIL

        # Try PIL/Pillow extraction
        if self.pil_available:
            try:
                pil_metadata = self._extract_pil_metadata(file_path)
                metadata.update(pil_metadata)
            except Exception as e:
                # Not fatal, continue with what we have
                metadata['extraction_error'] = str(e)

        # Try piexif for more detailed EXIF
        if self.piexif_available:
            try:
                exif_metadata = self._extract_piexif_metadata(file_path)
                metadata.update(exif_metadata)
            except Exception:
                pass  # Not fatal

        return metadata

    def _extract_pil_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata using PIL/Pillow.

        Args:
            file_path: Path to image file

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        with Image.open(file_path) as img:
            # Basic image info
            metadata['width'] = img.width
            metadata['height'] = img.height
            metadata['format'] = img.format
            metadata['mode'] = img.mode

            # EXIF data
            exif_data = img._getexif()
            if exif_data:
                exif_dict = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, tag_id)
                    exif_dict[tag_name] = value

                # Extract important fields
                metadata['camera_make'] = exif_dict.get('Make', '').strip()
                metadata['camera_model'] = exif_dict.get('Model', '').strip()
                metadata['software'] = exif_dict.get('Software', '').strip()

                # Date taken
                date_taken_str = exif_dict.get('DateTimeOriginal') or exif_dict.get('DateTime')
                if date_taken_str:
                    date_taken = parse_exif_date(date_taken_str)
                    if date_taken:
                        metadata['date_taken'] = date_taken
                        metadata['date_source'] = DateSource.EXIF

                # GPS data
                if 'GPSInfo' in exif_dict:
                    metadata['has_gps'] = True
                    metadata['gps_data'] = exif_dict['GPSInfo']
                else:
                    metadata['has_gps'] = False

                # Orientation
                metadata['orientation'] = exif_dict.get('Orientation', 1)

        return metadata

    def _extract_piexif_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata using piexif (more detailed EXIF).

        Args:
            file_path: Path to image file

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        try:
            exif_dict = piexif.load(str(file_path))

            # Extract from 0th IFD (main image)
            if '0th' in exif_dict:
                ifd = exif_dict['0th']
                if piexif.ImageIFD.Make in ifd:
                    metadata['camera_make'] = ifd[piexif.ImageIFD.Make].decode('utf-8', errors='ignore').strip()
                if piexif.ImageIFD.Model in ifd:
                    metadata['camera_model'] = ifd[piexif.ImageIFD.Model].decode('utf-8', errors='ignore').strip()
                if piexif.ImageIFD.Software in ifd:
                    metadata['software'] = ifd[piexif.ImageIFD.Software].decode('utf-8', errors='ignore').strip()

            # Extract from Exif IFD
            if 'Exif' in exif_dict:
                ifd = exif_dict['Exif']
                if piexif.ExifIFD.DateTimeOriginal in ifd:
                    date_str = ifd[piexif.ExifIFD.DateTimeOriginal].decode('utf-8', errors='ignore')
                    date_taken = parse_exif_date(date_str)
                    if date_taken:
                        metadata['date_taken'] = date_taken
                        metadata['date_source'] = DateSource.EXIF

                # ISO speed
                if piexif.ExifIFD.ISOSpeedRatings in ifd:
                    metadata['iso'] = ifd[piexif.ExifIFD.ISOSpeedRatings]

                # Focal length
                if piexif.ExifIFD.FocalLength in ifd:
                    focal = ifd[piexif.ExifIFD.FocalLength]
                    if isinstance(focal, tuple) and len(focal) == 2:
                        metadata['focal_length'] = focal[0] / focal[1]

            # GPS data
            if 'GPS' in exif_dict and exif_dict['GPS']:
                metadata['has_gps'] = True

        except Exception:
            pass  # Not fatal

        return metadata

    def _extract_raw_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from RAW image file.

        Args:
            file_path: Path to RAW file

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        with rawpy.imread(str(file_path)) as raw:
            # Basic dimensions
            metadata['width'] = raw.sizes.width
            metadata['height'] = raw.sizes.height

            # RAW-specific info
            metadata['raw_pattern'] = raw.raw_pattern.tolist() if hasattr(raw, 'raw_pattern') else None
            metadata['color_desc'] = raw.color_desc.decode('utf-8') if hasattr(raw, 'color_desc') else None

        return metadata

    def get_camera_info(self, metadata: Dict[str, Any]) -> tuple[str, str]:
        """
        Get camera make and model from metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Tuple of (make, model)
        """
        make = metadata.get('camera_make', '').strip()
        model = metadata.get('camera_model', '').strip()

        # Clean up model (sometimes includes make)
        if make and model and model.startswith(make):
            model = model[len(make):].strip()

        return make, model

    def get_date_taken(self, metadata: Dict[str, Any]) -> Optional[datetime]:
        """
        Get date taken from metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            datetime object or None
        """
        return metadata.get('date_taken')

    def has_exif_date(self, metadata: Dict[str, Any]) -> bool:
        """
        Check if metadata has EXIF date.

        Args:
            metadata: Metadata dictionary

        Returns:
            True if EXIF date present, False otherwise
        """
        return (
            'date_taken' in metadata and
            metadata.get('date_source') == DateSource.EXIF
        )

    def is_edited(self, metadata: Dict[str, Any], patterns: list[str]) -> bool:
        """
        Check if image was edited based on software field.

        Args:
            metadata: Metadata dictionary
            patterns: List of software patterns indicating editing

        Returns:
            True if edited, False otherwise
        """
        software = metadata.get('software', '').lower()
        if not software:
            return False

        for pattern in patterns:
            if pattern.lower() in software:
                return True

        return False

    def get_dimensions(self, metadata: Dict[str, Any]) -> tuple[int, int]:
        """
        Get image dimensions from metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Tuple of (width, height)
        """
        width = metadata.get('width', 0)
        height = metadata.get('height', 0)
        return width, height

    def has_gps_data(self, metadata: Dict[str, Any]) -> bool:
        """
        Check if image has GPS data.

        Args:
            metadata: Metadata dictionary

        Returns:
            True if GPS data present, False otherwise
        """
        return metadata.get('has_gps', False)
