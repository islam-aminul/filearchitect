"""
Undo dialog for FileArchitect GUI.

Shows preview of files to be deleted during undo operation.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QGroupBox, QProgressDialog,
    QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ...core.session import SessionManager
from ...database.manager import DatabaseManager

logger = logging.getLogger(__name__)


class UndoWorker(QThread):
    """Worker thread for undo operation."""

    finished = pyqtSignal(dict)  # results
    error = pyqtSignal(str)  # error message

    def __init__(self, session_manager: SessionManager, session_id: int, dry_run: bool = False):
        """
        Initialize undo worker.

        Args:
            session_manager: Session manager
            session_id: Session ID to undo
            dry_run: If True, only simulate (don't actually delete files)
        """
        super().__init__()
        self.session_manager = session_manager
        self.session_id = session_id
        self.dry_run = dry_run

    def run(self):
        """Run the undo operation."""
        try:
            results = self.session_manager.undo_session(
                self.session_id,
                dry_run=self.dry_run
            )
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"Undo operation failed: {e}", exc_info=True)
            self.error.emit(str(e))


class UndoDialog(QDialog):
    """
    Undo dialog with file preview.

    Shows what files will be deleted and allows user to proceed or cancel.
    """

    def __init__(
        self,
        destination_path: Path,
        db_manager: DatabaseManager,
        session_id: Optional[int] = None,
        parent=None
    ):
        """
        Initialize undo dialog.

        Args:
            destination_path: Destination directory
            db_manager: Database manager
            session_id: Specific session ID to undo (or None for last)
            parent: Parent widget
        """
        super().__init__(parent)

        self.destination_path = destination_path
        self.db_manager = db_manager
        self.session_manager = SessionManager(destination_path, db_manager)
        self.target_session_id = session_id
        self.preview_results: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Undo Session")
        self.setMinimumSize(700, 500)

        self._init_ui()
        self._load_preview()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Undo Session - Preview")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Warning
        warning_label = QLabel(
            "⚠️ This will DELETE all files that were organized in this session.\n"
            "This operation cannot be undone!"
        )
        warning_label.setStyleSheet("color: #f44336; font-weight: bold; padding: 10px;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Preview group
        self.preview_group = QGroupBox("Files to be Deleted")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText("Loading preview...")
        preview_layout.addWidget(self.preview_text)

        self.preview_group.setLayout(preview_layout)
        layout.addWidget(self.preview_group)

        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.stats_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.undo_btn = QPushButton("Proceed with Undo")
        self.undo_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.undo_btn.clicked.connect(self._perform_undo)
        self.undo_btn.setEnabled(False)
        button_layout.addWidget(self.undo_btn)

        layout.addLayout(button_layout)

    def _load_preview(self):
        """Load undo preview."""
        try:
            # Find session to undo
            if self.target_session_id:
                session_id = self.target_session_id
            else:
                # Get last completed session
                cursor = self.db_manager.execute(
                    """
                    SELECT session_id FROM sessions
                    WHERE status = 'COMPLETED'
                    ORDER BY completed_at DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                if not row:
                    self.preview_text.setPlainText("No completed sessions found to undo.")
                    return
                session_id = row[0]

            self.target_session_id = session_id

            # Run dry-run to get preview
            results = self.session_manager.undo_session(session_id, dry_run=True)
            self.preview_results = results

            # Display preview
            files_to_delete = results['files_to_delete']
            dirs_to_delete = results['dirs_to_delete']

            preview_lines = []
            preview_lines.append(f"Session ID: {session_id}\n")
            preview_lines.append(f"Files to be deleted: {len(files_to_delete)}")
            preview_lines.append(f"Directories to be removed: {len(dirs_to_delete)}\n")
            preview_lines.append("Files:")
            preview_lines.append("-" * 50)

            # Show first 100 files
            for i, file_path in enumerate(files_to_delete[:100]):
                preview_lines.append(str(file_path))

            if len(files_to_delete) > 100:
                preview_lines.append(f"\n... and {len(files_to_delete) - 100} more files")

            self.preview_text.setPlainText("\n".join(preview_lines))

            # Update stats
            self.stats_label.setText(
                f"Total: {len(files_to_delete)} files, {len(dirs_to_delete)} directories"
            )

            # Enable undo button
            self.undo_btn.setEnabled(True)

        except Exception as e:
            logger.error(f"Failed to load undo preview: {e}", exc_info=True)
            self.preview_text.setPlainText(f"Error loading preview:\n{str(e)}")
            QMessageBox.critical(
                self,
                "Preview Error",
                f"Failed to load undo preview:\n{str(e)}"
            )

    def _perform_undo(self):
        """Perform the undo operation."""
        if not self.target_session_id:
            QMessageBox.warning(self, "No Session", "No session selected to undo.")
            return

        # Final confirmation
        reply = QMessageBox.warning(
            self,
            "Confirm Undo",
            f"Are you absolutely sure you want to delete all files from session {self.target_session_id}?\n\n"
            f"This will permanently delete:\n"
            f"- {self.preview_results['files_to_delete'] if self.preview_results else 0} files\n"
            f"- {self.preview_results['dirs_to_delete'] if self.preview_results else 0} directories\n\n"
            f"THIS CANNOT BE UNDONE!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Show progress dialog
        progress = QProgressDialog("Undoing session...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)  # Can't cancel undo
        progress.show()

        # Create worker
        self.worker = UndoWorker(
            self.session_manager,
            self.target_session_id,
            dry_run=False
        )

        # Connect signals
        self.worker.finished.connect(lambda results: self._on_undo_finished(results, progress))
        self.worker.error.connect(lambda error: self._on_undo_error(error, progress))

        # Start worker
        self.worker.start()

    def _on_undo_finished(self, results: Dict[str, Any], progress: QProgressDialog):
        """Handle undo completion."""
        progress.close()

        # Show results
        QMessageBox.information(
            self,
            "Undo Complete",
            f"Session undo completed:\n\n"
            f"Files deleted: {results['files_deleted']}\n"
            f"Directories removed: {results['dirs_deleted']}\n"
            f"Failed: {results['files_failed']}\n"
        )

        self.accept()

    def _on_undo_error(self, error: str, progress: QProgressDialog):
        """Handle undo error."""
        progress.close()

        QMessageBox.critical(
            self,
            "Undo Error",
            f"Undo operation failed:\n{error}"
        )

        self.reject()
