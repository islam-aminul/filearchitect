"""
Configuration management for FileArchitect.

This module handles loading, validation, and saving of application
configuration using Pydantic for validation.
"""

from filearchitect.config.models import (
    Config,
    ExportSettings,
    DetectionPatterns,
    SkipPatterns,
    AudioServices,
    ProcessingOptions
)
from filearchitect.config.manager import (
    get_config_directory,
    load_config_from_file,
    save_config_to_file,
    load_config_from_destination,
    save_config_to_destination,
    merge_configs,
    validate_config,
    load_recent_paths,
    save_recent_paths,
    add_recent_path,
    get_default_config
)

__all__ = [
    "Config",
    "ExportSettings",
    "DetectionPatterns",
    "SkipPatterns",
    "AudioServices",
    "ProcessingOptions",
    "get_config_directory",
    "load_config_from_file",
    "save_config_to_file",
    "load_config_from_destination",
    "save_config_to_destination",
    "merge_configs",
    "validate_config",
    "load_recent_paths",
    "save_recent_paths",
    "add_recent_path",
    "get_default_config",
]
