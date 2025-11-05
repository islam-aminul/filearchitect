"""
Image export processor for FileArchitect.

Handles image conversion to JPEG format with resizing and EXIF preservation.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging

from ..core.exceptions import ProcessingError

logger = logging.getLogger(__name__)

# Try to import image libraries
try:
    from PIL import Image, ImageOps
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

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False


class ImageExporter:
    """
    Export images to JPEG format with resizing.

    Handles various input formats including RAW, HEIF, AVIF, etc.
    Preserves EXIF metadata and resizes to 4K maximum.
    """

    # Maximum dimensions for export (4K)
    MAX_WIDTH = 3840
    MAX_HEIGHT = 2160

    # JPEG quality
    JPEG_QUALITY = 90

    def __init__(self):
        """Initialize image exporter."""
        if not PIL_AVAILABLE:
            raise ImportError("PIL/Pillow is required for image export")

    def can_export(self, file_path: Path) -> bool:
        """
        Check if file can be exported.

        Args:
            file_path: Path to image file

        Returns:
            True if file can be exported
        """
        extension = file_path.suffix.lower()

        # Standard formats supported by PIL
        standard_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        if extension in standard_formats:
            return True

        # HEIF/HEIC
        if extension in {'.heic', '.heif'} and HEIF_AVAILABLE:
            return True

        # RAW formats
        raw_formats = {'.cr2', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.pef', '.srw'}
        if extension in raw_formats and RAWPY_AVAILABLE:
            return True

        return False

    def export_image(
        self,
        source_path: Path,
        dest_path: Path,
        max_size: Optional[Tuple[int, int]] = None,
        quality: int = JPEG_QUALITY,
        preserve_exif: bool = True
    ) -> Dict[str, Any]:
        """
        Export image to JPEG format.

        Args:
            source_path: Source image path
            dest_path: Destination JPEG path
            max_size: Maximum dimensions (width, height), defaults to 4K
            quality: JPEG quality (1-100)
            preserve_exif: Preserve EXIF metadata

        Returns:
            Dictionary with export info

        Raises:
            ProcessingError: If export fails
        """
        if not max_size:
            max_size = (self.MAX_WIDTH, self.MAX_HEIGHT)

        try:
            # Load image
            img, metadata = self._load_image(source_path)

            original_size = img.size
            logger.debug(f"Loaded image: {original_size}")

            # Auto-rotate based on EXIF orientation
            if preserve_exif and 'exif' in metadata:
                try:
                    img = ImageOps.exif_transpose(img)
                except Exception as e:
                    logger.warning(f"Could not auto-rotate: {e}")

            # Resize if needed
            needs_resize = (
                img.width > max_size[0] or
                img.height > max_size[1]
            )

            if needs_resize:
                img = self._resize_image(img, max_size)
                logger.debug(f"Resized to: {img.size}")

            # Convert to RGB if necessary
            if img.mode not in ('RGB', 'L'):
                if img.mode == 'RGBA':
                    # Create white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                    img = background
                else:
                    img = img.convert('RGB')

            # Prepare EXIF data
            exif_bytes = None
            if preserve_exif and PIEXIF_AVAILABLE and 'exif' in metadata:
                try:
                    exif_bytes = self._prepare_exif(metadata['exif'], img.size)
                except Exception as e:
                    logger.warning(f"Could not prepare EXIF: {e}")

            # Ensure destination directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as JPEG
            save_kwargs = {
                'format': 'JPEG',
                'quality': quality,
                'optimize': True
            }

            if exif_bytes:
                save_kwargs['exif'] = exif_bytes

            img.save(dest_path, **save_kwargs)

            # Get file sizes
            source_size = source_path.stat().st_size
            dest_size = dest_path.stat().st_size

            logger.info(f"Exported {source_path.name} -> {dest_path.name}")

            return {
                'success': True,
                'source_path': str(source_path),
                'dest_path': str(dest_path),
                'original_size': original_size,
                'exported_size': img.size,
                'resized': needs_resize,
                'source_bytes': source_size,
                'dest_bytes': dest_size,
                'compression_ratio': dest_size / source_size if source_size > 0 else 0
            }

        except Exception as e:
            logger.error(f"Failed to export {source_path}: {e}", exc_info=True)
            raise ProcessingError(f"Image export failed: {e}") from e

    def _load_image(self, file_path: Path) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Load image from file.

        Args:
            file_path: Path to image

        Returns:
            Tuple of (PIL Image, metadata dict)
        """
        extension = file_path.suffix.lower()
        metadata = {}

        # Try RAW formats first
        raw_formats = {'.cr2', '.nef', '.arw', '.dng', '.raf', '.orf', '.rw2', '.pef', '.srw'}
        if extension in raw_formats and RAWPY_AVAILABLE:
            try:
                with rawpy.imread(str(file_path)) as raw:
                    rgb = raw.postprocess()
                    img = Image.fromarray(rgb)
                    logger.debug(f"Loaded RAW image: {file_path.name}")
                    return img, metadata
            except Exception as e:
                logger.warning(f"Failed to load as RAW: {e}")
                # Fall through to try as regular image

        # Load as regular image
        img = Image.open(file_path)

        # Extract EXIF if available
        if hasattr(img, '_getexif') and img._getexif():
            metadata['exif'] = img.info.get('exif')
        elif 'exif' in img.info:
            metadata['exif'] = img.info['exif']

        return img, metadata

    def _resize_image(
        self,
        img: Image.Image,
        max_size: Tuple[int, int]
    ) -> Image.Image:
        """
        Resize image preserving aspect ratio.

        Only downscales, never upscales.

        Args:
            img: PIL Image
            max_size: Maximum dimensions (width, height)

        Returns:
            Resized PIL Image
        """
        # Don't upscale
        if img.width <= max_size[0] and img.height <= max_size[1]:
            return img

        # Calculate new size preserving aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        return img

    def _prepare_exif(self, exif_bytes: bytes, new_size: Tuple[int, int]) -> bytes:
        """
        Prepare EXIF data for exported image.

        Updates dimensions and removes thumbnail.

        Args:
            exif_bytes: Original EXIF bytes
            new_size: New image dimensions (width, height)

        Returns:
            Updated EXIF bytes
        """
        if not PIEXIF_AVAILABLE:
            return exif_bytes

        try:
            exif_dict = piexif.load(exif_bytes)

            # Update image dimensions
            if '0th' in exif_dict:
                exif_dict['0th'][piexif.ImageIFD.ImageWidth] = new_size[0]
                exif_dict['0th'][piexif.ImageIFD.ImageLength] = new_size[1]

            # Remove thumbnail (can be large)
            if '1st' in exif_dict:
                exif_dict['1st'] = {}
            if 'thumbnail' in exif_dict:
                exif_dict['thumbnail'] = None

            # Re-encode
            return piexif.dump(exif_dict)

        except Exception as e:
            logger.warning(f"Could not update EXIF: {e}")
            return exif_bytes

    def batch_export(
        self,
        files: list,
        output_dir: Path,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Export multiple images.

        Args:
            files: List of source file paths
            output_dir: Output directory
            **kwargs: Arguments passed to export_image()

        Returns:
            Dictionary with batch results
        """
        results = {
            'total': len(files),
            'succeeded': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        for file_path in files:
            try:
                # Check if can export
                if not self.can_export(file_path):
                    results['skipped'] += 1
                    continue

                # Generate output filename
                dest_path = output_dir / f"{file_path.stem}.jpg"

                # Export
                self.export_image(file_path, dest_path, **kwargs)
                results['succeeded'] += 1

            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'file': str(file_path),
                    'error': str(e)
                })
                logger.error(f"Failed to export {file_path}: {e}")

        return results
