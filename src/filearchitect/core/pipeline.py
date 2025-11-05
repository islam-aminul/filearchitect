"""
Processing pipeline for FileArchitect.

This module implements the main file processing pipeline that orchestrates
all the processing steps for each file.
"""

from pathlib import Path
from typing import Optional, Dict, Any, Callable
from enum import Enum
import logging

from ..core.constants import FileType, ProcessingStatus
from ..core.exceptions import ProcessingError, PipelineError
from ..core.detector import detect_file_type
from ..core.deduplication import DeduplicationEngine
from ..database.manager import DatabaseManager
from ..processors.base import BaseProcessor, ProcessingResult
from ..processors.image import ImageProcessor
from ..processors.video import VideoProcessor
from ..processors.audio import AudioProcessor
from ..processors.document import DocumentProcessor

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Pipeline processing stages."""
    INIT = "init"
    PROCESSED_CHECK = "processed_check"
    PATTERN_CHECK = "pattern_check"
    TYPE_DETECTION = "type_detection"
    UNKNOWN_FILTER = "unknown_filter"
    DEDUPLICATION = "deduplication"
    METADATA_EXTRACTION = "metadata_extraction"
    CATEGORIZATION = "categorization"
    PATH_GENERATION = "path_generation"
    CONFLICT_RESOLUTION = "conflict_resolution"
    FILE_OPERATION = "file_operation"
    DATABASE_UPDATE = "database_update"
    PROGRESS_UPDATE = "progress_update"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineResult:
    """Result of pipeline processing."""

    def __init__(
        self,
        source_path: Path,
        destination_path: Optional[Path] = None,
        status: ProcessingStatus = ProcessingStatus.PENDING,
        stage: PipelineStage = PipelineStage.INIT,
        file_type: Optional[FileType] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duplicate_of: Optional[Path] = None,
        bytes_processed: int = 0
    ):
        self.source_path = source_path
        self.destination_path = destination_path
        self.status = status
        self.stage = stage
        self.file_type = file_type
        self.category = category
        self.metadata = metadata or {}
        self.error = error
        self.duplicate_of = duplicate_of
        self.bytes_processed = bytes_processed

    def __repr__(self) -> str:
        return (
            f"PipelineResult(source={self.source_path.name}, "
            f"status={self.status.value}, stage={self.stage.value})"
        )


class ProcessingPipeline:
    """
    Main processing pipeline for files.

    Orchestrates all processing steps for each file through a state machine.
    """

    def __init__(
        self,
        config: Any,
        destination_root: Path,
        session_id: int,
        db_manager: Optional[DatabaseManager] = None,
        dedup_engine: Optional[DeduplicationEngine] = None,
        progress_callback: Optional[Callable] = None
    ):
        """
        Initialize processing pipeline.

        Args:
            config: Configuration object
            destination_root: Destination root directory
            session_id: Current session ID
            db_manager: Database manager instance
            dedup_engine: Deduplication engine instance
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.destination_root = destination_root
        self.session_id = session_id
        self.db_manager = db_manager or DatabaseManager.get_instance()
        self.dedup_engine = dedup_engine or DeduplicationEngine(config, self.db_manager)
        self.progress_callback = progress_callback

        # Initialize processors
        self.processors: Dict[FileType, BaseProcessor] = {
            FileType.IMAGE: ImageProcessor(config),
            FileType.VIDEO: VideoProcessor(config),
            FileType.AUDIO: AudioProcessor(config),
            FileType.DOCUMENT: DocumentProcessor(config)
        }

        # Processing statistics
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'duplicates': 0,
            'errors': 0,
            'bytes_processed': 0
        }

    def process_file(self, file_path: Path) -> PipelineResult:
        """
        Process a single file through the entire pipeline.

        Args:
            file_path: Path to file to process

        Returns:
            PipelineResult with processing outcome
        """
        result = PipelineResult(source_path=file_path)

        try:
            # Stage 1: Check if already processed
            result.stage = PipelineStage.PROCESSED_CHECK
            if self._is_already_processed(file_path):
                logger.debug(f"File already processed: {file_path}")
                result.status = ProcessingStatus.SKIPPED
                result.stage = PipelineStage.SKIPPED
                self.stats['skipped'] += 1
                return result

            # Stage 2: Check skip patterns
            result.stage = PipelineStage.PATTERN_CHECK
            if self._should_skip_by_pattern(file_path):
                logger.debug(f"File skipped by pattern: {file_path}")
                result.status = ProcessingStatus.SKIPPED
                result.stage = PipelineStage.SKIPPED
                self.stats['skipped'] += 1
                return result

            # Stage 3: Detect file type
            result.stage = PipelineStage.TYPE_DETECTION
            file_type = detect_file_type(file_path)
            result.file_type = file_type

            # Stage 4: Filter unknown types
            result.stage = PipelineStage.UNKNOWN_FILTER
            if file_type == FileType.UNKNOWN:
                logger.debug(f"Unknown file type: {file_path}")
                result.status = ProcessingStatus.SKIPPED
                result.stage = PipelineStage.SKIPPED
                self.stats['skipped'] += 1
                return result

            # Stage 5: Deduplication check
            result.stage = PipelineStage.DEDUPLICATION
            duplicate_info = self.dedup_engine.check_duplicate(file_path, file_type)
            if duplicate_info:
                logger.info(f"Duplicate file: {file_path} -> {duplicate_info['original_path']}")
                result.status = ProcessingStatus.DUPLICATE
                result.stage = PipelineStage.SKIPPED
                result.duplicate_of = Path(duplicate_info['original_path'])
                self.stats['duplicates'] += 1

                # Record duplicate in database
                self._record_duplicate(file_path, duplicate_info)
                return result

            # Get processor for file type
            processor = self.processors.get(file_type)
            if not processor:
                logger.warning(f"No processor for file type {file_type}: {file_path}")
                result.status = ProcessingStatus.SKIPPED
                result.stage = PipelineStage.SKIPPED
                self.stats['skipped'] += 1
                return result

            # Stage 6: Extract metadata
            result.stage = PipelineStage.METADATA_EXTRACTION
            metadata = processor.extract_metadata(file_path)
            result.metadata = metadata

            # Stage 7: Categorize
            result.stage = PipelineStage.CATEGORIZATION
            category = processor.categorize(file_path, metadata)
            result.category = category
            metadata['category'] = category

            # Stage 8: Generate destination path
            result.stage = PipelineStage.PATH_GENERATION
            dest_path = processor.get_destination_path(
                file_path,
                self.destination_root,
                metadata,
                category
            )

            # Stage 9: Resolve filename conflicts
            result.stage = PipelineStage.CONFLICT_RESOLUTION
            dest_path = self._resolve_conflict(dest_path)
            result.destination_path = dest_path

            # Stage 10: Process file (copy/convert)
            result.stage = PipelineStage.FILE_OPERATION
            processing_result = processor.process(file_path, dest_path, metadata)

            # Update result with processing outcome
            result.status = processing_result.status
            result.bytes_processed = file_path.stat().st_size
            self.stats['bytes_processed'] += result.bytes_processed

            # Stage 11: Update database
            result.stage = PipelineStage.DATABASE_UPDATE
            self._update_database(file_path, processing_result)

            # Stage 12: Progress update
            result.stage = PipelineStage.PROGRESS_UPDATE
            self.stats['processed'] += 1
            if self.progress_callback:
                self.progress_callback(result)

            # Stage 13: Complete
            result.stage = PipelineStage.COMPLETED
            logger.info(
                f"Processed {file_path} -> {dest_path} "
                f"[{file_type.value}/{category}]"
            )

            return result

        except Exception as e:
            logger.error(f"Pipeline error for {file_path}: {e}", exc_info=True)
            result.status = ProcessingStatus.ERROR
            result.stage = PipelineStage.FAILED
            result.error = str(e)
            self.stats['errors'] += 1

            # Record error in database
            self._record_error(file_path, str(e))

            return result

    def _is_already_processed(self, file_path: Path) -> bool:
        """
        Check if file was already processed in this session.

        Args:
            file_path: Path to file

        Returns:
            True if file was already processed
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM file_mappings
                    WHERE session_id = ?
                      AND source_path = ?
                      AND status = ?
                    """,
                    (self.session_id, str(file_path), ProcessingStatus.COMPLETED.value)
                )
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.warning(f"Error checking processed status: {e}")
            return False

    def _should_skip_by_pattern(self, file_path: Path) -> bool:
        """
        Check if file should be skipped by pattern.

        Args:
            file_path: Path to file

        Returns:
            True if file should be skipped
        """
        # Skip hidden files if configured
        if self.config.skip_hidden_files and file_path.name.startswith('.'):
            return True

        # Skip system files
        system_patterns = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
        if file_path.name in system_patterns:
            return True

        # Check skip patterns from config
        skip_patterns = getattr(self.config, 'skip_patterns', [])
        for pattern in skip_patterns:
            if file_path.match(pattern):
                return True

        return False

    def _resolve_conflict(self, dest_path: Path) -> Path:
        """
        Resolve filename conflicts by adding counter suffix.

        Args:
            dest_path: Proposed destination path

        Returns:
            Unique destination path
        """
        if not dest_path.exists():
            return dest_path

        # Add counter suffix
        stem = dest_path.stem
        suffix = dest_path.suffix
        parent = dest_path.parent
        counter = 1

        while True:
            new_name = f"{stem}_{counter}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1

            # Prevent infinite loop
            if counter > 10000:
                raise PipelineError(f"Too many conflicts for {dest_path}")

    def _record_duplicate(self, file_path: Path, duplicate_info: Dict[str, Any]):
        """Record duplicate file in database."""
        try:
            with self.db_manager.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO file_mappings (
                        session_id, source_path, destination_path,
                        status, error_message
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        str(file_path),
                        duplicate_info['original_path'],
                        ProcessingStatus.DUPLICATE.value,
                        f"Duplicate of {duplicate_info['original_path']}"
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording duplicate: {e}")

    def _update_database(self, file_path: Path, processing_result: ProcessingResult):
        """Update database with processing result."""
        try:
            with self.db_manager.get_connection() as conn:
                # Insert file record
                cursor = conn.execute(
                    """
                    INSERT INTO files (
                        file_path, file_hash, file_size, file_type,
                        category, metadata_json, date_taken
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(file_path),
                        processing_result.metadata.get('file_hash'),
                        file_path.stat().st_size,
                        processing_result.metadata.get('file_type'),
                        processing_result.category,
                        str(processing_result.metadata),
                        processing_result.metadata.get('date_taken')
                    )
                )
                file_id = cursor.lastrowid

                # Insert file mapping
                conn.execute(
                    """
                    INSERT INTO file_mappings (
                        session_id, source_path, destination_path,
                        file_id, status
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        str(processing_result.source_path),
                        str(processing_result.destination_path),
                        file_id,
                        processing_result.status.value
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating database: {e}")

    def _record_error(self, file_path: Path, error_message: str):
        """Record error in database."""
        try:
            with self.db_manager.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO file_mappings (
                        session_id, source_path, status, error_message
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        self.session_id,
                        str(file_path),
                        ProcessingStatus.ERROR.value,
                        error_message
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error recording error: {e}")

    def get_statistics(self) -> Dict[str, int]:
        """
        Get processing statistics.

        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()

    def reset_statistics(self):
        """Reset processing statistics."""
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'duplicates': 0,
            'errors': 0,
            'bytes_processed': 0
        }
