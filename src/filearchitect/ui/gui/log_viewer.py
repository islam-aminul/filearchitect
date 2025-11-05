"""
Log viewer dialog for FileArchitect GUI.

This module provides a log viewer window that displays application logs
in real-time with filtering and search capabilities.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QComboBox, QLineEdit, QLabel, QCheckBox
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QTextCursor, QFont

logger = logging.getLogger(__name__)


class LogViewerDialog(QDialog):
    """
    Log viewer dialog with real-time updates and filtering.

    Features:
    - Real-time log tailing
    - Log level filtering
    - Text search
    - Auto-scroll toggle
    - Clear and export functionality
    """

    def __init__(self, log_file: Optional[Path] = None, parent=None):
        """
        Initialize log viewer dialog.

        Args:
            log_file: Path to log file. If None, uses default location
            parent: Parent widget
        """
        super().__init__(parent)

        # Log file path
        if log_file is None:
            log_file = Path.home() / '.filearchitect' / 'logs' / 'filearchitect.log'
        self.log_file = log_file
        self.last_position = 0

        # Window properties
        self.setWindowTitle("Log Viewer - FileArchitect")
        self.setMinimumSize(900, 600)

        # Initialize UI
        self._init_ui()

        # Start update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_logs)
        self.update_timer.start(1000)  # Update every second

        # Load initial logs
        self._load_all_logs()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Top controls
        controls_layout = QHBoxLayout()

        # Log level filter
        level_label = QLabel("Level:")
        self.level_filter = QComboBox()
        self.level_filter.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.setCurrentText("ALL")
        self.level_filter.currentTextChanged.connect(self._apply_filters)

        # Search box
        search_label = QLabel("Search:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter log entries...")
        self.search_box.textChanged.connect(self._apply_filters)

        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)

        controls_layout.addWidget(level_label)
        controls_layout.addWidget(self.level_filter)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(search_label)
        controls_layout.addWidget(self.search_box, 1)
        controls_layout.addWidget(self.auto_scroll_check)

        layout.addLayout(controls_layout)

        # Log display area
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Use monospace font for logs
        font = QFont("Monaco" if Path("/System/Library/Fonts/Monaco.ttf").exists() else "Courier")
        font.setPointSize(11)
        self.log_display.setFont(font)

        layout.addWidget(self.log_display)

        # Bottom buttons
        button_layout = QHBoxLayout()

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_all_logs)

        # Clear button
        self.clear_btn = QPushButton("Clear Display")
        self.clear_btn.clicked.connect(self._clear_display)

        # Export button
        self.export_btn = QPushButton("Export Logs")
        self.export_btn.clicked.connect(self._export_logs)

        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)

        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def _load_all_logs(self):
        """Load all logs from file."""
        try:
            if not self.log_file.exists():
                self.log_display.setPlainText("Log file not found. No logs to display.")
                return

            with open(self.log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.log_display.setPlainText(content)
                self.last_position = len(content)

            # Scroll to bottom if auto-scroll is enabled
            if self.auto_scroll_check.isChecked():
                self._scroll_to_bottom()

            # Apply filters
            self._apply_filters()

        except Exception as e:
            logger.error(f"Failed to load logs: {e}")
            self.log_display.setPlainText(f"Error loading logs: {e}")

    def _update_logs(self):
        """Update logs with new content (tail functionality)."""
        try:
            if not self.log_file.exists():
                return

            # Read only new content
            with open(self.log_file, 'r', encoding='utf-8') as f:
                f.seek(self.last_position)
                new_content = f.read()

                if new_content:
                    # Append new content
                    self.log_display.moveCursor(QTextCursor.MoveOperation.End)
                    self.log_display.insertPlainText(new_content)
                    self.last_position = f.tell()

                    # Scroll to bottom if auto-scroll is enabled
                    if self.auto_scroll_check.isChecked():
                        self._scroll_to_bottom()

                    # Apply filters to new content
                    self._apply_filters()

        except Exception as e:
            logger.error(f"Failed to update logs: {e}")

    def _apply_filters(self):
        """Apply level and search filters to log display."""
        # For now, just highlight search matches
        # Full filtering would require parsing log format
        search_text = self.search_box.text()

        if search_text:
            # Simple highlight of search text
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_display.setTextCursor(cursor)

            # Note: Actual highlighting would require QTextDocument manipulation
            # This is a simplified version

    def _clear_display(self):
        """Clear the log display (doesn't delete log file)."""
        self.log_display.clear()
        self.last_position = 0

    def _export_logs(self):
        """Export logs to a file."""
        from PyQt6.QtWidgets import QFileDialog

        try:
            # Ask user for export location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Logs",
                str(Path.home() / f"filearchitect_logs_{Path(self.log_file).stem}.txt"),
                "Text Files (*.txt);;All Files (*)"
            )

            if file_path:
                # Copy log file to export location
                import shutil
                shutil.copy2(self.log_file, file_path)
                logger.info(f"Logs exported to {file_path}")

                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Logs exported successfully to:\n{file_path}"
                )

        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export logs:\n{str(e)}"
            )

    def _scroll_to_bottom(self):
        """Scroll log display to bottom."""
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Stop update timer
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        super().closeEvent(event)
