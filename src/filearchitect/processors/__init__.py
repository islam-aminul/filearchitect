"""
File processors for different file types.

This module contains specialized processors for images, videos,
audio files, and documents.
"""

from filearchitect.processors.base import BaseProcessor, ProcessingResult
from filearchitect.processors.metadata import ImageMetadataExtractor
from filearchitect.processors.image import ImageProcessor
from filearchitect.processors.video import VideoProcessor
from filearchitect.processors.audio import AudioProcessor
from filearchitect.processors.document import DocumentProcessor

__all__ = [
    "BaseProcessor",
    "ProcessingResult",
    "ImageMetadataExtractor",
    "ImageProcessor",
    "VideoProcessor",
    "AudioProcessor",
    "DocumentProcessor",
]
