"""
Configuration data models for FileArchitect.

This module defines Pydantic models for configuration validation.
"""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ExportSettings(BaseModel):
    """Image export configuration."""

    jpeg_quality: int = Field(default=85, ge=1, le=100)
    max_width: int = Field(default=3840, gt=0)
    max_height: int = Field(default=2160, gt=0)
    downscale_only: bool = Field(default=True)


class DetectionPatterns(BaseModel):
    """File detection pattern configuration."""

    screenshots: List[str] = Field(
        default=["Screenshot_*", "SCR_*", "screenshot*"]
    )
    social_media_images: List[str] = Field(
        default=["IMG-*-WA*", "FB_IMG_*", "received_*"]
    )
    social_media_videos: List[str] = Field(
        default=["VID-*-WA*", "FB_VID_*"]
    )
    edited_software: List[str] = Field(
        default=[
            "Adobe Photoshop",
            "Lightroom",
            "GIMP",
            "Snapseed",
            "Picasa",
            "Instagram",
        ]
    )
    motion_photos: dict = Field(
        default={
            "max_duration_seconds": 10,
            "filename_patterns": ["*_MVIMG_*", "MOTION_*"],
            "extensions": [".mp4", ".mov"],
        }
    )
    voice_notes: dict = Field(
        default={
            "filename_patterns": ["Recording_*", "Voice_*", "Audio_*"],
            "extensions": [".m4a", ".aac", ".amr"],
        }
    )
    whatsapp_audio: dict = Field(
        default={
            "filename_patterns": ["PTT-*-WA*"],
            "extensions": [".opus", ".ogg"],
        }
    )


class SkipPatterns(BaseModel):
    """Patterns for files and folders to skip."""

    folders: List[str] = Field(
        default=[".git", "node_modules", "__pycache__", ".DS_Store"]
    )
    files: List[str] = Field(
        default=[".DS_Store", "Thumbs.db", "desktop.ini", "*.tmp", "*.temp"]
    )


class AudioServices(BaseModel):
    """Audio metadata enhancement service configuration."""

    musicbrainz_enabled: bool = Field(default=True)
    musicbrainz_api_url: str = Field(default="https://musicbrainz.org/ws/2/")
    musicbrainz_user_agent: str = Field(default="FileArchitect/1.0")
    acoustid_enabled: bool = Field(default=True)
    acoustid_api_key: Optional[str] = Field(default=None)


class ProcessingOptions(BaseModel):
    """General processing options."""

    thread_count: int = Field(default=4, ge=1, le=16)
    verify_checksums: bool = Field(default=False)
    handle_duplicates: str = Field(default="skip")
    handle_errors: str = Field(default="skip_and_log")
    enable_preview: bool = Field(default=True)
    enable_undo: bool = Field(default=True)


class Config(BaseModel):
    """Main configuration model for FileArchitect."""

    version: str = Field(default="1.0")
    source_path: Optional[Path] = Field(default=None)
    destination_path: Optional[Path] = Field(default=None)

    export: ExportSettings = Field(default_factory=ExportSettings)
    detection: DetectionPatterns = Field(default_factory=DetectionPatterns)
    skip_patterns: SkipPatterns = Field(default_factory=SkipPatterns)
    audio_services: AudioServices = Field(default_factory=AudioServices)
    processing: ProcessingOptions = Field(default_factory=ProcessingOptions)

    datetime_fallback_patterns: List[str] = Field(
        default=[
            "YYYY-MM-DD HH-MM-SS",
            "YYYYMMDD_HHMMSS",
            "IMG_YYYYMMDD_HHMMSS",
            "VID-YYYYMMDD-HHMMSS",
        ]
    )

    movie_duration_threshold_minutes: int = Field(default=15, gt=0)
    min_file_size_bytes: int = Field(default=1024, ge=0)

    @field_validator("source_path", "destination_path")
    @classmethod
    def validate_path(cls, v: Optional[Path]) -> Optional[Path]:
        """Validate path exists and is accessible."""
        if v is not None and not isinstance(v, Path):
            return Path(v)
        return v

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
