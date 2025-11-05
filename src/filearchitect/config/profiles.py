"""
Configuration profiles management for FileArchitect.

This module provides functionality to save, load, and manage
configuration profiles for different organization scenarios.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from .models import Config

logger = logging.getLogger(__name__)


class ProfileManager:
    """
    Manage configuration profiles.

    Profiles are stored as JSON files in ~/.filearchitect/profiles/
    """

    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        Initialize profile manager.

        Args:
            profiles_dir: Directory for storing profiles. If None, uses default.
        """
        if profiles_dir is None:
            profiles_dir = Path.home() / '.filearchitect' / 'profiles'

        self.profiles_dir = profiles_dir
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Profile manager initialized: {self.profiles_dir}")

    def list_profiles(self) -> List[str]:
        """
        List all available profile names.

        Returns:
            List of profile names (without .json extension)
        """
        profiles = []
        for file in self.profiles_dir.glob("*.json"):
            profiles.append(file.stem)

        return sorted(profiles)

    def save_profile(self, name: str, config: Config, description: str = "") -> bool:
        """
        Save configuration as a named profile.

        Args:
            name: Profile name (without extension)
            config: Configuration to save
            description: Optional profile description

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Sanitize profile name
            safe_name = self._sanitize_name(name)
            if not safe_name:
                raise ValueError("Invalid profile name")

            profile_path = self.profiles_dir / f"{safe_name}.json"

            # Create profile data
            profile_data = {
                "name": name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "config": config.model_dump()
            }

            # Write to file
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2)

            logger.info(f"Profile saved: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save profile '{name}': {e}")
            return False

    def load_profile(self, name: str) -> Optional[Config]:
        """
        Load configuration from a named profile.

        Args:
            name: Profile name (without extension)

        Returns:
            Config object or None if profile doesn't exist
        """
        try:
            safe_name = self._sanitize_name(name)
            profile_path = self.profiles_dir / f"{safe_name}.json"

            if not profile_path.exists():
                logger.warning(f"Profile not found: {name}")
                return None

            # Read profile file
            with open(profile_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)

            # Create config from profile data
            config = Config(**profile_data['config'])

            logger.info(f"Profile loaded: {name}")
            return config

        except Exception as e:
            logger.error(f"Failed to load profile '{name}': {e}")
            return None

    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile.

        Args:
            name: Profile name (without extension)

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            safe_name = self._sanitize_name(name)
            profile_path = self.profiles_dir / f"{safe_name}.json"

            if not profile_path.exists():
                logger.warning(f"Profile not found: {name}")
                return False

            profile_path.unlink()
            logger.info(f"Profile deleted: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete profile '{name}': {e}")
            return False

    def get_profile_info(self, name: str) -> Optional[Dict]:
        """
        Get profile metadata without loading full config.

        Args:
            name: Profile name

        Returns:
            Dictionary with profile metadata or None
        """
        try:
            safe_name = self._sanitize_name(name)
            profile_path = self.profiles_dir / f"{safe_name}.json"

            if not profile_path.exists():
                return None

            with open(profile_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)

            return {
                "name": profile_data.get("name", name),
                "description": profile_data.get("description", ""),
                "created_at": profile_data.get("created_at", ""),
                "updated_at": profile_data.get("updated_at", "")
            }

        except Exception as e:
            logger.error(f"Failed to get profile info '{name}': {e}")
            return None

    def profile_exists(self, name: str) -> bool:
        """
        Check if a profile exists.

        Args:
            name: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        safe_name = self._sanitize_name(name)
        profile_path = self.profiles_dir / f"{safe_name}.json"
        return profile_path.exists()

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize profile name for use as filename.

        Args:
            name: Profile name

        Returns:
            Sanitized name safe for filenames
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        sanitized = name

        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')

        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip('. ')

        return sanitized


def get_default_profiles() -> List[Dict]:
    """
    Get list of default profiles to create on first run.

    Returns:
        List of profile definitions
    """
    return [
        {
            "name": "Default",
            "description": "Standard organization settings",
            "config": {}  # Uses default Config()
        },
        {
            "name": "Photos - By Date",
            "description": "Organize photos by year/month",
            "config": {
                "organization": {
                    "structure": "YYYY/MM",
                    "use_creation_date": True
                }
            }
        },
        {
            "name": "Photos - By Camera",
            "description": "Organize by camera model",
            "config": {
                "organization": {
                    "structure": "Camera/YYYY",
                    "group_by_camera": True
                }
            }
        },
        {
            "name": "Mixed Media",
            "description": "Organize all media types by date",
            "config": {
                "organization": {
                    "structure": "YYYY/MM",
                    "separate_types": True
                }
            }
        }
    ]


def create_default_profiles(profile_manager: ProfileManager) -> None:
    """
    Create default profiles if they don't exist.

    Args:
        profile_manager: ProfileManager instance
    """
    from .manager import get_default_config

    for profile_def in get_default_profiles():
        name = profile_def["name"]

        if not profile_manager.profile_exists(name):
            config = get_default_config()

            # Apply any custom config overrides
            if profile_def.get("config"):
                # Merge with default config
                # (simplified - would need proper deep merge in production)
                pass

            profile_manager.save_profile(
                name=name,
                config=config,
                description=profile_def["description"]
            )

            logger.info(f"Created default profile: {name}")
