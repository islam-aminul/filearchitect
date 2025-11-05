"""
Progress display widget for FileArchitect GUI.

Shows real-time progress updates during file processing.
"""

from typing import Dict, Optional
from datetime import datetime
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

from ...core.orchestrator import ProcessingProgress, OrchestratorState

logger = logging.getLogger(__name__)


class ProgressWidget(QWidget):
    """
    Progress display widget.

    Shows:
    - Overall progress bar
    - Current file being processed
    - File counts by category
    - Processing statistics
    - ETA
    """

    def __init__(self, parent=None):
        """Initialize progress widget."""
        super().__init__(parent)

        self._init_ui()
        self._reset_display()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)

        # Overall progress group
        layout.addWidget(self._create_overall_progress_group())

        # Statistics group
        layout.addWidget(self._create_statistics_group())

        # Category counts group
        layout.addWidget(self._create_category_group())

    def _create_overall_progress_group(self) -> QGroupBox:
        """Create overall progress display group."""
        group = QGroupBox("Processing Progress")
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(30)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Current file
        current_file_layout = QVBoxLayout()
        current_file_label = QLabel("Current File:")
        current_file_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        current_file_layout.addWidget(current_file_label)

        self.current_file_label = QLabel("—")
        self.current_file_label.setWordWrap(True)
        self.current_file_label.setStyleSheet("color: #555; font-size: 11px;")
        current_file_layout.addWidget(self.current_file_label)

        layout.addLayout(current_file_layout)

        group.setLayout(layout)
        return group

    def _create_statistics_group(self) -> QGroupBox:
        """Create statistics display group."""
        group = QGroupBox("Statistics")
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        # Left column
        row = 0

        # Files processed
        layout.addWidget(self._create_stat_label("Files Processed:"), row, 0)
        self.files_processed_label = self._create_value_label("0 / 0")
        layout.addWidget(self.files_processed_label, row, 1)

        # Processing speed
        layout.addWidget(self._create_stat_label("Speed:"), row, 2)
        self.speed_label = self._create_value_label("0.0 files/s")
        layout.addWidget(self.speed_label, row, 3)

        row += 1

        # Bytes processed
        layout.addWidget(self._create_stat_label("Data Processed:"), row, 0)
        self.bytes_processed_label = self._create_value_label("0 / 0 GB")
        layout.addWidget(self.bytes_processed_label, row, 1)

        # ETA
        layout.addWidget(self._create_stat_label("Estimated Time:"), row, 2)
        self.eta_label = self._create_value_label("—")
        layout.addWidget(self.eta_label, row, 3)

        row += 1

        # Skipped
        layout.addWidget(self._create_stat_label("Skipped:"), row, 0)
        self.skipped_label = self._create_value_label("0")
        layout.addWidget(self.skipped_label, row, 1)

        # Duplicates
        layout.addWidget(self._create_stat_label("Duplicates:"), row, 2)
        self.duplicates_label = self._create_value_label("0")
        layout.addWidget(self.duplicates_label, row, 3)

        row += 1

        # Errors
        layout.addWidget(self._create_stat_label("Errors:"), row, 0)
        self.errors_label = self._create_value_label("0")
        layout.addWidget(self.errors_label, row, 1)

        # Elapsed time
        layout.addWidget(self._create_stat_label("Elapsed Time:"), row, 2)
        self.elapsed_label = self._create_value_label("00:00:00")
        layout.addWidget(self.elapsed_label, row, 3)

        group.setLayout(layout)
        return group

    def _create_category_group(self) -> QGroupBox:
        """Create category counts display group."""
        group = QGroupBox("Files by Category")
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        # Images
        layout.addWidget(self._create_stat_label("Images:"), 0, 0)
        self.images_label = self._create_value_label("0")
        layout.addWidget(self.images_label, 0, 1)

        # Videos
        layout.addWidget(self._create_stat_label("Videos:"), 0, 2)
        self.videos_label = self._create_value_label("0")
        layout.addWidget(self.videos_label, 0, 3)

        # Audio
        layout.addWidget(self._create_stat_label("Audio:"), 1, 0)
        self.audio_label = self._create_value_label("0")
        layout.addWidget(self.audio_label, 1, 1)

        # Documents
        layout.addWidget(self._create_stat_label("Documents:"), 1, 2)
        self.documents_label = self._create_value_label("0")
        layout.addWidget(self.documents_label, 1, 3)

        group.setLayout(layout)
        return group

    def _create_stat_label(self, text: str) -> QLabel:
        """Create a statistics label."""
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _create_value_label(self, text: str) -> QLabel:
        """Create a value label."""
        label = QLabel(text)
        label.setStyleSheet("color: #2196F3; font-size: 12px;")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _reset_display(self):
        """Reset all display values."""
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self.current_file_label.setText("—")
        self.files_processed_label.setText("0 / 0")
        self.bytes_processed_label.setText("0 / 0 GB")
        self.speed_label.setText("0.0 files/s")
        self.eta_label.setText("—")
        self.skipped_label.setText("0")
        self.duplicates_label.setText("0")
        self.errors_label.setText("0")
        self.elapsed_label.setText("00:00:00")
        self.images_label.setText("0")
        self.videos_label.setText("0")
        self.audio_label.setText("0")
        self.documents_label.setText("0")

    @pyqtSlot(object)
    def update_progress(self, progress: ProcessingProgress):
        """
        Update progress display.

        Args:
            progress: ProcessingProgress object
        """
        try:
            # Update progress bar
            percent = progress.progress_percent
            self.progress_bar.setValue(int(percent))
            self.progress_bar.setFormat(f"{percent:.1f}%")

            # Update current file
            if progress.current_file:
                # Truncate long paths
                path_str = str(progress.current_file)
                if len(path_str) > 80:
                    path_str = "..." + path_str[-77:]
                self.current_file_label.setText(path_str)
            else:
                self.current_file_label.setText("—")

            # Update file counts
            total_files = progress.files_scanned
            completed = (
                progress.files_processed +
                progress.files_skipped +
                progress.files_duplicates +
                progress.files_error
            )
            self.files_processed_label.setText(f"{completed} / {total_files}")

            # Update bytes
            bytes_gb = progress.bytes_processed / (1024**3)
            total_gb = progress.bytes_total / (1024**3)
            self.bytes_processed_label.setText(f"{bytes_gb:.2f} / {total_gb:.2f} GB")

            # Update speed
            if progress.processing_speed > 0:
                self.speed_label.setText(f"{progress.processing_speed:.1f} files/s")
            else:
                self.speed_label.setText("—")

            # Update ETA
            if progress.eta_seconds is not None and progress.eta_seconds > 0:
                eta_str = self._format_seconds(progress.eta_seconds)
                self.eta_label.setText(eta_str)
            else:
                self.eta_label.setText("—")

            # Update counts
            self.skipped_label.setText(str(progress.files_skipped))
            self.duplicates_label.setText(str(progress.files_duplicates))

            # Update errors with color
            errors = progress.files_error
            self.errors_label.setText(str(errors))
            if errors > 0:
                self.errors_label.setStyleSheet("color: #f44336; font-size: 12px; font-weight: bold;")
            else:
                self.errors_label.setStyleSheet("color: #2196F3; font-size: 12px;")

            # Update elapsed time
            elapsed_str = self._format_seconds(progress.elapsed_seconds)
            self.elapsed_label.setText(elapsed_str)

            # Update category counts
            categories = progress.category_counts
            self.images_label.setText(str(self._get_image_count(categories)))
            self.videos_label.setText(str(self._get_video_count(categories)))
            self.audio_label.setText(str(self._get_audio_count(categories)))
            self.documents_label.setText(str(self._get_document_count(categories)))

        except Exception as e:
            logger.error(f"Error updating progress display: {e}", exc_info=True)

    def _format_seconds(self, seconds: int) -> str:
        """
        Format seconds as HH:MM:SS.

        Args:
            seconds: Number of seconds

        Returns:
            Formatted time string
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _get_image_count(self, categories: Dict[str, int]) -> int:
        """Get total image count from categories."""
        image_categories = [
            'originals', 'raw', 'edited', 'screenshots',
            'social_media', 'export', 'collection'
        ]
        return sum(categories.get(cat, 0) for cat in image_categories)

    def _get_video_count(self, categories: Dict[str, int]) -> int:
        """Get total video count from categories."""
        video_categories = [
            'camera_videos', 'motion_photos', 'social_media_videos', 'movies'
        ]
        return sum(categories.get(cat, 0) for cat in video_categories)

    def _get_audio_count(self, categories: Dict[str, int]) -> int:
        """Get total audio count from categories."""
        audio_categories = ['songs', 'voice_notes', 'whatsapp_audio']
        return sum(categories.get(cat, 0) for cat in audio_categories)

    def _get_document_count(self, categories: Dict[str, int]) -> int:
        """Get total document count from categories."""
        doc_categories = [
            'pdfs', 'text', 'word', 'excel', 'powerpoint', 'code', 'other_docs'
        ]
        return sum(categories.get(cat, 0) for cat in doc_categories)

    def reset(self):
        """Reset the progress display."""
        self._reset_display()
