"""
Database manager for FileArchitect.

This module provides the database connection manager and query methods.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Tuple
from contextlib import contextmanager
from datetime import datetime

from ..core.exceptions import DatabaseError
from ..core.constants import FileType, ProcessingStatus, SessionStatus, DateSource, DATABASE_TIMEOUT
from .models import (
    Session, FileRecord, FileMapping, DuplicateGroup,
    CacheEntry, SessionStatistics, DuplicateInfo
)
from .schema import initialize_database, get_schema_version, SCHEMA_VERSION


class DatabaseManager:
    """
    Database manager with connection pooling and query methods.

    This class implements the singleton pattern to ensure only one database
    connection is active at a time.
    """

    _instance: Optional['DatabaseManager'] = None
    _db_path: Optional[Path] = None
    _connection: Optional[sqlite3.Connection] = None

    def __new__(cls, db_path: Optional[Path] = None):
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to database file
        """
        if db_path and self._db_path != db_path:
            self._db_path = db_path
            self._close_connection()

    @classmethod
    def get_instance(cls, db_path: Optional[Path] = None) -> 'DatabaseManager':
        """
        Get the singleton instance of DatabaseManager.

        Args:
            db_path: Optional path to database file

        Returns:
            DatabaseManager instance
        """
        if cls._instance is None or (db_path and cls._db_path != db_path):
            cls._instance = cls(db_path)
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection, creating if necessary.

        Returns:
            SQLite connection object
        """
        if self._connection is None:
            if self._db_path is None:
                raise DatabaseError("Database path not set")

            # Initialize database if needed
            if not self._db_path.exists():
                initialize_database(self._db_path)
            else:
                # Verify schema version
                current_version = get_schema_version(self._db_path)
                if current_version != SCHEMA_VERSION:
                    raise DatabaseError(
                        f"Database schema version mismatch. Expected {SCHEMA_VERSION}, got {current_version}"
                    )

            # Create connection
            self._connection = sqlite3.connect(
                str(self._db_path),
                timeout=DATABASE_TIMEOUT,
                check_same_thread=False
            )
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.row_factory = sqlite3.Row

        return self._connection

    def _close_connection(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.

        Yields:
            Database cursor

        Example:
            >>> with db_manager.transaction() as cursor:
            ...     cursor.execute("INSERT ...")
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseError(f"Transaction failed: {e}") from e

    # Session methods

    def create_session(self, session: Session) -> None:
        """
        Create a new session record.

        Args:
            session: Session object

        Raises:
            DatabaseError: If creation fails
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (
                    session_id, source_path, destination_path, status,
                    start_time, config_snapshot
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.source_path,
                    session.destination_path,
                    session.status.value,
                    session.start_time.isoformat(),
                    session.config_snapshot
                )
            )

    def update_session_status(self, session_id: str, status: SessionStatus, error_message: Optional[str] = None) -> None:
        """
        Update session status.

        Args:
            session_id: Session identifier
            status: New status
            error_message: Optional error message
        """
        with self.transaction() as cursor:
            if status in (SessionStatus.COMPLETED, SessionStatus.STOPPED, SessionStatus.ERROR):
                cursor.execute(
                    """
                    UPDATE sessions
                    SET status = ?, end_time = ?, error_message = ?
                    WHERE session_id = ?
                    """,
                    (status.value, datetime.now().isoformat(), error_message, session_id)
                )
            else:
                cursor.execute(
                    """
                    UPDATE sessions
                    SET status = ?
                    WHERE session_id = ?
                    """,
                    (status.value, session_id)
                )

    def update_session_progress(
        self,
        session_id: str,
        files_scanned: Optional[int] = None,
        files_processed: Optional[int] = None,
        files_skipped: Optional[int] = None,
        files_error: Optional[int] = None,
        duplicates_found: Optional[int] = None,
        bytes_processed: Optional[int] = None,
        bytes_total: Optional[int] = None
    ) -> None:
        """
        Update session progress counters.

        Args:
            session_id: Session identifier
            files_scanned: Number of files scanned
            files_processed: Number of files processed
            files_skipped: Number of files skipped
            files_error: Number of files with errors
            duplicates_found: Number of duplicates found
            bytes_processed: Bytes processed
            bytes_total: Total bytes
        """
        updates = []
        values = []

        if files_scanned is not None:
            updates.append("files_scanned = ?")
            values.append(files_scanned)
        if files_processed is not None:
            updates.append("files_processed = ?")
            values.append(files_processed)
        if files_skipped is not None:
            updates.append("files_skipped = ?")
            values.append(files_skipped)
        if files_error is not None:
            updates.append("files_error = ?")
            values.append(files_error)
        if duplicates_found is not None:
            updates.append("duplicates_found = ?")
            values.append(duplicates_found)
        if bytes_processed is not None:
            updates.append("bytes_processed = ?")
            values.append(bytes_processed)
        if bytes_total is not None:
            updates.append("bytes_total = ?")
            values.append(bytes_total)

        if not updates:
            return

        values.append(session_id)

        with self.transaction() as cursor:
            cursor.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?",
                values
            )

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return Session(
            session_id=row['session_id'],
            source_path=row['source_path'],
            destination_path=row['destination_path'],
            status=SessionStatus(row['status']),
            start_time=datetime.fromisoformat(row['start_time']),
            end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
            files_scanned=row['files_scanned'],
            files_processed=row['files_processed'],
            files_skipped=row['files_skipped'],
            files_error=row['files_error'],
            duplicates_found=row['duplicates_found'],
            bytes_processed=row['bytes_processed'],
            bytes_total=row['bytes_total'],
            config_snapshot=row['config_snapshot'],
            error_message=row['error_message']
        )

    def get_incomplete_sessions(self) -> List[Session]:
        """
        Get all incomplete sessions.

        Returns:
            List of incomplete sessions
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM sessions
            WHERE status IN (?, ?)
            ORDER BY start_time DESC
            """,
            (SessionStatus.RUNNING.value, SessionStatus.PAUSED.value)
        )

        sessions = []
        for row in cursor.fetchall():
            sessions.append(Session(
                session_id=row['session_id'],
                source_path=row['source_path'],
                destination_path=row['destination_path'],
                status=SessionStatus(row['status']),
                start_time=datetime.fromisoformat(row['start_time']),
                end_time=datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                files_scanned=row['files_scanned'],
                files_processed=row['files_processed'],
                files_skipped=row['files_skipped'],
                files_error=row['files_error'],
                duplicates_found=row['duplicates_found'],
                bytes_processed=row['bytes_processed'],
                bytes_total=row['bytes_total'],
                config_snapshot=row['config_snapshot'],
                error_message=row['error_message']
            ))

        return sessions

    # File methods

    def insert_file(self, file_record: FileRecord) -> int:
        """
        Insert a file record.

        Args:
            file_record: FileRecord object

        Returns:
            Inserted file ID

        Raises:
            DatabaseError: If insertion fails
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO files (
                    session_id, source_path, destination_path, file_hash,
                    file_size, file_type, file_extension, status, category,
                    date_taken, date_source, camera_make, camera_model,
                    metadata_json, error_message, processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_record.session_id,
                    file_record.source_path,
                    file_record.destination_path,
                    file_record.file_hash,
                    file_record.file_size,
                    file_record.file_type.value,
                    file_record.file_extension,
                    file_record.status.value,
                    file_record.category,
                    file_record.date_taken.isoformat() if file_record.date_taken else None,
                    file_record.date_source.value if file_record.date_source else None,
                    file_record.camera_make,
                    file_record.camera_model,
                    file_record.metadata_json,
                    file_record.error_message,
                    file_record.processed_at.isoformat()
                )
            )
            return cursor.lastrowid

    def check_duplicate(self, file_hash: str, file_extension: str) -> Optional[int]:
        """
        Check if file is a duplicate based on hash and extension category.

        Args:
            file_hash: File hash
            file_extension: File extension

        Returns:
            ID of original file if duplicate, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id FROM files
            WHERE file_hash = ? AND file_extension = ? AND status = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (file_hash, file_extension, ProcessingStatus.COMPLETED.value)
        )

        row = cursor.fetchone()
        return row['id'] if row else None

    def get_files_by_session(self, session_id: str, status: Optional[ProcessingStatus] = None) -> List[FileRecord]:
        """
        Get files by session ID.

        Args:
            session_id: Session identifier
            status: Optional status filter

        Returns:
            List of file records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                "SELECT * FROM files WHERE session_id = ? AND status = ?",
                (session_id, status.value)
            )
        else:
            cursor.execute(
                "SELECT * FROM files WHERE session_id = ?",
                (session_id,)
            )

        files = []
        for row in cursor.fetchall():
            files.append(self._row_to_file_record(row))

        return files

    def _row_to_file_record(self, row: sqlite3.Row) -> FileRecord:
        """Convert database row to FileRecord object."""
        return FileRecord(
            id=row['id'],
            session_id=row['session_id'],
            source_path=row['source_path'],
            destination_path=row['destination_path'],
            file_hash=row['file_hash'],
            file_size=row['file_size'],
            file_type=FileType(row['file_type']),
            file_extension=row['file_extension'],
            status=ProcessingStatus(row['status']),
            category=row['category'],
            date_taken=datetime.fromisoformat(row['date_taken']) if row['date_taken'] else None,
            date_source=DateSource(row['date_source']) if row['date_source'] else None,
            camera_make=row['camera_make'],
            camera_model=row['camera_model'],
            metadata_json=row['metadata_json'],
            error_message=row['error_message'],
            processed_at=datetime.fromisoformat(row['processed_at'])
        )

    # File mapping methods (for undo)

    def insert_file_mapping(self, mapping: FileMapping) -> int:
        """
        Insert a file mapping for undo functionality.

        Args:
            mapping: FileMapping object

        Returns:
            Inserted mapping ID
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO file_mappings (
                    session_id, source_path, destination_path, operation, file_hash
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    mapping.session_id,
                    mapping.source_path,
                    mapping.destination_path,
                    mapping.operation,
                    mapping.file_hash
                )
            )
            return cursor.lastrowid

    def get_file_mappings(self, session_id: str) -> List[FileMapping]:
        """
        Get file mappings for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of file mappings
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM file_mappings WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        )

        mappings = []
        for row in cursor.fetchall():
            mappings.append(FileMapping(
                id=row['id'],
                session_id=row['session_id'],
                source_path=row['source_path'],
                destination_path=row['destination_path'],
                operation=row['operation'],
                file_hash=row['file_hash'],
                created_at=datetime.fromisoformat(row['created_at'])
            ))

        return mappings

    # Duplicate group methods

    def create_or_update_duplicate_group(
        self,
        file_hash: str,
        file_extension: str,
        original_file_id: Optional[int] = None
    ) -> int:
        """
        Create or update duplicate group.

        Args:
            file_hash: File hash
            file_extension: File extension
            original_file_id: ID of original file

        Returns:
            Duplicate group ID
        """
        with self.transaction() as cursor:
            # Check if group exists
            cursor.execute(
                "SELECT id, duplicate_count FROM duplicate_groups WHERE file_hash = ? AND file_extension = ?",
                (file_hash, file_extension)
            )
            row = cursor.fetchone()

            if row:
                # Update existing group
                group_id = row['id']
                new_count = row['duplicate_count'] + 1
                cursor.execute(
                    """
                    UPDATE duplicate_groups
                    SET duplicate_count = ?, last_seen_at = ?
                    WHERE id = ?
                    """,
                    (new_count, datetime.now().isoformat(), group_id)
                )
            else:
                # Create new group
                cursor.execute(
                    """
                    INSERT INTO duplicate_groups (
                        file_hash, file_extension, original_file_id, duplicate_count
                    )
                    VALUES (?, ?, ?, 1)
                    """,
                    (file_hash, file_extension, original_file_id)
                )
                group_id = cursor.lastrowid

            return group_id

    # Cache methods

    def get_cached_hash(self, file_path: str, file_mtime: float) -> Optional[str]:
        """
        Get cached file hash if still valid.

        Args:
            file_path: File path
            file_mtime: File modification time

        Returns:
            Cached hash if valid, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT file_hash, file_mtime FROM cache WHERE file_path = ?",
            (file_path,)
        )

        row = cursor.fetchone()
        if row and row['file_mtime'] == file_mtime:
            # Update last accessed time
            with self.transaction() as update_cursor:
                update_cursor.execute(
                    "UPDATE cache SET last_accessed = ? WHERE file_path = ?",
                    (datetime.now().isoformat(), file_path)
                )
            return row['file_hash']

        return None

    def cache_file_hash(self, file_path: str, file_hash: str, file_size: int, file_mtime: float) -> None:
        """
        Cache file hash.

        Args:
            file_path: File path
            file_hash: File hash
            file_size: File size
            file_mtime: File modification time
        """
        with self.transaction() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache (
                    file_path, file_hash, file_size, file_mtime, cached_at, last_accessed
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file_path,
                    file_hash,
                    file_size,
                    file_mtime,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                )
            )

    def close(self) -> None:
        """Close database connection."""
        self._close_connection()
