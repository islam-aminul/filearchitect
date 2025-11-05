"""
Video processor for FileArchitect.

This module handles video file processing including metadata extraction,
categorization, and organization.
"""

import fnmatch
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.constants import FileType, ProcessingStatus
from ..core.exceptions import ProcessingError, MetadataError
from ..utils.datetime import parse_date_with_fallback, get_year_from_date
from ..utils.filesystem import copy_file_streaming
from ..core.sidecar import copy_sidecar_files
from .base import BaseProcessor, ProcessingResult

# Try to import video libraries
try:
    from pymediainfo import MediaInfo
    MEDIAINFO_AVAILABLE = True
except ImportError:
    MEDIAINFO_AVAILABLE = False

try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False


class VideoProcessor(BaseProcessor):
    """
    Processor for video files.

    Handles metadata extraction, categorization, and organization.
    Does not re-encode videos.
    """

    def __init__(self, config: Any):
        """
        Initialize video processor.

        Args:
            config: Configuration object
        """
        super().__init__(config)

    def get_file_type(self) -> FileType:
        """Get the file type this processor handles."""
        return FileType.VIDEO

    def can_process(self, file_path: Path) -> bool:
        """
        Check if this processor can handle the given file.

        Args:
            file_path: Path to file

        Returns:
            True if processor can handle this file
        """
        from ..core.detector import detect_file_type
        return detect_file_type(file_path) == FileType.VIDEO

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from video file.

        Args:
            file_path: Path to video file

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

        # Try MediaInfo first (more comprehensive)
        if MEDIAINFO_AVAILABLE:
            try:
                mediainfo_data = self._extract_mediainfo(file_path)
                metadata.update(mediainfo_data)
            except Exception as e:
                metadata['extraction_error'] = str(e)

        # Try ffmpeg as fallback
        elif FFMPEG_AVAILABLE:
            try:
                ffmpeg_data = self._extract_ffmpeg(file_path)
                metadata.update(ffmpeg_data)
            except Exception as e:
                metadata['extraction_error'] = str(e)

        # Add date from fallback sources if not found
        if 'date_taken' not in metadata:
            date_taken, date_source = parse_date_with_fallback(
                filename=file_path.name,
                folder_path=str(file_path.parent)
            )
            if date_taken:
                metadata['date_taken'] = date_taken
                metadata['date_source'] = date_source

        return metadata

    def _extract_mediainfo(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata using MediaInfo.

        Args:
            file_path: Path to video file

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        media_info = MediaInfo.parse(str(file_path))

        for track in media_info.tracks:
            if track.track_type == 'General':
                # Duration
                if track.duration:
                    metadata['duration_ms'] = int(track.duration)
                    metadata['duration_seconds'] = int(track.duration) / 1000

                # File size
                if track.file_size:
                    metadata['file_size'] = int(track.file_size)

                # Creation date
                if hasattr(track, 'encoded_date') and track.encoded_date:
                    metadata['encoded_date'] = track.encoded_date

                # Camera/device info
                if hasattr(track, 'make') and track.make:
                    metadata['camera_make'] = track.make
                if hasattr(track, 'model') and track.model:
                    metadata['camera_model'] = track.model

                # Format
                if track.format:
                    metadata['container_format'] = track.format

            elif track.track_type == 'Video':
                # Resolution
                if track.width:
                    metadata['width'] = int(track.width)
                if track.height:
                    metadata['height'] = int(track.height)

                # Codec
                if track.codec:
                    metadata['video_codec'] = track.codec

                # Frame rate
                if track.frame_rate:
                    metadata['frame_rate'] = float(track.frame_rate)

            elif track.track_type == 'Audio':
                if not 'audio_codec' in metadata:  # Get first audio track
                    if track.codec:
                        metadata['audio_codec'] = track.codec

        return metadata

    def _extract_ffmpeg(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata using ffmpeg-python.

        Args:
            file_path: Path to video file

        Returns:
            Dictionary of metadata
        """
        metadata = {}

        try:
            probe = ffmpeg.probe(str(file_path))

            # General info
            if 'format' in probe:
                fmt = probe['format']
                if 'duration' in fmt:
                    duration = float(fmt['duration'])
                    metadata['duration_seconds'] = duration
                    metadata['duration_ms'] = int(duration * 1000)

                if 'size' in fmt:
                    metadata['file_size'] = int(fmt['size'])

                if 'tags' in fmt:
                    tags = fmt['tags']
                    if 'creation_time' in tags:
                        metadata['creation_time'] = tags['creation_time']
                    if 'make' in tags:
                        metadata['camera_make'] = tags['make']
                    if 'model' in tags:
                        metadata['camera_model'] = tags['model']

            # Stream info
            if 'streams' in probe:
                for stream in probe['streams']:
                    if stream['codec_type'] == 'video':
                        metadata['width'] = stream.get('width')
                        metadata['height'] = stream.get('height')
                        metadata['video_codec'] = stream.get('codec_name')
                        if 'r_frame_rate' in stream:
                            # Parse frame rate like "30000/1001"
                            num, den = stream['r_frame_rate'].split('/')
                            metadata['frame_rate'] = int(num) / int(den)

                    elif stream['codec_type'] == 'audio' and 'audio_codec' not in metadata:
                        metadata['audio_codec'] = stream.get('codec_name')

        except Exception:
            pass

        return metadata

    def categorize(self, file_path: Path, metadata: Dict[str, Any]) -> str:
        """
        Categorize video file.

        Categories:
        - Camera Videos: Videos from cameras with metadata
        - Motion Photos: Short videos (< threshold) with motion photo patterns
        - Social Media: Social media filename patterns
        - Movies: Long videos or fallback

        Args:
            file_path: Path to file
            metadata: File metadata

        Returns:
            Category string
        """
        file_name = file_path.name
        duration = metadata.get('duration_seconds', 0)

        # 1. Check for motion photos
        if self._is_motion_photo(file_name, duration):
            return 'Motion Photos'

        # 2. Check for social media
        if self._is_social_media(file_name):
            return 'Social Media'

        # 3. Check for camera videos
        if self._has_camera_info(metadata):
            return 'Camera Videos'

        # 4. Movies (fallback or long videos)
        movie_threshold = self.config.movie_duration_threshold_minutes * 60
        if duration > movie_threshold:
            return 'Movies'

        # Default to Camera Videos
        return 'Camera Videos'

    def _is_motion_photo(self, file_name: str, duration: float) -> bool:
        """Check if video is a motion photo."""
        motion_config = self.config.detection.motion_photos

        # Check duration
        max_duration = motion_config.get('max_duration_seconds', 10)
        if duration > max_duration:
            return False

        # Check filename patterns
        patterns = motion_config.get('filename_patterns', [])
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True

        return False

    def _is_social_media(self, file_name: str) -> bool:
        """Check if video is from social media."""
        patterns = self.config.detection.social_media_videos
        for pattern in patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return True
        return False

    def _has_camera_info(self, metadata: Dict[str, Any]) -> bool:
        """Check if metadata has camera information."""
        return bool(metadata.get('camera_make') or metadata.get('camera_model'))

    def get_destination_path(
        self,
        file_path: Path,
        destination_root: Path,
        metadata: Dict[str, Any],
        category: str
    ) -> Path:
        """
        Generate destination path for video.

        Structure:
        - Camera Videos: Videos/Originals/[Make - Model]/[Year]/filename.ext
        - Motion Photos: Videos/Motion Photos/[Year]/filename.ext
        - Social Media: Videos/Social Media/filename.ext
        - Movies: Videos/Movies/filename.ext

        Args:
            file_path: Source file path
            destination_root: Destination root directory
            metadata: File metadata
            category: File category

        Returns:
            Destination path
        """
        parts = [destination_root, 'Videos']

        # Get date for year folder
        date_taken = metadata.get('date_taken')
        year = get_year_from_date(date_taken) if date_taken else None

        # Get camera info
        make = metadata.get('camera_make', '')
        model = metadata.get('camera_model', '')
        camera_folder = f"{make} - {model}" if make and model else (make or model or "Unknown")

        if category == 'Camera Videos':
            parts.append('Originals')
            if make or model:
                parts.append(camera_folder)
            if year:
                parts.append(year)

        elif category == 'Motion Photos':
            parts.append('Motion Photos')
            if year:
                parts.append(year)

        elif category == 'Social Media':
            parts.append('Social Media')

        elif category == 'Movies':
            parts.append('Movies')

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
        Process video file (copy without re-encoding).

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

            # Copy file (streaming for large videos)
            file_size = source_path.stat().st_size
            copy_file_streaming(
                source_path,
                destination_path,
                progress_callback=None  # TODO: Add progress callback support
            )

            # Copy sidecar files (.thm, .srt, etc.)
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
            raise ProcessingError(f"Failed to process video {source_path}: {e}") from e

    def get_video_info_string(self, metadata: Dict[str, Any]) -> str:
        """
        Get human-readable video info string.

        Args:
            metadata: Video metadata

        Returns:
            Info string like "1920x1080 30fps H.264"
        """
        parts = []

        # Resolution
        width = metadata.get('width')
        height = metadata.get('height')
        if width and height:
            parts.append(f"{width}x{height}")

        # Frame rate
        fps = metadata.get('frame_rate')
        if fps:
            parts.append(f"{fps:.0f}fps")

        # Codec
        codec = metadata.get('video_codec')
        if codec:
            parts.append(codec)

        return ' '.join(parts) if parts else 'Unknown'
