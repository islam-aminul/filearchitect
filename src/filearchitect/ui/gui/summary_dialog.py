"""
Summary dialog for FileArchitect GUI.

Shows processing statistics and results after completion.
"""

from typing import Dict, Optional
from pathlib import Path
import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QGridLayout, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...core.orchestrator import ProcessingProgress
from ...core.session import SessionManager

logger = logging.getLogger(__name__)


class SummaryDialog(QDialog):
    """
    Summary dialog shown after processing completion.

    Displays:
    - Overall statistics
    - Files by category
    - Errors encountered
    - Processing time
    - Space saved from deduplication
    """

    def __init__(
        self,
        progress: ProcessingProgress,
        session_manager: Optional[SessionManager] = None,
        parent=None
    ):
        """
        Initialize summary dialog.

        Args:
            progress: Final processing progress
            session_manager: Session manager for detailed stats
            parent: Parent widget
        """
        super().__init__(parent)

        self.progress = progress
        self.session_manager = session_manager

        self.setWindowTitle("Processing Complete")
        self.setMinimumSize(600, 500)

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("✓ Processing Completed Successfully")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #4CAF50;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Overall statistics
        layout.addWidget(self._create_overall_stats_group())

        # Category breakdown
        layout.addWidget(self._create_category_group())

        # Additional info
        layout.addWidget(self._create_additional_info_group())

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _create_overall_stats_group(self) -> QGroupBox:
        """Create overall statistics group."""
        group = QGroupBox("Overall Statistics")
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        row = 0

        # Files processed
        layout.addWidget(self._create_label("Files Processed:", bold=True), row, 0)
        processed = (
            self.progress.files_processed +
            self.progress.files_skipped +
            self.progress.files_duplicates
        )
        layout.addWidget(
            self._create_value_label(f"{processed} / {self.progress.files_scanned}"),
            row, 1
        )

        # Processing time
        layout.addWidget(self._create_label("Processing Time:", bold=True), row, 2)
        time_str = self._format_seconds(self.progress.elapsed_seconds)
        layout.addWidget(self._create_value_label(time_str), row, 3)

        row += 1

        # Successfully organized
        layout.addWidget(self._create_label("Successfully Organized:", bold=True), row, 0)
        layout.addWidget(
            self._create_value_label(str(self.progress.files_processed), color="#4CAF50"),
            row, 1
        )

        # Average speed
        layout.addWidget(self._create_label("Average Speed:", bold=True), row, 2)
        speed_str = f"{self.progress.processing_speed:.1f} files/sec"
        layout.addWidget(self._create_value_label(speed_str), row, 3)

        row += 1

        # Skipped
        layout.addWidget(self._create_label("Skipped:", bold=True), row, 0)
        layout.addWidget(
            self._create_value_label(str(self.progress.files_skipped), color="#FF9800"),
            row, 1
        )

        # Data processed
        layout.addWidget(self._create_label("Data Processed:", bold=True), row, 2)
        data_gb = self.progress.bytes_processed / (1024**3)
        layout.addWidget(
            self._create_value_label(f"{data_gb:.2f} GB"),
            row, 3
        )

        row += 1

        # Duplicates
        layout.addWidget(self._create_label("Duplicates:", bold=True), row, 0)
        layout.addWidget(
            self._create_value_label(str(self.progress.files_duplicates), color="#2196F3"),
            row, 1
        )

        # Errors
        layout.addWidget(self._create_label("Errors:", bold=True), row, 2)
        error_color = "#f44336" if self.progress.files_error > 0 else "#666"
        layout.addWidget(
            self._create_value_label(str(self.progress.files_error), color=error_color),
            row, 3
        )

        group.setLayout(layout)
        return group

    def _create_category_group(self) -> QGroupBox:
        """Create category breakdown group."""
        group = QGroupBox("Files by Category")
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        categories = self.progress.category_counts
        if not categories:
            label = QLabel("No category information available")
            label.setStyleSheet("color: #666; font-style: italic;")
            layout.addWidget(label, 0, 0, 1, 4)
        else:
            # Group categories
            image_count = self._get_image_count(categories)
            video_count = self._get_video_count(categories)
            audio_count = self._get_audio_count(categories)
            doc_count = self._get_document_count(categories)

            row = 0

            # Images
            layout.addWidget(self._create_label("Images:", bold=True), row, 0)
            layout.addWidget(self._create_value_label(str(image_count)), row, 1)

            # Videos
            layout.addWidget(self._create_label("Videos:", bold=True), row, 2)
            layout.addWidget(self._create_value_label(str(video_count)), row, 3)

            row += 1

            # Audio
            layout.addWidget(self._create_label("Audio:", bold=True), row, 0)
            layout.addWidget(self._create_value_label(str(audio_count)), row, 1)

            # Documents
            layout.addWidget(self._create_label("Documents:", bold=True), row, 2)
            layout.addWidget(self._create_value_label(str(doc_count)), row, 3)

        group.setLayout(layout)
        return group

    def _create_additional_info_group(self) -> QGroupBox:
        """Create additional information group."""
        group = QGroupBox("Additional Information")
        layout = QVBoxLayout()

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(100)

        # Build info text
        info_lines = []

        if self.progress.files_error > 0:
            info_lines.append(
                f"⚠️ {self.progress.files_error} file(s) encountered errors. "
                f"Check the log file for details."
            )

        if self.progress.files_duplicates > 0:
            info_lines.append(
                f"ℹ️ {self.progress.files_duplicates} duplicate file(s) were skipped "
                f"to save space."
            )

        if self.progress.files_skipped > 0:
            info_lines.append(
                f"ℹ️ {self.progress.files_skipped} file(s) were skipped "
                f"(unknown types or excluded patterns)."
            )

        if not info_lines:
            info_lines.append("✓ All files processed successfully!")

        info_text.setPlainText("\n\n".join(info_lines))
        layout.addWidget(info_text)

        group.setLayout(layout)
        return group

    def _create_label(self, text: str, bold: bool = False) -> QLabel:
        """Create a label."""
        label = QLabel(text)
        if bold:
            label.setStyleSheet("font-weight: bold;")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _create_value_label(self, text: str, color: str = "#2196F3") -> QLabel:
        """Create a value label."""
        label = QLabel(text)
        label.setStyleSheet(f"color: {color}; font-weight: bold;")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _format_seconds(self, seconds: int) -> str:
        """Format seconds as HH:MM:SS."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _get_image_count(self, categories: Dict[str, int]) -> int:
        """Get total image count."""
        image_categories = [
            'originals', 'raw', 'edited', 'screenshots',
            'social_media', 'export', 'collection'
        ]
        return sum(categories.get(cat, 0) for cat in image_categories)

    def _get_video_count(self, categories: Dict[str, int]) -> int:
        """Get total video count."""
        video_categories = [
            'camera_videos', 'motion_photos', 'social_media_videos', 'movies'
        ]
        return sum(categories.get(cat, 0) for cat in video_categories)

    def _get_audio_count(self, categories: Dict[str, int]) -> int:
        """Get total audio count."""
        audio_categories = ['songs', 'voice_notes', 'whatsapp_audio']
        return sum(categories.get(cat, 0) for cat in audio_categories)

    def _get_document_count(self, categories: Dict[str, int]) -> int:
        """Get total document count."""
        doc_categories = [
            'pdfs', 'text', 'word', 'excel', 'powerpoint', 'code', 'other_docs'
        ]
        return sum(categories.get(cat, 0) for cat in doc_categories)
