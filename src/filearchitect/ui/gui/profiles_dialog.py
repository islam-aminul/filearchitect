"""
Settings profiles management dialog for FileArchitect GUI.

This module provides a dialog for managing configuration profiles.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QMessageBox,
    QInputDialog, QTextEdit, QGroupBox
)
from PyQt6.QtCore import Qt

from ...config.profiles import ProfileManager
from ...config.models import Config

logger = logging.getLogger(__name__)


class ProfilesDialog(QDialog):
    """
    Profiles management dialog.

    Features:
    - List all profiles
    - Create new profile from current settings
    - Load profile
    - Delete profile
    - View profile details
    """

    def __init__(self, current_config: Config, parent=None):
        """
        Initialize profiles dialog.

        Args:
            current_config: Current configuration
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_config = current_config
        self.profile_manager = ProfileManager()
        self.selected_profile: Optional[str] = None
        self.loaded_config: Optional[Config] = None

        # Window properties
        self.setWindowTitle("Manage Settings Profiles")
        self.setMinimumSize(700, 500)

        # Initialize UI
        self._init_ui()

        # Load profiles list
        self._refresh_profiles()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title
        title_label = QLabel("Configuration Profiles")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # Info text
        info_label = QLabel(
            "Save and load different configurations for various organization scenarios."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Main content area
        content_layout = QHBoxLayout()

        # Left side - Profiles list
        left_group = QGroupBox("Available Profiles")
        left_layout = QVBoxLayout(left_group)

        self.profiles_list = QListWidget()
        self.profiles_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.profiles_list.itemDoubleClicked.connect(self._on_load_profile)
        left_layout.addWidget(self.profiles_list)

        # List buttons
        list_buttons = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_profiles)
        list_buttons.addWidget(self.refresh_btn)

        list_buttons.addStretch()

        left_layout.addLayout(list_buttons)

        content_layout.addWidget(left_group, 2)

        # Right side - Profile details and actions
        right_layout = QVBoxLayout()

        # Profile details
        details_group = QGroupBox("Profile Details")
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)

        right_layout.addWidget(details_group)

        # Action buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        # Save current settings
        self.save_btn = QPushButton("Save Current as New Profile")
        self.save_btn.setToolTip("Save current settings as a new profile")
        self.save_btn.clicked.connect(self._on_save_profile)
        actions_layout.addWidget(self.save_btn)

        # Load profile
        self.load_btn = QPushButton("Load Selected Profile")
        self.load_btn.setToolTip("Load the selected profile")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._on_load_profile)
        actions_layout.addWidget(self.load_btn)

        # Update profile
        self.update_btn = QPushButton("Update Selected Profile")
        self.update_btn.setToolTip("Update selected profile with current settings")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._on_update_profile)
        actions_layout.addWidget(self.update_btn)

        # Delete profile
        self.delete_btn = QPushButton("Delete Selected Profile")
        self.delete_btn.setToolTip("Delete the selected profile")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_profile)
        actions_layout.addWidget(self.delete_btn)

        right_layout.addWidget(actions_group)

        right_layout.addStretch()

        content_layout.addLayout(right_layout, 1)

        layout.addLayout(content_layout)

        # Bottom buttons
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _refresh_profiles(self):
        """Refresh profiles list."""
        self.profiles_list.clear()

        profiles = self.profile_manager.list_profiles()

        for profile_name in profiles:
            item = QListWidgetItem(profile_name)
            self.profiles_list.addItem(item)

        if not profiles:
            self.details_text.setPlainText("No profiles found.\n\nClick 'Save Current as New Profile' to create one.")

    def _on_selection_changed(self):
        """Handle profile selection change."""
        items = self.profiles_list.selectedItems()

        if items:
            profile_name = items[0].text()
            self.selected_profile = profile_name

            # Enable action buttons
            self.load_btn.setEnabled(True)
            self.update_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

            # Show profile details
            self._show_profile_details(profile_name)
        else:
            self.selected_profile = None
            self.load_btn.setEnabled(False)
            self.update_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.details_text.clear()

    def _show_profile_details(self, profile_name: str):
        """
        Show profile details.

        Args:
            profile_name: Name of profile to show
        """
        info = self.profile_manager.get_profile_info(profile_name)

        if info:
            details = f"**{info['name']}**\n\n"

            if info.get('description'):
                details += f"{info['description']}\n\n"

            details += f"Created: {info.get('created_at', 'Unknown')[:10]}\n"
            details += f"Updated: {info.get('updated_at', 'Unknown')[:10]}"

            self.details_text.setPlainText(details)
        else:
            self.details_text.setPlainText("Error loading profile details.")

    def _on_save_profile(self):
        """Save current settings as new profile."""
        # Ask for profile name
        name, ok = QInputDialog.getText(
            self,
            "Save Profile",
            "Enter profile name:",
            text="My Profile"
        )

        if not ok or not name:
            return

        # Check if profile already exists
        if self.profile_manager.profile_exists(name):
            reply = QMessageBox.question(
                self,
                "Profile Exists",
                f"Profile '{name}' already exists.\n\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        # Ask for description
        description, ok = QInputDialog.getText(
            self,
            "Profile Description",
            "Enter description (optional):",
        )

        if not ok:
            description = ""

        # Save profile
        if self.profile_manager.save_profile(name, self.current_config, description):
            QMessageBox.information(
                self,
                "Success",
                f"Profile '{name}' saved successfully."
            )
            self._refresh_profiles()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save profile '{name}'."
            )

    def _on_load_profile(self):
        """Load selected profile."""
        if not self.selected_profile:
            return

        # Confirm load
        reply = QMessageBox.question(
            self,
            "Load Profile",
            f"Load profile '{self.selected_profile}'?\n\nThis will replace current settings.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Load profile
        config = self.profile_manager.load_profile(self.selected_profile)

        if config:
            self.loaded_config = config
            QMessageBox.information(
                self,
                "Success",
                f"Profile '{self.selected_profile}' loaded.\n\nClick Close to apply settings."
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load profile '{self.selected_profile}'."
            )

    def _on_update_profile(self):
        """Update selected profile with current settings."""
        if not self.selected_profile:
            return

        # Confirm update
        reply = QMessageBox.question(
            self,
            "Update Profile",
            f"Update profile '{self.selected_profile}' with current settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Get existing description
        info = self.profile_manager.get_profile_info(self.selected_profile)
        description = info.get('description', '') if info else ''

        # Update profile
        if self.profile_manager.save_profile(self.selected_profile, self.current_config, description):
            QMessageBox.information(
                self,
                "Success",
                f"Profile '{self.selected_profile}' updated successfully."
            )
            self._refresh_profiles()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to update profile '{self.selected_profile}'."
            )

    def _on_delete_profile(self):
        """Delete selected profile."""
        if not self.selected_profile:
            return

        # Confirm delete
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{self.selected_profile}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete profile
        if self.profile_manager.delete_profile(self.selected_profile):
            QMessageBox.information(
                self,
                "Success",
                f"Profile '{self.selected_profile}' deleted successfully."
            )
            self._refresh_profiles()
        else:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete profile '{self.selected_profile}'."
            )

    def get_loaded_config(self) -> Optional[Config]:
        """
        Get the loaded configuration if any.

        Returns:
            Loaded Config or None
        """
        return self.loaded_config
