"""
Audio processor for FileArchitect.

This module handles audio file processing including metadata extraction,
categorization, and organization.
"""

import fnmatch
from pathlib import Path
from typing import Optional, Dict, Any

from ..core.constants import FileType, ProcessingStatus
from ..core.exceptions import ProcessingError, MetadataError
from ..utils.datetime import parse_date_with_fallback, get_year_from_date
from ..utils.filesystem import copy_file_atomic
from .base import BaseProcessor, ProcessingResult

# Try to import audio library
try:
    from mutagen import File as MutagenFile
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class AudioProcessor(BaseProcessor):
    """
    Processor for audio files.

    Handles metadata extraction, categorization, and organization.
    """

    def __init__(self, config: Any):
        """
        Initialize audio processor.

        Args:
            config: Configuration object
        """
        super().__init__(config)

    def get_file_type(self) -> FileType:
        """Get the file type this processor handles."""
        return FileType.AUDIO

    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.

        Args:
            file_path: Path to file

        Returns:
            True if processor can handle this file
        """
        from ..core.detector import detect_file_type
        return detect_file_type(file_path) == FileType.AUDIO

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary of metadata

        Raises:
            ProcessingError: If extraction fails
        """
        if not file_path.exists():
            raise MetadataError(f"File does not exist: {file_path}")

        metadata = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix.lower(),
        }

        # Extract audio metadata using mutagen
        if MUTAGEN_AVAILABLE:
            try:
                audio = MutagenFile(str(file_path))
                if audio is not None:
                    # Duration
                    if hasattr(audio.info, 'length'):
                        metadata['duration_seconds'] = int(audio.info.length)

                    # Bitrate
                    if hasattr(audio.info, 'bitrate'):
                        metadata['bitrate'] = audio.info.bitrate

                    # Sample rate
                    if hasattr(audio.info, 'sample_rate'):
                        metadata['sample_rate'] = audio.info.sample_rate

                    # Tags
                    if audio.tags:
                        metadata['artist'] = str(audio.tags.get('artist', [''])[0]) if 'artist' in audio.tags else None
                        metadata['album'] = str(audio.tags.get('album', [''])[0]) if 'album' in audio.tags else None
                        metadata['title'] = str(audio.tags.get('title', [''])[0]) if 'title' in audio.tags else None
                        metadata['genre'] = str(audio.tags.get('genre', [''])[0]) if 'genre' in audio.tags else None
                        metadata['date'] = str(audio.tags.get('date', [''])[0]) if 'date' in audio.tags else None

                        # Has metadata
                        metadata['has_metadata'] = any([
                            metadata.get('artist'),
                            metadata.get('album'),
                            metadata.get('title')
                        ])
                    else:
                        metadata['has_metadata'] = False

            except Exception as e:
                metadata['extraction_error'] = str(e)

        # Add date from fallback sources
        if 'date_taken' not in metadata:
            date_taken, date_source = parse_date_with_fallback(
                filename=file_path.name,
                folder_path=str(file_path.parent)
            )
            if date_taken:
                metadata['date_taken'] = date_taken
                metadata['date_source'] = date_source

        return metadata

    def categorize(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        """
        Categorize audio file.

        Categories:
        - Songs: Audio files with metadata (artist, album, title)
        - Voice Notes: Voice recording patterns
        - Social Media Audio: WhatsApp audio patterns
        - Collection: Fallback

        Args:
            file_path: Path to file
            metadata: File metadata

        Returns:
            Category string
        """
        file_name = file_path.name
        extension = file_path.suffix.lower()

        # 1. Check for voice notes
        if self._is_voice_note(file_name, extension):
            return 'Voice Notes'

        # 2. Check for social media audio (WhatsApp)
        if self._is_whatsapp_audio(file_name, extension):
            return 'WhatsApp Audio'

        # 3. Check for songs (has metadata)
        if metadata.get('has_metadata', False):
            return 'Songs'

        # 4. Fallback to collection
        return 'Collection'

    def _is_voice_note(self, file_name: str, extension: str) -> bool:
        """Check if audio is a voice note."""
        voice_config = self.config.detection.voice_notes

        # Check extension
        extensions = voice_config.get('extensions', [])
        if extension not in extensions:
            return False

        # Check filename patterns
        patterns = voice_config.get('filename_patterns', [])
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        return False

    def _is_whatsapp_audio(self, file_name: str, extension: str) -> bool:
        """Check if audio is from WhatsApp."""
        whatsapp_config = self.config.detection.whatsapp_audio

        # Check extension
        extensions = whatsapp_config.get('extensions', [])
        if extension not in extensions:
            return False

        # Check filename patterns
        patterns = whatsapp_config.get('filename_patterns', [])
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        return False

    def get_destination_path(
        self,
        file_path: Path,
        destination_root: Path,
        metadata: Dict[str, Any],
        category: str
    ) -> Path:
        """
        Generate destination path for audio.

        Structure:
        - Songs: Audio/Songs/filename.ext
        - Voice Notes: Audio/Voice Notes/[Year]/filename.ext
        - WhatsApp Audio: Audio/WhatsApp/[Year]/filename.ext
        - Collection: Audio/Collection/filename.ext

        Args:
            file_path: Source file path
            destination_root: Destination root directory
            metadata: File metadata
            category: File category

        Returns:
            Destination path
        """
        parts = [destination_root, 'Audio']

        # Get date for year folder
        date_taken = metadata.get('date_taken')
        year = get_year_from_date(date_taken) if date_taken else None

        if category == 'Songs':
            parts.append('Songs')

        elif category == 'Voice Notes':
            parts.append('Voice Notes')
            if year:
                parts.append(year)

        elif category == 'WhatsApp Audio':
            parts.append('WhatsApp')
            if year:
                parts.append(year)

        elif category == 'Collection':
            parts.append('Collection')

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
        Process audio file (copy to destination).

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
            raise ProcessingError(f"Failed to process audio {source_path}: {e}") from e
