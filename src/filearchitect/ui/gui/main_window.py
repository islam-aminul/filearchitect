"""
Main window for FileArchitect GUI.

Provides the primary user interface with path selection, progress display,
and control buttons.
"""

from pathlib import Path
from typing import Optional
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QGroupBox, QMenuBar, QMenu, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon

from ...core.session import SessionManager
from ...core.space import SpaceManager
from ...database.manager import DatabaseManager
from ...config.manager import (
    get_default_config,
    load_config_from_destination,
    load_recent_paths,
    add_recent_path
)
from .progress_widget import ProgressWidget
from .worker import ProcessingWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window for FileArchitect.

    Provides UI for:
    - Source and destination path selection
    - Processing controls (start, pause, resume, stop)
    - Progress monitoring
    - Settings and configuration
    """

    # Signals
    start_processing = pyqtSignal(Path, Path)
    resume_processing = pyqtSignal()
    pause_processing = pyqtSignal()
    stop_processing = pyqtSignal()

    def __init__(self):
        """Initialize main window."""
        super().__init__()

        # Window properties
        self.setWindowTitle("FileArchitect - Intelligent File Organization")
        self.setMinimumSize(900, 700)

        # Components
        self.db_manager = DatabaseManager.get_instance()
        self.session_manager: Optional[SessionManager] = None
        self.space_manager: Optional[SpaceManager] = None
        self.config = get_default_config()

        # State
        self.source_path: Optional[Path] = None
        self.destination_path: Optional[Path] = None
        self.is_processing = False
        self.is_paused = False
        self.current_session_id: Optional[int] = None
        self.worker: Optional[ProcessingWorker] = None

        # Initialize UI
        self._init_ui()
        self._init_menu_bar()
        self._init_status_bar()
        self._load_recent_paths()
        self._update_ui_state()

        logger.info("Main window initialized")

    def _init_ui(self):
        """Initialize the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Add components
        main_layout.addWidget(self._create_path_selection_group())
        main_layout.addWidget(self._create_control_buttons())

        # Add progress widget
        self.progress_widget = ProgressWidget()
        main_layout.addWidget(self.progress_widget)

        main_layout.addStretch()

    def _create_path_selection_group(self) -> QGroupBox:
        """Create path selection group box."""
        group = QGroupBox("File Locations")
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Source path section
        source_layout = QVBoxLayout()
        source_label = QLabel("Source Directory:")
        source_label.setStyleSheet("font-weight: bold;")
        source_layout.addWidget(source_label)

        source_row = QHBoxLayout()
        self.source_path_edit = QLineEdit()
        self.source_path_edit.setReadOnly(True)
        self.source_path_edit.setPlaceholderText("Select source directory...")
        source_row.addWidget(self.source_path_edit)

        self.source_browse_btn = QPushButton("Browse...")
        self.source_browse_btn.setFixedWidth(100)
        self.source_browse_btn.clicked.connect(self._select_source_path)
        source_row.addWidget(self.source_browse_btn)

        source_layout.addLayout(source_row)

        self.source_status_label = QLabel()
        self.source_status_label.setStyleSheet("color: gray; font-size: 11px;")
        source_layout.addWidget(self.source_status_label)

        layout.addLayout(source_layout)

        # Destination path section
        dest_layout = QVBoxLayout()
        dest_label = QLabel("Destination Directory:")
        dest_label.setStyleSheet("font-weight: bold;")
        dest_layout.addWidget(dest_label)

        dest_row = QHBoxLayout()
        self.dest_path_edit = QLineEdit()
        self.dest_path_edit.setReadOnly(True)
        self.dest_path_edit.setPlaceholderText("Select destination directory...")
        dest_row.addWidget(self.dest_path_edit)

        self.dest_browse_btn = QPushButton("Browse...")
        self.dest_browse_btn.setFixedWidth(100)
        self.dest_browse_btn.clicked.connect(self._select_dest_path)
        dest_row.addWidget(self.dest_browse_btn)

        dest_layout.addLayout(dest_row)

        self.dest_status_label = QLabel()
        self.dest_status_label.setStyleSheet("color: gray; font-size: 11px;")
        dest_layout.addWidget(self.dest_status_label)

        layout.addLayout(dest_layout)

        group.setLayout(layout)
        return group

    def _create_control_buttons(self) -> QWidget:
        """Create control button panel."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)

        # Start button
        self.start_btn = QPushButton("Start Processing")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_btn.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_btn)

        # Pause button
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFixedHeight(40)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        layout.addWidget(self.pause_btn)

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self.stop_btn)

        # Settings button
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedHeight(40)
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        layout.addWidget(self.settings_btn)

        return widget

    def _init_menu_bar(self):
        """Initialize menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        settings_action = QAction("&Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._on_settings_clicked)
        edit_menu.addAction(settings_action)

        # Session menu
        session_menu = menubar.addMenu("&Session")

        resume_action = QAction("&Resume Last Session", self)
        resume_action.triggered.connect(self._on_resume_clicked)
        session_menu.addAction(resume_action)

        undo_action = QAction("&Undo Last Session", self)
        undo_action.triggered.connect(self._on_undo_clicked)
        session_menu.addAction(undo_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        log_action = QAction("View &Log", self)
        log_action.triggered.connect(self._on_view_log_clicked)
        view_menu.addAction(log_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about_clicked)
        help_menu.addAction(about_action)

    def _init_status_bar(self):
        """Initialize status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _load_recent_paths(self):
        """Load and populate recent paths."""
        try:
            recent_paths = load_recent_paths()

            if recent_paths.get('source'):
                source = Path(recent_paths['source'][0])
                if source.exists() and source.is_dir():
                    self._set_source_path(source)

            if recent_paths.get('destination'):
                dest = Path(recent_paths['destination'][0])
                if dest.exists() and dest.is_dir():
                    self._set_dest_path(dest)
        except Exception as e:
            logger.warning(f"Failed to load recent paths: {e}")

    def _select_source_path(self):
        """Open dialog to select source path."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Source Directory",
            str(self.source_path) if self.source_path else ""
        )

        if path:
            self._set_source_path(Path(path))

    def _set_source_path(self, path: Path):
        """Set source path and update UI."""
        self.source_path = path
        self.source_path_edit.setText(str(path))

        if path.exists() and path.is_dir():
            self.source_status_label.setText("✓ Directory accessible")
            self.source_status_label.setStyleSheet("color: green; font-size: 11px;")
            add_recent_path('source', str(path))
        else:
            self.source_status_label.setText("✗ Directory not accessible")
            self.source_status_label.setStyleSheet("color: red; font-size: 11px;")

        self._update_ui_state()

    def _select_dest_path(self):
        """Open dialog to select destination path."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Destination Directory",
            str(self.destination_path) if self.destination_path else ""
        )

        if path:
            self._set_dest_path(Path(path))

    def _set_dest_path(self, path: Path):
        """Set destination path and update UI."""
        self.destination_path = path
        self.dest_path_edit.setText(str(path))

        if path.exists() and path.is_dir():
            # Check available space
            self.space_manager = SpaceManager(path)
            space_info = self.space_manager.get_space_info(path)

            status_text = f"✓ Directory accessible - {space_info.free_gb:.1f} GB available"

            if space_info.free_gb < self.space_manager.min_free_gb:
                status_text += f" (Warning: Less than {self.space_manager.min_free_gb} GB)"
                self.dest_status_label.setStyleSheet("color: orange; font-size: 11px;")
            else:
                self.dest_status_label.setStyleSheet("color: green; font-size: 11px;")

            self.dest_status_label.setText(status_text)
            add_recent_path('destination', str(path))

            # Load configuration from destination
            try:
                self.config = load_config_from_destination(path)
                logger.info("Loaded configuration from destination")
            except Exception as e:
                logger.warning(f"Could not load config from destination: {e}")
                self.config = get_default_config()
        else:
            self.dest_status_label.setText("✗ Directory not accessible")
            self.dest_status_label.setStyleSheet("color: red; font-size: 11px;")

        self._update_ui_state()

    def _update_ui_state(self):
        """Update UI element states based on current state."""
        paths_valid = (
            self.source_path and self.source_path.exists() and
            self.destination_path and self.destination_path.exists()
        )

        # Enable/disable buttons based on state
        self.start_btn.setEnabled(paths_valid and not self.is_processing)
        self.pause_btn.setEnabled(self.is_processing and not self.is_paused)
        self.stop_btn.setEnabled(self.is_processing)
        self.settings_btn.setEnabled(not self.is_processing)

        # Update button text
        if self.is_paused:
            self.pause_btn.setText("Resume")
        else:
            self.pause_btn.setText("Pause")

    def _on_start_clicked(self):
        """Handle start button click."""
        if not self.source_path or not self.destination_path:
            QMessageBox.warning(
                self,
                "Invalid Paths",
                "Please select valid source and destination directories."
            )
            return

        # Check if there's an incomplete session
        if self.destination_path:
            self.session_manager = SessionManager(self.destination_path, self.db_manager)
            incomplete = self.session_manager.find_incomplete_session(
                str(self.source_path),
                str(self.destination_path)
            )

            if incomplete:
                reply = QMessageBox.question(
                    self,
                    "Resume Session?",
                    f"Found incomplete session from previous run.\n"
                    f"Progress: {incomplete.get('files_processed', 0)} files processed\n\n"
                    f"Do you want to resume?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self._on_resume_clicked()
                    return

        # Check available space
        if self.space_manager:
            space_info = self.space_manager.get_space_info(self.destination_path)
            if space_info.free_gb < self.space_manager.min_free_gb:
                reply = QMessageBox.warning(
                    self,
                    "Low Disk Space",
                    f"Warning: Only {space_info.free_gb:.1f} GB available.\n"
                    f"Recommended: At least {self.space_manager.min_free_gb} GB\n\n"
                    f"Continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply != QMessageBox.StandardButton.Yes:
                    return

        # Start worker thread
        self._start_worker(resume=False)
        logger.info(f"Starting processing: {self.source_path} -> {self.destination_path}")

    def _start_worker(self, resume: bool = False, session_id: Optional[int] = None):
        """
        Start worker thread.

        Args:
            resume: Whether to resume a previous session
            session_id: Session ID for resume
        """
        # Stop any existing worker
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

        # Create worker
        self.worker = ProcessingWorker(
            config=self.config,
            source_path=self.source_path,
            destination_path=self.destination_path,
            session_id=session_id,
            resume=resume
        )

        # Connect signals
        self.worker.progress_update.connect(self.progress_widget.update_progress)
        self.worker.processing_started.connect(self.processing_started)
        self.worker.processing_completed.connect(self.processing_completed)
        self.worker.processing_error.connect(self.processing_error)
        self.worker.processing_stopped.connect(self.processing_stopped)

        # Start worker
        self.is_processing = True
        self._update_ui_state()
        self.status_bar.showMessage("Starting processing...")
        self.worker.start()

    def _on_pause_clicked(self):
        """Handle pause/resume button click."""
        if not self.worker:
            return

        if self.is_paused:
            self.is_paused = False
            self.worker.resume_processing()
            self.status_bar.showMessage("Resuming processing...")
            logger.info("Resuming processing")
        else:
            self.is_paused = True
            self.worker.pause()
            self.status_bar.showMessage("Paused")
            logger.info("Pausing processing")

        self._update_ui_state()

    def _on_stop_clicked(self):
        """Handle stop button click."""
        if not self.worker:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Stop",
            "Are you sure you want to stop processing?\n"
            "You can resume later from where you left off.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.worker.stop()
            self.status_bar.showMessage("Stopping...")
            logger.info("Stopped processing")

    def _on_resume_clicked(self):
        """Handle resume session."""
        if not self.destination_path:
            QMessageBox.warning(
                self,
                "No Destination",
                "Please select a destination directory first."
            )
            return

        self.session_manager = SessionManager(self.destination_path, self.db_manager)
        incomplete = self.session_manager.find_incomplete_session(
            str(self.source_path) if self.source_path else None,
            str(self.destination_path)
        )

        if not incomplete:
            QMessageBox.information(
                self,
                "No Session to Resume",
                "No incomplete session found."
            )
            return

        # Get session ID
        session_id = incomplete.get('session_id')
        if not session_id:
            QMessageBox.warning(
                self,
                "Invalid Session",
                "Could not get session ID."
            )
            return

        # Set source path if not already set
        if not self.source_path:
            source_str = incomplete.get('source_path')
            if source_str:
                self._set_source_path(Path(source_str))

        # Start worker in resume mode
        self._start_worker(resume=True, session_id=session_id)
        logger.info(f"Resuming session {session_id}")

    def _on_undo_clicked(self):
        """Handle undo last session."""
        if not self.destination_path:
            QMessageBox.warning(
                self,
                "No Destination",
                "Please select a destination directory first."
            )
            return

        # This will be implemented in a separate dialog
        QMessageBox.information(
            self,
            "Undo Session",
            "Undo functionality will be implemented in a separate dialog."
        )

    def _on_settings_clicked(self):
        """Handle settings button click."""
        # Settings dialog will be implemented separately
        QMessageBox.information(
            self,
            "Settings",
            "Settings dialog will be implemented."
        )

    def _on_view_log_clicked(self):
        """Handle view log menu action."""
        QMessageBox.information(
            self,
            "View Log",
            "Log viewer will be implemented."
        )

    def _on_about_clicked(self):
        """Handle about menu action."""
        from ...core.constants import VERSION

        QMessageBox.about(
            self,
            "About FileArchitect",
            f"<h2>FileArchitect {VERSION}</h2>"
            f"<p>Intelligent file organization tool</p>"
            f"<p>Automatically organizes photos, videos, audio, and documents "
            f"based on metadata and content.</p>"
            f"<p><b>Features:</b></p>"
            f"<ul>"
            f"<li>Smart categorization and organization</li>"
            f"<li>Duplicate detection</li>"
            f"<li>EXIF metadata extraction</li>"
            f"<li>Multi-threaded processing</li>"
            f"<li>Session management with resume</li>"
            f"</ul>"
        )

    def processing_started(self, session_id: int):
        """Called when processing starts."""
        self.current_session_id = session_id
        self.is_processing = True
        self._update_ui_state()
        self.status_bar.showMessage("Processing...")

    def processing_paused(self):
        """Called when processing is paused."""
        self.is_paused = True
        self._update_ui_state()
        self.status_bar.showMessage("Paused")

    def processing_resumed(self):
        """Called when processing is resumed."""
        self.is_paused = False
        self._update_ui_state()
        self.status_bar.showMessage("Processing...")

    def processing_stopped(self):
        """Called when processing is stopped."""
        self.is_processing = False
        self.is_paused = False
        self._update_ui_state()
        self.status_bar.showMessage("Stopped")

    def processing_completed(self):
        """Called when processing completes."""
        self.is_processing = False
        self.is_paused = False
        self._update_ui_state()
        self.status_bar.showMessage("Completed")

        QMessageBox.information(
            self,
            "Processing Complete",
            "File organization completed successfully!"
        )

    def processing_error(self, error: str):
        """Called when processing encounters an error."""
        self.is_processing = False
        self.is_paused = False
        self._update_ui_state()
        self.status_bar.showMessage("Error")

        QMessageBox.critical(
            self,
            "Processing Error",
            f"An error occurred during processing:\n\n{error}"
        )
