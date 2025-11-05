"""
Configuration management for FileArchitect.

This module handles loading, saving, and validating configuration files.
"""

import json
import platform
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from pydantic import ValidationError

from .models import Config
from ..core.exceptions import ConfigurationError
from ..core.constants import CONFIG_DIR, CONFIG_FILE


def get_config_directory() -> Path:
    """
    Get OS-specific configuration directory.

    Returns:
        Path to configuration directory

    Examples:
        >>> config_dir = get_config_directory()
        >>> print(config_dir)
        PosixPath('/home/user/.config/filearchitect')
    """
    system = platform.system()

    if system == "Windows":
        # Windows: %APPDATA%/FileArchitect/
        base = Path.home() / "AppData" / "Roaming"
    elif system == "Darwin":
        # macOS: ~/Library/Application Support/FileArchitect/
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux/Unix: ~/.config/filearchitect/
        base = Path.home() / ".config"

    config_dir = base / "filearchitect"
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir


def get_destination_config_path(destination: Path) -> Path:
    """
    Get configuration file path in destination directory.

    Args:
        destination: Destination directory path

    Returns:
        Path to configuration file

    Examples:
        >>> config_path = get_destination_config_path(Path("/media/photos"))
        >>> print(config_path)
        PosixPath('/media/photos/conf/config.json')
    """
    return destination / CONFIG_DIR / CONFIG_FILE


def load_config_from_file(config_path: Path) -> Config:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to configuration file

    Returns:
        Config object

    Raises:
        ConfigurationError: If file cannot be loaded or is invalid

    Examples:
        >>> config = load_config_from_file(Path("config.json"))
    """
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        # Convert path strings to Path objects if needed
        if 'source_path' in data and data['source_path']:
            data['source_path'] = Path(data['source_path'])
        if 'destination_path' in data and data['destination_path']:
            data['destination_path'] = Path(data['destination_path'])

        config = Config(**data)
        return config

    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in configuration file: {e}") from e
    except ValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}") from e


def save_config_to_file(config: Config, config_path: Path) -> None:
    """
    Save configuration to JSON file.

    Args:
        config: Config object to save
        config_path: Path to save configuration file

    Raises:
        ConfigurationError: If file cannot be saved

    Examples:
        >>> config = Config()
        >>> save_config_to_file(config, Path("config.json"))
    """
    try:
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert config to dict
        data = config.model_dump(mode='json')

        # Convert Path objects to strings
        if 'source_path' in data and data['source_path']:
            data['source_path'] = str(data['source_path'])
        if 'destination_path' in data and data['destination_path']:
            data['destination_path'] = str(data['destination_path'])

        # Write to file with pretty formatting
        with config_path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        raise ConfigurationError(f"Failed to save configuration: {e}") from e


def load_config_from_destination(destination: Path) -> Config:
    """
    Load configuration from destination directory.

    Args:
        destination: Destination directory path

    Returns:
        Config object if found, otherwise default Config

    Examples:
        >>> config = load_config_from_destination(Path("/media/photos"))
    """
    config_path = get_destination_config_path(destination)

    if config_path.exists():
        return load_config_from_file(config_path)

    # Return default config
    return Config()


def save_config_to_destination(config: Config, destination: Path) -> None:
    """
    Save configuration to destination directory.

    Args:
        config: Config object to save
        destination: Destination directory path

    Raises:
        ConfigurationError: If save fails

    Examples:
        >>> config = Config()
        >>> save_config_to_destination(config, Path("/media/photos"))
    """
    config_path = get_destination_config_path(destination)
    save_config_to_file(config, config_path)


def merge_configs(base: Config, override: Config) -> Config:
    """
    Merge two configurations, with override taking precedence.

    Args:
        base: Base configuration
        override: Override configuration

    Returns:
        Merged configuration

    Examples:
        >>> default = Config()
        >>> user = Config(export=ExportSettings(jpeg_quality=90))
        >>> merged = merge_configs(default, user)
    """
    # Convert both to dicts
    base_dict = base.model_dump()
    override_dict = override.model_dump()

    # Merge dictionaries (override takes precedence)
    merged_dict = {**base_dict, **override_dict}

    # Create new Config from merged dict
    return Config(**merged_dict)


def validate_config(config: Config) -> List[str]:
    """
    Validate configuration and return list of issues.

    Args:
        config: Config object to validate

    Returns:
        List of validation error messages (empty if valid)

    Examples:
        >>> config = Config()
        >>> errors = validate_config(config)
        >>> if errors:
        ...     print("Validation errors:", errors)
    """
    errors = []

    # Check paths
    if config.source_path and not config.source_path.exists():
        errors.append(f"Source path does not exist: {config.source_path}")

    if config.destination_path and not config.destination_path.exists():
        errors.append(f"Destination path does not exist: {config.destination_path}")

    # Check export settings
    if config.export.jpeg_quality < 1 or config.export.jpeg_quality > 100:
        errors.append(f"JPEG quality must be 1-100, got {config.export.jpeg_quality}")

    if config.export.max_width <= 0:
        errors.append(f"Max width must be positive, got {config.export.max_width}")

    if config.export.max_height <= 0:
        errors.append(f"Max height must be positive, got {config.export.max_height}")

    # Check processing options
    if config.processing.thread_count < 1 or config.processing.thread_count > 16:
        errors.append(f"Thread count must be 1-16, got {config.processing.thread_count}")

    if config.processing.handle_duplicates not in ['skip', 'keep_all', 'ask']:
        errors.append(f"Invalid duplicate handling: {config.processing.handle_duplicates}")

    if config.processing.handle_errors not in ['skip_and_log', 'stop', 'ask']:
        errors.append(f"Invalid error handling: {config.processing.handle_errors}")

    # Check movie duration threshold
    if config.movie_duration_threshold_minutes <= 0:
        errors.append(f"Movie duration threshold must be positive, got {config.movie_duration_threshold_minutes}")

    # Check min file size
    if config.min_file_size_bytes < 0:
        errors.append(f"Min file size cannot be negative, got {config.min_file_size_bytes}")

    return errors


# Recent paths management

def get_recent_paths_file() -> Path:
    """
    Get path to recent paths storage file.

    Returns:
        Path to recent paths JSON file

    Examples:
        >>> recent_file = get_recent_paths_file()
    """
    return get_config_directory() / "recent_paths.json"


def load_recent_paths() -> dict:
    """
    Load recently used paths.

    Returns:
        Dictionary with 'sources' and 'destinations' lists

    Examples:
        >>> recent = load_recent_paths()
        >>> print("Recent sources:", recent['sources'])
    """
    recent_file = get_recent_paths_file()

    if not recent_file.exists():
        return {'sources': [], 'destinations': []}

    try:
        with recent_file.open('r', encoding='utf-8') as f:
            data = json.load(f)

        # Convert strings back to Path objects
        if 'sources' in data:
            data['sources'] = [Path(p) for p in data['sources']]
        if 'destinations' in data:
            data['destinations'] = [Path(p) for p in data['destinations']]

        return data

    except (json.JSONDecodeError, Exception):
        return {'sources': [], 'destinations': []}


def save_recent_paths(sources: List[Path], destinations: List[Path]) -> None:
    """
    Save recently used paths.

    Args:
        sources: List of recent source paths
        destinations: List of recent destination paths

    Examples:
        >>> save_recent_paths([Path("/source1")], [Path("/dest1")])
    """
    recent_file = get_recent_paths_file()

    try:
        data = {
            'sources': [str(p) for p in sources],
            'destinations': [str(p) for p in destinations],
            'updated_at': datetime.now().isoformat()
        }

        with recent_file.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    except Exception:
        # Silently fail - recent paths are not critical
        pass


def add_recent_path(path: Path, path_type: str) -> None:
    """
    Add a path to recent paths.

    Args:
        path: Path to add
        path_type: Either 'source' or 'destination'

    Examples:
        >>> add_recent_path(Path("/media/photos"), "destination")
    """
    recent = load_recent_paths()

    key = f"{path_type}s"  # 'sources' or 'destinations'

    if key not in recent:
        recent[key] = []

    # Remove path if already in list
    recent[key] = [p for p in recent[key] if p != path]

    # Add to front
    recent[key].insert(0, path)

    # Keep only last 10
    recent[key] = recent[key][:10]

    # Save
    other_key = 'destinations' if path_type == 'source' else 'sources'
    save_recent_paths(
        recent.get('sources', []),
        recent.get('destinations', [])
    )


def get_default_config() -> Config:
    """
    Get default configuration.

    Returns:
        Config object with all default values

    Examples:
        >>> config = get_default_config()
    """
    return Config()


def create_config_template(output_path: Path) -> None:
    """
    Create a configuration template file.

    Args:
        output_path: Path to save template

    Examples:
        >>> create_config_template(Path("config_template.json"))
    """
    config = get_default_config()
    save_config_to_file(config, output_path)
