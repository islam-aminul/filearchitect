"""
FileArchitect - Intelligent file organization and deduplication tool.

FileArchitect helps organize, deduplicate, and manage personal media files
from multiple backup sources into a well-structured destination storage.
"""

__version__ = "1.0.0"
__author__ = "FileArchitect Team"
__license__ = "MIT"

# Expose main API
from filearchitect.core.exceptions import FileArchitectError

__all__ = ["__version__", "__author__", "__license__", "FileArchitectError"]
