"""
Session management for FileArchitect.

This module handles session persistence, resume logic, and undo/rollback functionality.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json
import logging

from ..core.constants import SessionStatus, ProcessingStatus
from ..core.exceptions import DatabaseError
from ..database.manager import DatabaseManager

logger = logging.getLogger(__name__)


class SessionAction(Enum):
    """Session actions for tracking."""
    CREATED = "created"
    STARTED = "started"
    PAUSED = "paused"
    RESUMED = "resumed"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ProgressSnapshot:
    """Snapshot of processing progress at a point in time."""
    session_id: int
    timestamp: str
    status: str
    files_scanned: int
    files_processed: int
    files_pending: int
    files_skipped: int
    files_duplicates: int
    files_error: int
    bytes_processed: int
    bytes_total: int
    processing_speed: float
    eta_seconds: Optional[int]
    category_counts: Dict[str, int]
    current_file: Optional[str] = None

    @classmethod
    def from_progress(cls, progress: Any) -> 'ProgressSnapshot':
        """
        Create snapshot from ProcessingProgress object.

        Args:
            progress: ProcessingProgress object

        Returns:
            ProgressSnapshot
        """
        return cls(
            session_id=progress.session_id,
            timestamp=datetime.now().isoformat(),
            status=progress.state.value,
            files_scanned=progress.files_scanned,
            files_processed=progress.files_processed,
            files_pending=progress.files_pending,
            files_skipped=progress.files_skipped,
            files_duplicates=progress.files_duplicates,
            files_error=progress.files_error,
            bytes_processed=progress.bytes_processed,
            bytes_total=progress.bytes_total,
            processing_speed=progress.processing_speed,
            eta_seconds=progress.eta_seconds,
            category_counts=progress.category_counts.copy(),
            current_file=str(progress.current_file) if progress.current_file else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressSnapshot':
        """Create from dictionary."""
        return cls(**data)


class SessionManager:
    """
    Manages processing sessions with persistence and resume capabilities.

    Handles session lifecycle, progress persistence, and undo operations.
    """

    def __init__(
        self,
        destination_root: Path,
        db_manager: Optional[DatabaseManager] = None
    ):
        """
        Initialize session manager.

        Args:
            destination_root: Destination root directory
            db_manager: Database manager instance
        """
        self.destination_root = destination_root
        self.db_manager = db_manager or DatabaseManager.get_instance()

        # Progress file location
        self.progress_dir = destination_root / "conf"
        self.progress_file = self.progress_dir / "progress.json"

    def create_session(
        self,
        source_path: Path,
        destination_path: Path,
        config_hash: Optional[str] = None
    ) -> int:
        """
        Create a new processing session.

        Args:
            source_path: Source directory path
            destination_path: Destination directory path
            config_hash: Optional configuration hash

        Returns:
            Session ID

        Raises:
            DatabaseError: If session creation fails
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO sessions (
                        source_path, destination_path, config_hash,
                        status, created_at, started_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(source_path),
                        str(destination_path),
                        config_hash,
                        SessionStatus.PENDING.value,
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    )
                )
                session_id = cursor.lastrowid
                conn.commit()

                logger.info(f"Created session {session_id}: {source_path} -> {destination_path}")
                return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise DatabaseError(f"Failed to create session: {e}") from e

    def update_session_status(
        self,
        session_id: int,
        status: SessionStatus,
        error_message: Optional[str] = None
    ):
        """
        Update session status.

        Args:
            session_id: Session ID
            status: New status
            error_message: Optional error message
        """
        try:
            with self.db_manager.get_connection() as conn:
                if status == SessionStatus.COMPLETED:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET status = ?, completed_at = ?, error_message = ?
                        WHERE session_id = ?
                        """,
                        (status.value, datetime.now().isoformat(), error_message, session_id)
                    )
                else:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET status = ?, error_message = ?
                        WHERE session_id = ?
                        """,
                        (status.value, error_message, session_id)
                    )
                conn.commit()

                logger.info(f"Updated session {session_id} status to {status.value}")

        except Exception as e:
            logger.error(f"Failed to update session status: {e}")

    def save_progress(self, snapshot: ProgressSnapshot):
        """
        Save progress snapshot to disk.

        Args:
            snapshot: Progress snapshot to save
        """
        try:
            # Ensure progress directory exists
            self.progress_dir.mkdir(parents=True, exist_ok=True)

            # Write progress file
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot.to_dict(), f, indent=2)

            logger.debug(f"Saved progress snapshot for session {snapshot.session_id}")

        except Exception as e:
            logger.error(f"Failed to save progress: {e}")

    def load_progress(self) -> Optional[ProgressSnapshot]:
        """
        Load progress snapshot from disk.

        Returns:
            ProgressSnapshot or None if not found
        """
        try:
            if not self.progress_file.exists():
                return None

            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            snapshot = ProgressSnapshot.from_dict(data)
            logger.info(f"Loaded progress snapshot for session {snapshot.session_id}")
            return snapshot

        except Exception as e:
            logger.error(f"Failed to load progress: {e}")
            return None

    def clear_progress(self):
        """Clear progress file."""
        try:
            if self.progress_file.exists():
                self.progress_file.unlink()
                logger.info("Cleared progress file")
        except Exception as e:
            logger.error(f"Failed to clear progress: {e}")

    def find_incomplete_session(self) -> Optional[Dict[str, Any]]:
        """
        Find incomplete session that can be resumed.

        Returns:
            Session info dictionary or None
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT session_id, source_path, destination_path,
                           status, created_at, started_at
                    FROM sessions
                    WHERE status IN (?, ?)
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (SessionStatus.IN_PROGRESS.value, SessionStatus.PAUSED.value)
                )
                row = cursor.fetchone()

                if row:
                    return {
                        'session_id': row[0],
                        'source_path': row[1],
                        'destination_path': row[2],
                        'status': row[3],
                        'created_at': row[4],
                        'started_at': row[5]
                    }

                return None

        except Exception as e:
            logger.error(f"Failed to find incomplete session: {e}")
            return None

    def get_processed_files(self, session_id: int) -> set:
        """
        Get set of files already processed in session.

        Args:
            session_id: Session ID

        Returns:
            Set of processed file paths
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT source_path FROM file_mappings
                    WHERE session_id = ?
                      AND status = ?
                    """,
                    (session_id, ProcessingStatus.COMPLETED.value)
                )
                return {Path(row[0]) for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Failed to get processed files: {e}")
            return set()

    def get_session_statistics(self, session_id: int) -> Dict[str, Any]:
        """
        Get session statistics.

        Args:
            session_id: Session ID

        Returns:
            Statistics dictionary
        """
        try:
            with self.db_manager.get_connection() as conn:
                # Get file counts by status
                cursor = conn.execute(
                    """
                    SELECT status, COUNT(*) FROM file_mappings
                    WHERE session_id = ?
                    GROUP BY status
                    """,
                    (session_id,)
                )
                status_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get total files
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM file_mappings
                    WHERE session_id = ?
                    """,
                    (session_id,)
                )
                total_files = cursor.fetchone()[0]

                # Get session info
                cursor = conn.execute(
                    """
                    SELECT status, created_at, started_at, completed_at
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,)
                )
                row = cursor.fetchone()

                return {
                    'session_id': session_id,
                    'status': row[0] if row else None,
                    'created_at': row[1] if row else None,
                    'started_at': row[2] if row else None,
                    'completed_at': row[3] if row else None,
                    'total_files': total_files,
                    'completed': status_counts.get(ProcessingStatus.COMPLETED.value, 0),
                    'skipped': status_counts.get(ProcessingStatus.SKIPPED.value, 0),
                    'duplicates': status_counts.get(ProcessingStatus.DUPLICATE.value, 0),
                    'errors': status_counts.get(ProcessingStatus.ERROR.value, 0)
                }

        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {}

    def can_resume_session(self, session_id: int) -> bool:
        """
        Check if session can be resumed.

        Args:
            session_id: Session ID

        Returns:
            True if session can be resumed
        """
        try:
            # Get session info
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT status, source_path, destination_path
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,)
                )
                row = cursor.fetchone()

                if not row:
                    return False

                status = row[0]
                source_path = Path(row[1])
                dest_path = Path(row[2])

                # Check status
                if status not in (SessionStatus.IN_PROGRESS.value, SessionStatus.PAUSED.value):
                    return False

                # Check paths still exist
                if not source_path.exists() or not dest_path.exists():
                    logger.warning(f"Session {session_id} paths no longer accessible")
                    return False

                return True

        except Exception as e:
            logger.error(f"Error checking if session can resume: {e}")
            return False

    def undo_session(self, session_id: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Undo a completed session by removing copied files.

        Args:
            session_id: Session ID to undo
            dry_run: If True, only simulate undo

        Returns:
            Dictionary with undo results:
            {
                'files_deleted': int,
                'files_failed': int,
                'dirs_deleted': int,
                'errors': List[str]
            }
        """
        results = {
            'files_deleted': 0,
            'files_failed': 0,
            'dirs_deleted': 0,
            'errors': []
        }

        try:
            # Get all file mappings for session
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT destination_path FROM file_mappings
                    WHERE session_id = ?
                      AND destination_path IS NOT NULL
                    ORDER BY destination_path DESC
                    """,
                    (session_id,)
                )
                dest_files = [Path(row[0]) for row in cursor.fetchall()]

            logger.info(f"Undoing session {session_id}: {len(dest_files)} files to process")

            # Delete destination files
            for dest_path in dest_files:
                try:
                    if dest_path.exists():
                        if not dry_run:
                            dest_path.unlink()
                        results['files_deleted'] += 1
                        logger.debug(f"{'Would delete' if dry_run else 'Deleted'}: {dest_path}")
                    else:
                        logger.debug(f"File already deleted: {dest_path}")
                except Exception as e:
                    results['files_failed'] += 1
                    error_msg = f"Failed to delete {dest_path}: {e}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)

            # Remove empty directories
            if not dry_run:
                dirs_to_check = set(f.parent for f in dest_files)
                for dir_path in sorted(dirs_to_check, reverse=True):
                    try:
                        if dir_path.exists() and not any(dir_path.iterdir()):
                            dir_path.rmdir()
                            results['dirs_deleted'] += 1
                            logger.debug(f"Removed empty directory: {dir_path}")
                    except Exception as e:
                        logger.debug(f"Could not remove directory {dir_path}: {e}")

            # Update session status
            if not dry_run:
                with self.db_manager.get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET status = ?
                        WHERE session_id = ?
                        """,
                        (SessionStatus.UNDONE.value, session_id)
                    )
                    conn.commit()

            logger.info(
                f"Undo {'simulation' if dry_run else 'complete'} for session {session_id}: "
                f"{results['files_deleted']} files deleted, "
                f"{results['files_failed']} failed, "
                f"{results['dirs_deleted']} dirs removed"
            )

            return results

        except Exception as e:
            error_msg = f"Failed to undo session {session_id}: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results

    def format_session_info(self, session_info: Dict[str, Any]) -> str:
        """
        Format session info as human-readable string.

        Args:
            session_info: Session info dictionary

        Returns:
            Formatted string
        """
        stats = self.get_session_statistics(session_info['session_id'])

        return (
            f"Session {session_info['session_id']}:\n"
            f"  Status: {session_info['status']}\n"
            f"  Source: {session_info['source_path']}\n"
            f"  Destination: {session_info['destination_path']}\n"
            f"  Created: {session_info['created_at']}\n"
            f"  Started: {session_info['started_at']}\n"
            f"  Files: {stats.get('total_files', 0)} total, "
            f"{stats.get('completed', 0)} completed, "
            f"{stats.get('skipped', 0)} skipped, "
            f"{stats.get('duplicates', 0)} duplicates, "
            f"{stats.get('errors', 0)} errors\n"
        )
