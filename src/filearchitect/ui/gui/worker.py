"""
Background worker thread for FileArchitect GUI.

Runs the processing orchestrator in a separate thread to keep the GUI responsive.
"""

from pathlib import Path
from typing import Optional
import logging

from PyQt6.QtCore import QThread, pyqtSignal

from ...core.orchestrator import ProcessingOrchestrator, ProcessingProgress
from ...core.session import SessionManager
from ...database.manager import DatabaseManager
from ...config.models import Config

logger = logging.getLogger(__name__)


class ProcessingWorker(QThread):
    """
    Background worker thread for file processing.

    Runs the ProcessingOrchestrator in a separate thread and emits
    signals for progress updates and completion.
    """

    # Signals
    progress_update = pyqtSignal(object)  # ProcessingProgress
    processing_started = pyqtSignal(int)  # session_id
    processing_completed = pyqtSignal()
    processing_error = pyqtSignal(str)  # error message
    processing_stopped = pyqtSignal()

    def __init__(
        self,
        config: Config,
        source_path: Path,
        destination_path: Path,
        session_id: Optional[int] = None,
        resume: bool = False
    ):
        """
        Initialize worker thread.

        Args:
            config: Configuration object
            source_path: Source directory
            destination_path: Destination directory
            session_id: Session ID (for resume)
            resume: Whether this is a resume operation
        """
        super().__init__()

        self.config = config
        self.source_path = source_path
        self.destination_path = destination_path
        self.session_id = session_id
        self.resume = resume

        self.orchestrator: Optional[ProcessingOrchestrator] = None
        self.db_manager = DatabaseManager.get_instance()
        self.session_manager = SessionManager(destination_path, self.db_manager)

        self._should_stop = False
        self._should_pause = False

    def run(self):
        """Run the processing in the background thread."""
        try:
            logger.info("Worker thread started")

            # Create or get session
            if self.resume and self.session_id:
                session_id = self.session_id
                logger.info(f"Resuming session {session_id}")
            else:
                # Create new session
                session_id = self.session_manager.create_session(
                    str(self.source_path),
                    str(self.destination_path)
                )
                logger.info(f"Created new session {session_id}")

            self.processing_started.emit(session_id)

            # Get number of workers from config
            num_workers = getattr(self.config.processing, 'threads', None)

            # Create orchestrator
            self.orchestrator = ProcessingOrchestrator(
                config=self.config,
                source_path=self.source_path,
                destination_path=self.destination_path,
                session_id=session_id,
                num_workers=num_workers,
                progress_callback=self._on_progress,
                session_manager=self.session_manager
            )

            # Start processing
            self.orchestrator.start()

            # Emit completion
            self.processing_completed.emit()
            logger.info("Processing completed successfully")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Worker thread error: {e}", exc_info=True)
            self.processing_error.emit(error_msg)

    def _on_progress(self, progress: ProcessingProgress):
        """
        Progress callback from orchestrator.

        Args:
            progress: ProcessingProgress object
        """
        # Emit progress signal to GUI
        self.progress_update.emit(progress)

    def pause(self):
        """Pause processing."""
        if self.orchestrator:
            logger.info("Worker: pausing orchestrator")
            self.orchestrator.pause()

    def resume_processing(self):
        """Resume processing."""
        if self.orchestrator:
            logger.info("Worker: resuming orchestrator")
            self.orchestrator.resume()

    def stop(self):
        """Stop processing."""
        if self.orchestrator:
            logger.info("Worker: stopping orchestrator")
            self.orchestrator.stop()
            self.processing_stopped.emit()

    def get_progress(self) -> Optional[ProcessingProgress]:
        """
        Get current progress.

        Returns:
            ProcessingProgress object or None
        """
        if self.orchestrator:
            return self.orchestrator.get_progress()
        return None
