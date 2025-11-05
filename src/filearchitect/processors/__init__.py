"""
File processors for different file types.

This module contains specialized processors for images, videos,
audio files, and documents.
"""

from filearchitect.processors.base import BaseProcessor
from filearchitect.processors.image import ImageProcessor
from filearchitect.processors.video import VideoProcessor
from filearchitect.processors.audio import AudioProcessor
from filearchitect.processors.document import DocumentProcessor

__all__ = [
    "BaseProcessor",
    "ImageProcessor",
    "VideoProcessor",
    "AudioProcessor",
    "DocumentProcessor",
]
