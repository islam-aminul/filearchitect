"""
File type detection for FileArchitect.

This module provides file type detection using both content-based (magic)
and extension-based methods with fallback logic.
"""

from pathlib import Path
from typing import Optional
import mimetypes

from ..core.constants import (
    FileType,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    AUDIO_EXTENSIONS,
    DOCUMENT_EXTENSIONS
)
from ..core.exceptions import FileAccessError

# Try to import python-magic
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


# MIME type to FileType mapping
MIME_TYPE_MAPPING = {
    # Images
    'image/jpeg': FileType.IMAGE,
    'image/png': FileType.IMAGE,
    'image/gif': FileType.IMAGE,
    'image/bmp': FileType.IMAGE,
    'image/tiff': FileType.IMAGE,
    'image/webp': FileType.IMAGE,
    'image/heic': FileType.IMAGE,
    'image/heif': FileType.IMAGE,
    'image/avif': FileType.IMAGE,
    'image/x-canon-cr2': FileType.IMAGE,
    'image/x-canon-crw': FileType.IMAGE,
    'image/x-nikon-nef': FileType.IMAGE,
    'image/x-sony-arw': FileType.IMAGE,
    'image/x-adobe-dng': FileType.IMAGE,

    # Videos
    'video/mp4': FileType.VIDEO,
    'video/quicktime': FileType.VIDEO,
    'video/x-msvideo': FileType.VIDEO,
    'video/x-matroska': FileType.VIDEO,
    'video/webm': FileType.VIDEO,
    'video/x-ms-wmv': FileType.VIDEO,
    'video/x-flv': FileType.VIDEO,
    'video/mpeg': FileType.VIDEO,
    'video/3gpp': FileType.VIDEO,

    # Audio
    'audio/mpeg': FileType.AUDIO,
    'audio/wav': FileType.AUDIO,
    'audio/x-wav': FileType.AUDIO,
    'audio/flac': FileType.AUDIO,
    'audio/x-flac': FileType.AUDIO,
    'audio/mp4': FileType.AUDIO,
    'audio/aac': FileType.AUDIO,
    'audio/ogg': FileType.AUDIO,
    'audio/opus': FileType.AUDIO,
    'audio/x-ms-wma': FileType.AUDIO,
    'audio/amr': FileType.AUDIO,
    'audio/aiff': FileType.AUDIO,

    # Documents
    'application/pdf': FileType.DOCUMENT,
    'text/plain': FileType.DOCUMENT,
    'text/rtf': FileType.DOCUMENT,
    'text/markdown': FileType.DOCUMENT,
    'application/msword': FileType.DOCUMENT,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileType.DOCUMENT,
    'application/vnd.oasis.opendocument.text': FileType.DOCUMENT,
    'application/vnd.ms-excel': FileType.DOCUMENT,
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileType.DOCUMENT,
    'application/vnd.oasis.opendocument.spreadsheet': FileType.DOCUMENT,
    'text/csv': FileType.DOCUMENT,
    'application/vnd.ms-powerpoint': FileType.DOCUMENT,
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': FileType.DOCUMENT,
    'application/vnd.oasis.opendocument.presentation': FileType.DOCUMENT,
    'text/html': FileType.DOCUMENT,
    'text/xml': FileType.DOCUMENT,
    'application/xml': FileType.DOCUMENT,
    'application/json': FileType.DOCUMENT,
    'text/x-python': FileType.DOCUMENT,
    'text/x-java': FileType.DOCUMENT,
    'text/x-c': FileType.DOCUMENT,
    'text/x-c++': FileType.DOCUMENT,
}


def detect_file_type_by_extension(file_path: Path) -> FileType:
    """
    Detect file type based on extension.

    Args:
        file_path: Path to file

    Returns:
        FileType enum value

    Examples:
        >>> detect_file_type_by_extension(Path("photo.jpg"))
        <FileType.IMAGE: 'image'>
    """
    extension = file_path.suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    elif extension in VIDEO_EXTENSIONS:
        return FileType.VIDEO
    elif extension in AUDIO_EXTENSIONS:
        return FileType.AUDIO
    elif extension in DOCUMENT_EXTENSIONS:
        return FileType.DOCUMENT
    else:
        return FileType.UNKNOWN


def detect_file_type_by_mime(mime_type: str) -> FileType:
    """
    Detect file type based on MIME type.

    Args:
        mime_type: MIME type string

    Returns:
        FileType enum value

    Examples:
        >>> detect_file_type_by_mime("image/jpeg")
        <FileType.IMAGE: 'image'>
    """
    # Direct mapping
    if mime_type in MIME_TYPE_MAPPING:
        return MIME_TYPE_MAPPING[mime_type]

    # Fallback to general category
    if mime_type.startswith('image/'):
        return FileType.IMAGE
    elif mime_type.startswith('video/'):
        return FileType.VIDEO
    elif mime_type.startswith('audio/'):
        return FileType.AUDIO
    elif mime_type.startswith('text/') or mime_type.startswith('application/'):
        return FileType.DOCUMENT
    else:
        return FileType.UNKNOWN


def detect_file_type_by_content(file_path: Path) -> Optional[FileType]:
    """
    Detect file type by reading file content (magic bytes).

    Args:
        file_path: Path to file

    Returns:
        FileType enum value, or None if detection fails

    Examples:
        >>> detect_file_type_by_content(Path("photo.jpg"))
        <FileType.IMAGE: 'image'>
    """
    if not MAGIC_AVAILABLE:
        return None

    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        # Detect MIME type using python-magic
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(str(file_path))

        if mime_type:
            return detect_file_type_by_mime(mime_type)

    except Exception:
        # If magic detection fails, return None to fall back to extension
        pass

    return None


def detect_file_type(file_path: Path, use_content: bool = True) -> FileType:
    """
    Detect file type using content-based detection with extension fallback.

    Args:
        file_path: Path to file
        use_content: Whether to use content-based detection (default: True)

    Returns:
        FileType enum value

    Examples:
        >>> detect_file_type(Path("photo.jpg"))
        <FileType.IMAGE: 'image'>
    """
    if not file_path.exists():
        raise FileAccessError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise FileAccessError(f"Path is not a file: {file_path}")

    # Try content-based detection first if available
    if use_content and MAGIC_AVAILABLE:
        content_type = detect_file_type_by_content(file_path)
        if content_type and content_type != FileType.UNKNOWN:
            return content_type

    # Fallback to extension-based detection
    return detect_file_type_by_extension(file_path)


def get_mime_type(file_path: Path) -> Optional[str]:
    """
    Get MIME type for a file.

    Args:
        file_path: Path to file

    Returns:
        MIME type string, or None if detection fails

    Examples:
        >>> get_mime_type(Path("photo.jpg"))
        'image/jpeg'
    """
    if not file_path.exists():
        return None

    # Try python-magic first
    if MAGIC_AVAILABLE:
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(str(file_path))
            if mime_type:
                return mime_type
        except Exception:
            pass

    # Fallback to mimetypes module
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type


def is_supported_file_type(file_path: Path) -> bool:
    """
    Check if file type is supported.

    Args:
        file_path: Path to file

    Returns:
        True if file type is supported, False otherwise

    Examples:
        >>> is_supported_file_type(Path("photo.jpg"))
        True
    """
    try:
        file_type = detect_file_type(file_path)
        return file_type != FileType.UNKNOWN
    except FileAccessError:
        return False


def classify_file(file_path: Path) -> tuple[FileType, str]:
    """
    Classify file and return type with extension.

    Args:
        file_path: Path to file

    Returns:
        Tuple of (FileType, extension)

    Examples:
        >>> classify_file(Path("photo.jpg"))
        (<FileType.IMAGE: 'image'>, '.jpg')
    """
    file_type = detect_file_type(file_path)
    extension = file_path.suffix.lower()

    return file_type, extension


def get_file_category(file_path: Path) -> str:
    """
    Get human-readable category for a file.

    Args:
        file_path: Path to file

    Returns:
        Category string ("Image", "Video", "Audio", "Document", "Unknown")

    Examples:
        >>> get_file_category(Path("photo.jpg"))
        'Image'
    """
    file_type = detect_file_type(file_path)

    category_map = {
        FileType.IMAGE: "Image",
        FileType.VIDEO: "Video",
        FileType.AUDIO: "Audio",
        FileType.DOCUMENT: "Document",
        FileType.UNKNOWN: "Unknown"
    }

    return category_map.get(file_type, "Unknown")


def validate_file_format(file_path: Path, expected_type: FileType) -> bool:
    """
    Validate that file matches expected type.

    Args:
        file_path: Path to file
        expected_type: Expected FileType

    Returns:
        True if file matches expected type, False otherwise

    Examples:
        >>> validate_file_format(Path("photo.jpg"), FileType.IMAGE)
        True
    """
    try:
        actual_type = detect_file_type(file_path)
        return actual_type == expected_type
    except FileAccessError:
        return False
