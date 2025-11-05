"""
Processing orchestrator for FileArchitect.

This module implements the main orchestrator that manages parallel file processing,
resource allocation, and progress tracking.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty
from threading import Thread, Event, Lock
import logging
import time

from ..core.constants import ProcessingStatus, SessionStatus
from ..core.exceptions import OrchestratorError
from ..core.pipeline import ProcessingPipeline, PipelineResult
from ..core.scanner import FileScanner
from ..database.manager import DatabaseManager
from ..core.deduplication import DeduplicationEngine
from ..core.session import SessionManager, ProgressSnapshot

logger = logging.getLogger(__name__)


class OrchestratorState(Enum):
    """Orchestrator states."""
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ProcessingProgress:
    """Processing progress information."""
    state: OrchestratorState
    session_id: int
    start_time: Optional[datetime] = None
    current_file: Optional[Path] = None
    files_scanned: int = 0
    files_processed: int = 0
    files_pending: int = 0
    files_skipped: int = 0
    files_duplicates: int = 0
    files_error: int = 0
    bytes_processed: int = 0
    bytes_total: int = 0
    processing_speed: float = 0.0  # files per second
    eta_seconds: Optional[int] = None
    last_update: Optional[datetime] = None
    category_counts: Dict[str, int] = None

    def __post_init__(self):
        if self.category_counts is None:
            self.category_counts = {}

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        total = self.files_scanned
        if total == 0:
            return 0.0
        completed = self.files_processed + self.files_skipped + self.files_duplicates + self.files_error
        return (completed / total) * 100.0

    @property
    def elapsed_seconds(self) -> int:
        """Calculate elapsed time in seconds."""
        if not self.start_time:
            return 0
        return int((datetime.now() - self.start_time).total_seconds())


class ProcessingOrchestrator:
    """
    Main orchestrator for file processing.

    Manages parallel processing with worker threads, progress tracking,
    and resource management.
    """

    def __init__(
        self,
        config: Any,
        source_path: Path,
        destination_path: Path,
        session_id: int,
        num_workers: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        session_manager: Optional[SessionManager] = None
    ):
        """
        Initialize orchestrator.

        Args:
            config: Configuration object
            source_path: Source directory to scan
            destination_path: Destination root directory
            session_id: Session ID
            num_workers: Number of worker threads (default: CPU count)
            progress_callback: Optional callback for progress updates
            session_manager: Optional session manager for persistence
        """
        self.config = config
        self.source_path = source_path
        self.destination_path = destination_path
        self.session_id = session_id
        self.progress_callback = progress_callback

        # Worker configuration
        import multiprocessing
        self.num_workers = num_workers or multiprocessing.cpu_count()

        # Initialize components
        self.db_manager = DatabaseManager.get_instance()
        self.dedup_engine = DeduplicationEngine(config, self.db_manager)
        self.scanner = FileScanner(config)
        self.session_manager = session_manager or SessionManager(destination_path, self.db_manager)

        # Processing state
        self.state = OrchestratorState.IDLE
        self.state_lock = Lock()

        # File queue and workers
        self.file_queue: Queue[Optional[Path]] = Queue()
        self.result_queue: Queue[PipelineResult] = Queue()
        self.workers: List[Thread] = []

        # Control events
        self.pause_event = Event()
        self.stop_event = Event()
        self.pause_event.set()  # Not paused initially

        # Progress tracking
        self.progress = ProcessingProgress(
            state=self.state,
            session_id=session_id,
            start_time=None
        )
        self.progress_lock = Lock()

        # Statistics
        self.file_list: List[Path] = []
        self.total_size: int = 0

    def start(self):
        """Start processing."""
        logger.info(f"Starting orchestrator with {self.num_workers} workers")

        with self.state_lock:
            if self.state != OrchestratorState.IDLE:
                raise OrchestratorError(f"Cannot start from state {self.state}")
            self.state = OrchestratorState.SCANNING
            self.progress.state = self.state
            self.progress.start_time = datetime.now()

        # Update session status
        self.session_manager.update_session_status(self.session_id, SessionStatus.IN_PROGRESS)

        try:
            # Phase 1: Scan files
            self._scan_files()

            # Phase 2: Start workers
            self._start_workers()

            # Phase 3: Process files
            self._process_files()

            # Phase 4: Wait for completion
            self._wait_for_completion()

            # Update state
            with self.state_lock:
                if self.state != OrchestratorState.STOPPING:
                    self.state = OrchestratorState.COMPLETED
                    self.progress.state = self.state
                    logger.info("Processing completed successfully")

                    # Update session status
                    self.session_manager.update_session_status(self.session_id, SessionStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            with self.state_lock:
                self.state = OrchestratorState.ERROR
                self.progress.state = self.state

            # Update session status
            self.session_manager.update_session_status(
                self.session_id,
                SessionStatus.ERROR,
                str(e)
            )
            raise

        finally:
            self._cleanup()

    def pause(self):
        """Pause processing."""
        logger.info("Pausing orchestrator")
        with self.state_lock:
            if self.state != OrchestratorState.PROCESSING:
                logger.warning(f"Cannot pause from state {self.state}")
                return
            self.state = OrchestratorState.PAUSED
            self.progress.state = self.state

        self.pause_event.clear()

        # Update session status
        self.session_manager.update_session_status(self.session_id, SessionStatus.PAUSED)

        self._update_progress()

    def resume(self):
        """Resume processing."""
        logger.info("Resuming orchestrator")
        with self.state_lock:
            if self.state != OrchestratorState.PAUSED:
                logger.warning(f"Cannot resume from state {self.state}")
                return
            self.state = OrchestratorState.PROCESSING
            self.progress.state = self.state

        self.pause_event.set()

        # Update session status
        self.session_manager.update_session_status(self.session_id, SessionStatus.IN_PROGRESS)

        self._update_progress()

    def stop(self):
        """Stop processing."""
        logger.info("Stopping orchestrator")
        with self.state_lock:
            if self.state in (OrchestratorState.STOPPED, OrchestratorState.COMPLETED):
                logger.warning(f"Already in state {self.state}")
                return
            self.state = OrchestratorState.STOPPING
            self.progress.state = self.state

        # Signal stop
        self.stop_event.set()
        self.pause_event.set()  # Unpause if paused

        # Wait for workers to finish current files
        self._wait_for_workers()

        with self.state_lock:
            self.state = OrchestratorState.STOPPED
            self.progress.state = self.state

        # Update session status
        self.session_manager.update_session_status(self.session_id, SessionStatus.STOPPED)

        logger.info("Orchestrator stopped")
        self._update_progress()

    def get_progress(self) -> ProcessingProgress:
        """
        Get current progress.

        Returns:
            ProcessingProgress object
        """
        with self.progress_lock:
            return ProcessingProgress(
                state=self.progress.state,
                session_id=self.progress.session_id,
                start_time=self.progress.start_time,
                current_file=self.progress.current_file,
                files_scanned=self.progress.files_scanned,
                files_processed=self.progress.files_processed,
                files_pending=self.progress.files_pending,
                files_skipped=self.progress.files_skipped,
                files_duplicates=self.progress.files_duplicates,
                files_error=self.progress.files_error,
                bytes_processed=self.progress.bytes_processed,
                bytes_total=self.progress.bytes_total,
                processing_speed=self.progress.processing_speed,
                eta_seconds=self.progress.eta_seconds,
                last_update=self.progress.last_update,
                category_counts=self.progress.category_counts.copy()
            )

    def _scan_files(self):
        """Scan source directory for files."""
        logger.info(f"Scanning {self.source_path}")

        self.file_list = []
        self.total_size = 0

        for file_path in self.scanner.scan(self.source_path):
            # Check if stopped
            if self.stop_event.is_set():
                logger.info("Scanning interrupted")
                break

            self.file_list.append(file_path)
            try:
                self.total_size += file_path.stat().st_size
            except (OSError, FileNotFoundError):
                pass

            # Update progress periodically
            if len(self.file_list) % 100 == 0:
                with self.progress_lock:
                    self.progress.files_scanned = len(self.file_list)
                    self.progress.bytes_total = self.total_size
                self._update_progress()

        with self.progress_lock:
            self.progress.files_scanned = len(self.file_list)
            self.progress.bytes_total = self.total_size
            self.progress.files_pending = len(self.file_list)

        logger.info(
            f"Scanning complete: {len(self.file_list)} files, "
            f"{self.total_size / (1024**3):.2f} GB"
        )
        self._update_progress()

    def _start_workers(self):
        """Start worker threads."""
        logger.info(f"Starting {self.num_workers} worker threads")

        with self.state_lock:
            self.state = OrchestratorState.PROCESSING
            self.progress.state = self.state

        for i in range(self.num_workers):
            worker = Thread(
                target=self._worker_loop,
                args=(i,),
                name=f"Worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

        # Start result aggregator thread
        aggregator = Thread(
            target=self._result_aggregator_loop,
            name="ResultAggregator",
            daemon=True
        )
        aggregator.start()
        self.workers.append(aggregator)

    def _process_files(self):
        """Add files to processing queue."""
        logger.info(f"Queueing {len(self.file_list)} files for processing")

        for file_path in self.file_list:
            # Check if stopped
            if self.stop_event.is_set():
                break

            self.file_queue.put(file_path)

        # Add sentinel values to signal workers to exit
        for _ in range(self.num_workers):
            self.file_queue.put(None)

    def _worker_loop(self, worker_id: int):
        """
        Worker thread loop.

        Args:
            worker_id: Worker ID
        """
        logger.debug(f"Worker {worker_id} started")

        # Create pipeline for this worker
        pipeline = ProcessingPipeline(
            self.config,
            self.destination_path,
            self.session_id,
            self.db_manager,
            self.dedup_engine,
            progress_callback=None  # Don't use callback in workers
        )

        while not self.stop_event.is_set():
            # Wait for pause
            self.pause_event.wait()

            # Get file from queue
            try:
                file_path = self.file_queue.get(timeout=1.0)
            except Empty:
                continue

            # Check for sentinel
            if file_path is None:
                break

            # Update current file
            with self.progress_lock:
                self.progress.current_file = file_path

            # Process file
            try:
                result = pipeline.process_file(file_path)
                self.result_queue.put(result)
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", exc_info=True)

            finally:
                self.file_queue.task_done()

        logger.debug(f"Worker {worker_id} stopped")

    def _result_aggregator_loop(self):
        """Result aggregator thread loop."""
        logger.debug("Result aggregator started")

        last_update = time.time()
        update_interval = 1.0  # Update progress every second

        while not self.stop_event.is_set():
            try:
                result = self.result_queue.get(timeout=1.0)
            except Empty:
                # Update progress periodically even without results
                if time.time() - last_update >= update_interval:
                    self._update_progress()
                    last_update = time.time()
                continue

            # Update progress with result
            with self.progress_lock:
                self.progress.files_pending -= 1

                if result.status == ProcessingStatus.COMPLETED:
                    self.progress.files_processed += 1
                    self.progress.bytes_processed += result.bytes_processed

                    # Update category counts
                    if result.category:
                        self.progress.category_counts[result.category] = \
                            self.progress.category_counts.get(result.category, 0) + 1

                elif result.status == ProcessingStatus.SKIPPED:
                    self.progress.files_skipped += 1

                elif result.status == ProcessingStatus.DUPLICATE:
                    self.progress.files_duplicates += 1

                elif result.status == ProcessingStatus.ERROR:
                    self.progress.files_error += 1

                # Calculate processing speed and ETA
                elapsed = self.progress.elapsed_seconds
                if elapsed > 0:
                    completed = (
                        self.progress.files_processed +
                        self.progress.files_skipped +
                        self.progress.files_duplicates +
                        self.progress.files_error
                    )
                    self.progress.processing_speed = completed / elapsed

                    if self.progress.processing_speed > 0:
                        remaining = self.progress.files_pending
                        self.progress.eta_seconds = int(remaining / self.progress.processing_speed)

                self.progress.last_update = datetime.now()

            # Invoke progress callback
            if time.time() - last_update >= update_interval:
                self._update_progress()
                last_update = time.time()

            self.result_queue.task_done()

        logger.debug("Result aggregator stopped")

    def _wait_for_completion(self):
        """Wait for all files to be processed."""
        logger.info("Waiting for processing to complete")
        self.file_queue.join()

    def _wait_for_workers(self):
        """Wait for all worker threads to finish."""
        logger.info("Waiting for workers to finish")
        for worker in self.workers:
            worker.join(timeout=5.0)

    def _cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up resources")

        # Clear queues
        while not self.file_queue.empty():
            try:
                self.file_queue.get_nowait()
            except Empty:
                break

        while not self.result_queue.empty():
            try:
                self.result_queue.get_nowait()
            except Empty:
                break

        # Final progress update
        self._update_progress()

        # Clear progress file if completed successfully
        if self.state == OrchestratorState.COMPLETED:
            self.session_manager.clear_progress()

    def _update_progress(self):
        """Invoke progress callback and save progress to disk."""
        progress = self.get_progress()

        # Save progress to disk
        try:
            snapshot = ProgressSnapshot.from_progress(progress)
            self.session_manager.save_progress(snapshot)
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

        # Invoke callback
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
