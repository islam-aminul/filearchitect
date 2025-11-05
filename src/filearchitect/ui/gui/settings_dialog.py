"""
Settings dialog for FileArchitect GUI.

Provides a tabbed interface for editing all configuration options.
"""

from typing import Optional
import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QWidget, QLabel, QSpinBox, QCheckBox,
    QComboBox, QGroupBox, QGridLayout, QListWidget,
    QLineEdit, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt

from ...config.models import Config
from ...config.manager import save_config_to_destination

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Settings dialog with tabbed interface.

    Allows editing of all configuration options:
    - Processing options
    - Export settings
    - Skip patterns
    - Audio services
    """

    def __init__(self, config: Config, destination_path: Optional[str] = None, parent=None):
        """
        Initialize settings dialog.

        Args:
            config: Current configuration
            destination_path: Destination path for saving config
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config
        self.destination_path = destination_path
        self.modified = False

        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 500)

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Add tabs
        self.tabs.addTab(self._create_processing_tab(), "Processing")
        self.tabs.addTab(self._create_export_tab(), "Export")
        self.tabs.addTab(self._create_skip_patterns_tab(), "Skip Patterns")
        self.tabs.addTab(self._create_audio_services_tab(), "Audio Services")
        self.tabs.addTab(self._create_advanced_tab(), "Advanced")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.restore_btn = QPushButton("Restore Defaults")
        self.restore_btn.clicked.connect(self._restore_defaults)
        button_layout.addWidget(self.restore_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_settings)
        self.save_btn.setDefault(True)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _create_processing_tab(self) -> QWidget:
        """Create processing options tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Performance group
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout()

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 16)
        self.threads_spin.setValue(getattr(self.config.processing, 'thread_count', 4))
        self.threads_spin.setSuffix(" threads")
        perf_layout.addRow("Worker Threads:", self.threads_spin)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        self.verify_checksums_check = QCheckBox("Verify file checksums (slower but safer)")
        self.verify_checksums_check.setChecked(
            getattr(self.config.processing, 'verify_checksums', False)
        )
        options_layout.addWidget(self.verify_checksums_check)

        self.enable_preview_check = QCheckBox("Enable preview/dry-run mode")
        self.enable_preview_check.setChecked(
            getattr(self.config.processing, 'enable_preview', True)
        )
        options_layout.addWidget(self.enable_preview_check)

        self.enable_undo_check = QCheckBox("Enable undo/rollback functionality")
        self.enable_undo_check.setChecked(
            getattr(self.config.processing, 'enable_undo', True)
        )
        options_layout.addWidget(self.enable_undo_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Handling group
        handling_group = QGroupBox("File Handling")
        handling_layout = QFormLayout()

        self.duplicates_combo = QComboBox()
        self.duplicates_combo.addItems(["skip", "keep_newest", "keep_oldest", "keep_all"])
        current_dup = getattr(self.config.processing, 'handle_duplicates', 'skip')
        self.duplicates_combo.setCurrentText(current_dup)
        handling_layout.addRow("Duplicate Files:", self.duplicates_combo)

        self.errors_combo = QComboBox()
        self.errors_combo.addItems(["skip_and_log", "stop", "interactive"])
        current_err = getattr(self.config.processing, 'handle_errors', 'skip_and_log')
        self.errors_combo.setCurrentText(current_err)
        handling_layout.addRow("Errors:", self.errors_combo)

        handling_group.setLayout(handling_layout)
        layout.addWidget(handling_group)

        layout.addStretch()
        return widget

    def _create_export_tab(self) -> QWidget:
        """Create image export settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        export_group = QGroupBox("JPEG Export Settings")
        export_layout = QFormLayout()

        # Quality
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(self.config.export.jpeg_quality)
        self.quality_spin.setSuffix(" %")
        export_layout.addRow("JPEG Quality:", self.quality_spin)

        # Max width
        self.max_width_spin = QSpinBox()
        self.max_width_spin.setRange(800, 7680)
        self.max_width_spin.setSingleStep(100)
        self.max_width_spin.setValue(self.config.export.max_width)
        self.max_width_spin.setSuffix(" px")
        export_layout.addRow("Max Width:", self.max_width_spin)

        # Max height
        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(600, 4320)
        self.max_height_spin.setSingleStep(100)
        self.max_height_spin.setValue(self.config.export.max_height)
        self.max_height_spin.setSuffix(" px")
        export_layout.addRow("Max Height:", self.max_height_spin)

        # Downscale only
        self.downscale_check = QCheckBox("Downscale only (never upscale)")
        self.downscale_check.setChecked(self.config.export.downscale_only)
        export_layout.addRow("", self.downscale_check)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # Info label
        info_label = QLabel(
            "<i>Images will be converted to JPEG with these settings.<br>"
            "EXIF metadata is preserved when possible.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def _create_skip_patterns_tab(self) -> QWidget:
        """Create skip patterns tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Folders to skip
        folders_group = QGroupBox("Folders to Skip")
        folders_layout = QVBoxLayout()

        self.skip_folders_list = QListWidget()
        self.skip_folders_list.addItems(self.config.skip_patterns.folders)
        folders_layout.addWidget(self.skip_folders_list)

        folders_btn_layout = QHBoxLayout()
        add_folder_btn = QPushButton("Add")
        add_folder_btn.clicked.connect(lambda: self._add_skip_pattern('folder'))
        folders_btn_layout.addWidget(add_folder_btn)

        remove_folder_btn = QPushButton("Remove")
        remove_folder_btn.clicked.connect(lambda: self._remove_skip_pattern('folder'))
        folders_btn_layout.addWidget(remove_folder_btn)
        folders_btn_layout.addStretch()

        folders_layout.addLayout(folders_btn_layout)
        folders_group.setLayout(folders_layout)
        layout.addWidget(folders_group)

        # Files to skip
        files_group = QGroupBox("File Patterns to Skip")
        files_layout = QVBoxLayout()

        self.skip_files_list = QListWidget()
        self.skip_files_list.addItems(self.config.skip_patterns.files)
        files_layout.addWidget(self.skip_files_list)

        files_btn_layout = QHBoxLayout()
        add_file_btn = QPushButton("Add")
        add_file_btn.clicked.connect(lambda: self._add_skip_pattern('file'))
        files_btn_layout.addWidget(add_file_btn)

        remove_file_btn = QPushButton("Remove")
        remove_file_btn.clicked.connect(lambda: self._remove_skip_pattern('file'))
        files_btn_layout.addWidget(remove_file_btn)
        files_btn_layout.addStretch()

        files_layout.addLayout(files_btn_layout)
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)

        return widget

    def _create_audio_services_tab(self) -> QWidget:
        """Create audio services configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # MusicBrainz
        mb_group = QGroupBox("MusicBrainz")
        mb_layout = QVBoxLayout()

        self.mb_enabled_check = QCheckBox("Enable MusicBrainz metadata lookup")
        self.mb_enabled_check.setChecked(self.config.audio_services.musicbrainz_enabled)
        mb_layout.addWidget(self.mb_enabled_check)

        mb_form = QFormLayout()
        self.mb_url_edit = QLineEdit(self.config.audio_services.musicbrainz_api_url)
        mb_form.addRow("API URL:", self.mb_url_edit)

        self.mb_user_agent_edit = QLineEdit(self.config.audio_services.musicbrainz_user_agent)
        mb_form.addRow("User Agent:", self.mb_user_agent_edit)

        mb_layout.addLayout(mb_form)
        mb_group.setLayout(mb_layout)
        layout.addWidget(mb_group)

        # AcoustID
        acoustid_group = QGroupBox("AcoustID")
        acoustid_layout = QVBoxLayout()

        self.acoustid_enabled_check = QCheckBox("Enable AcoustID fingerprinting")
        self.acoustid_enabled_check.setChecked(self.config.audio_services.acoustid_enabled)
        acoustid_layout.addWidget(self.acoustid_enabled_check)

        acoustid_form = QFormLayout()
        self.acoustid_key_edit = QLineEdit(
            self.config.audio_services.acoustid_api_key or ""
        )
        self.acoustid_key_edit.setPlaceholderText("Enter API key (optional)")
        acoustid_form.addRow("API Key:", self.acoustid_key_edit)

        acoustid_layout.addLayout(acoustid_form)
        acoustid_group.setLayout(acoustid_layout)
        layout.addWidget(acoustid_group)

        # Info
        info_label = QLabel(
            "<i>These services enhance audio file metadata.<br>"
            "Requires internet connection.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout()

        # Movie duration threshold
        self.movie_threshold_spin = QSpinBox()
        self.movie_threshold_spin.setRange(5, 120)
        self.movie_threshold_spin.setValue(self.config.movie_duration_threshold_minutes)
        self.movie_threshold_spin.setSuffix(" minutes")
        advanced_layout.addRow("Movie Duration Threshold:", self.movie_threshold_spin)

        # Min file size
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(0, 1024 * 1024)
        self.min_size_spin.setValue(self.config.min_file_size_bytes)
        self.min_size_spin.setSuffix(" bytes")
        advanced_layout.addRow("Minimum File Size:", self.min_size_spin)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Info
        info_label = QLabel(
            "<i>These settings affect file classification and processing.<br>"
            "Only modify if you understand the implications.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def _add_skip_pattern(self, pattern_type: str):
        """Add a skip pattern."""
        from PyQt6.QtWidgets import QInputDialog

        pattern, ok = QInputDialog.getText(
            self,
            "Add Pattern",
            f"Enter {pattern_type} pattern to skip:"
        )

        if ok and pattern:
            if pattern_type == 'folder':
                self.skip_folders_list.addItem(pattern)
            else:
                self.skip_files_list.addItem(pattern)
            self.modified = True

    def _remove_skip_pattern(self, pattern_type: str):
        """Remove selected skip pattern."""
        if pattern_type == 'folder':
            list_widget = self.skip_folders_list
        else:
            list_widget = self.skip_files_list

        current_item = list_widget.currentItem()
        if current_item:
            list_widget.takeItem(list_widget.row(current_item))
            self.modified = True

    def _restore_defaults(self):
        """Restore default settings."""
        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "Are you sure you want to restore default settings?\n"
            "All current settings will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            from ...config.manager import get_default_config
            self.config = get_default_config()
            self._load_config_to_ui()
            self.modified = True

    def _load_config_to_ui(self):
        """Reload config values to UI."""
        # Processing
        self.threads_spin.setValue(getattr(self.config.processing, 'thread_count', 4))
        self.verify_checksums_check.setChecked(
            getattr(self.config.processing, 'verify_checksums', False)
        )
        self.enable_preview_check.setChecked(
            getattr(self.config.processing, 'enable_preview', True)
        )
        self.enable_undo_check.setChecked(
            getattr(self.config.processing, 'enable_undo', True)
        )
        self.duplicates_combo.setCurrentText(
            getattr(self.config.processing, 'handle_duplicates', 'skip')
        )
        self.errors_combo.setCurrentText(
            getattr(self.config.processing, 'handle_errors', 'skip_and_log')
        )

        # Export
        self.quality_spin.setValue(self.config.export.jpeg_quality)
        self.max_width_spin.setValue(self.config.export.max_width)
        self.max_height_spin.setValue(self.config.export.max_height)
        self.downscale_check.setChecked(self.config.export.downscale_only)

        # Skip patterns
        self.skip_folders_list.clear()
        self.skip_folders_list.addItems(self.config.skip_patterns.folders)
        self.skip_files_list.clear()
        self.skip_files_list.addItems(self.config.skip_patterns.files)

        # Audio services
        self.mb_enabled_check.setChecked(self.config.audio_services.musicbrainz_enabled)
        self.mb_url_edit.setText(self.config.audio_services.musicbrainz_api_url)
        self.mb_user_agent_edit.setText(self.config.audio_services.musicbrainz_user_agent)
        self.acoustid_enabled_check.setChecked(self.config.audio_services.acoustid_enabled)
        self.acoustid_key_edit.setText(self.config.audio_services.acoustid_api_key or "")

        # Advanced
        self.movie_threshold_spin.setValue(self.config.movie_duration_threshold_minutes)
        self.min_size_spin.setValue(self.config.min_file_size_bytes)

    def _save_settings(self):
        """Save settings and close dialog."""
        try:
            # Update config from UI
            self.config.processing.thread_count = self.threads_spin.value()
            self.config.processing.verify_checksums = self.verify_checksums_check.isChecked()
            self.config.processing.enable_preview = self.enable_preview_check.isChecked()
            self.config.processing.enable_undo = self.enable_undo_check.isChecked()
            self.config.processing.handle_duplicates = self.duplicates_combo.currentText()
            self.config.processing.handle_errors = self.errors_combo.currentText()

            # Export settings
            self.config.export.jpeg_quality = self.quality_spin.value()
            self.config.export.max_width = self.max_width_spin.value()
            self.config.export.max_height = self.max_height_spin.value()
            self.config.export.downscale_only = self.downscale_check.isChecked()

            # Skip patterns
            folders = [
                self.skip_folders_list.item(i).text()
                for i in range(self.skip_folders_list.count())
            ]
            files = [
                self.skip_files_list.item(i).text()
                for i in range(self.skip_files_list.count())
            ]
            self.config.skip_patterns.folders = folders
            self.config.skip_patterns.files = files

            # Audio services
            self.config.audio_services.musicbrainz_enabled = self.mb_enabled_check.isChecked()
            self.config.audio_services.musicbrainz_api_url = self.mb_url_edit.text()
            self.config.audio_services.musicbrainz_user_agent = self.mb_user_agent_edit.text()
            self.config.audio_services.acoustid_enabled = self.acoustid_enabled_check.isChecked()
            acoustid_key = self.acoustid_key_edit.text()
            self.config.audio_services.acoustid_api_key = acoustid_key if acoustid_key else None

            # Advanced
            self.config.movie_duration_threshold_minutes = self.movie_threshold_spin.value()
            self.config.min_file_size_bytes = self.min_size_spin.value()

            # Save to destination if available
            if self.destination_path:
                from pathlib import Path
                save_config_to_destination(Path(self.destination_path), self.config)
                logger.info(f"Configuration saved to {self.destination_path}")

            self.modified = True
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save settings: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save settings:\n{str(e)}"
            )

    def get_config(self) -> Config:
        """
        Get the updated configuration.

        Returns:
            Updated Config object
        """
        return self.config

    def was_modified(self) -> bool:
        """
        Check if settings were modified.

        Returns:
            True if settings were modified
        """
        return self.modified
