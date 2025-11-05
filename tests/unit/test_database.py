"""
Unit tests for database layer.

Tests database manager, schema, and models.
"""

import pytest
from pathlib import Path
from datetime import datetime
import uuid

from filearchitect.database.manager import DatabaseManager
from filearchitect.database.models import Session, FileRecord
from filearchitect.database.schema import verify_database_integrity, get_schema_version
from filearchitect.core.constants import SessionStatus, ProcessingStatus, FileType


@pytest.mark.unit
class TestDatabaseManager:
    """Test DatabaseManager class."""

    def test_database_initialization(self, temp_dir):
        """Test database initialization creates all tables."""
        db_path = temp_dir / "test.db"
        manager = DatabaseManager(db_path)

        # Trigger connection creation
        conn = manager._get_connection()

        # Check that database file exists
        assert db_path.exists()

        # Check that tables exist
        with manager.transaction() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {'sessions', 'files', 'file_mappings', 'duplicate_groups', 'cache', 'schema_version'}
        assert expected_tables.issubset(tables)

        manager.close()

    def test_singleton_pattern(self, temp_dir):
        """Test that DatabaseManager follows singleton pattern."""
        db_path = temp_dir / "test.db"

        manager1 = DatabaseManager(db_path)
        manager2 = DatabaseManager(db_path)

        assert manager1 is manager2

        manager1.close()

    def test_transaction_commit(self, db_manager):
        """Test transaction commit."""
        session_id = str(uuid.uuid4())

        with db_manager.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, source_path, destination_path, status, start_time)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, "/source", "/dest", SessionStatus.RUNNING.value, datetime.now().isoformat())
            )

        # Verify data was committed
        with db_manager.transaction() as cursor:
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,))
            count = cursor.fetchone()[0]
        assert count == 1

    def test_transaction_rollback(self, db_manager):
        """Test transaction rollback on error."""
        from filearchitect.core.exceptions import DatabaseError

        session_id = str(uuid.uuid4())

        try:
            with db_manager.transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sessions (session_id, source_path, destination_path, status, start_time)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, "/source", "/dest", SessionStatus.RUNNING.value, datetime.now().isoformat())
                )
                # Force an error
                raise ValueError("Test error")
        except DatabaseError:
            pass

        # Verify data was rolled back
        with db_manager.transaction() as cursor:
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,))
            count = cursor.fetchone()[0]
        assert count == 0


@pytest.mark.unit
class TestSessionManagement:
    """Test session database operations."""

    def test_create_session(self, db_manager):
        """Test creating a new session."""
        session = Session(
            session_id=str(uuid.uuid4()),
            source_path="/test/source",
            destination_path="/test/dest",
            status=SessionStatus.RUNNING,
            start_time=datetime.now()
        )

        db_manager.create_session(session)

        # Verify session was created
        retrieved = db_manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.source_path == "/test/source"
        assert retrieved.destination_path == "/test/dest"
        assert retrieved.status == SessionStatus.RUNNING

    def test_update_session_status(self, db_manager, session_id):
        """Test updating session status."""
        db_manager.update_session_status(session_id, SessionStatus.COMPLETED)

        # Verify update
        session = db_manager.get_session(session_id)
        assert session.status == SessionStatus.COMPLETED
        assert session.end_time is not None

    def test_session_progress(self, db_manager, session_id):
        """Test updating session progress."""
        db_manager.update_session_progress(
            session_id,
            files_scanned=100,
            files_processed=95,
            files_skipped=3,
            files_error=2
        )

        session = db_manager.get_session(session_id)
        assert session.files_scanned == 100
        assert session.files_processed == 95
        assert session.files_skipped == 3
        assert session.files_error == 2

    def test_get_incomplete_sessions(self, db_manager):
        """Test retrieving incomplete sessions."""
        # Create a running session
        running_session = Session(
            session_id=str(uuid.uuid4()),
            source_path="/test/source1",
            destination_path="/test/dest1",
            status=SessionStatus.RUNNING,
            start_time=datetime.now()
        )
        db_manager.create_session(running_session)

        # Create a paused session
        paused_session = Session(
            session_id=str(uuid.uuid4()),
            source_path="/test/source2",
            destination_path="/test/dest2",
            status=SessionStatus.PAUSED,
            start_time=datetime.now()
        )
        db_manager.create_session(paused_session)

        # Create a completed session
        completed_session = Session(
            session_id=str(uuid.uuid4()),
            source_path="/test/source3",
            destination_path="/test/dest3",
            status=SessionStatus.COMPLETED,
            start_time=datetime.now()
        )
        db_manager.create_session(completed_session)

        # Get incomplete sessions
        incomplete = db_manager.get_incomplete_sessions()

        # Should only have running and paused
        incomplete_ids = {s.session_id for s in incomplete}
        assert running_session.session_id in incomplete_ids
        assert paused_session.session_id in incomplete_ids
        assert completed_session.session_id not in incomplete_ids


@pytest.mark.unit
class TestFileRecords:
    """Test file record operations."""

    def test_insert_file_record(self, db_manager, session_id):
        """Test inserting a file record."""
        file_record = FileRecord(
            session_id=session_id,
            source_path="/test/file.jpg",
            destination_path="/dest/2023/11/file.jpg",
            file_hash="abc123",
            file_size=1024,
            file_type=FileType.IMAGE,
            file_extension=".jpg",
            status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now()
        )

        file_id = db_manager.insert_file(file_record)
        assert file_id > 0

    def test_check_duplicate(self, db_manager, session_id):
        """Test duplicate detection."""
        test_hash = "test_hash_123"

        # Insert first file
        file1 = FileRecord(
            session_id=session_id,
            source_path="/test/file1.jpg",
            destination_path="/dest/file1.jpg",
            file_hash=test_hash,
            file_size=1024,
            file_type=FileType.IMAGE,
            file_extension=".jpg",
            status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now()
        )
        file1_id = db_manager.insert_file(file1)

        # Check duplicate
        duplicate_id = db_manager.check_duplicate(test_hash, ".jpg")
        assert duplicate_id == file1_id

    def test_get_files_by_session(self, db_manager, session_id):
        """Test retrieving files by session."""
        # Insert multiple files
        for i in range(3):
            file_record = FileRecord(
                session_id=session_id,
                source_path=f"/test/file{i}.jpg",
                destination_path=f"/dest/file{i}.jpg",
                file_hash=f"hash{i}",
                file_size=1024 * i,
                file_type=FileType.IMAGE,
                file_extension=".jpg",
                status=ProcessingStatus.COMPLETED,
                processed_at=datetime.now()
            )
            db_manager.insert_file(file_record)

        # Get all files
        files = db_manager.get_files_by_session(session_id)
        assert len(files) == 3

        # Get files by status
        completed_files = db_manager.get_files_by_session(session_id, ProcessingStatus.COMPLETED)
        assert len(completed_files) == 3


@pytest.mark.unit
class TestDatabaseSchema:
    """Test database schema functions."""

    def test_verify_database_integrity(self, temp_dir):
        """Test database integrity verification."""
        # Create a fresh database for integrity check
        db_path = temp_dir / "test_integrity.db"
        manager = DatabaseManager(db_path)

        # Initialize database
        manager._get_connection()

        # Close it before integrity check
        manager.close()

        # Should return True for valid database
        result = verify_database_integrity(db_path)
        assert result is True

    def test_schema_version(self, temp_dir):
        """Test schema version tracking."""
        db_path = temp_dir / "test_version.db"
        manager = DatabaseManager(db_path)

        # Trigger database creation
        manager._get_connection()

        version = get_schema_version(db_path)
        assert version >= 1

        manager.close()


@pytest.mark.unit
class TestCacheMethods:
    """Test hash caching functionality."""

    def test_cache_file_hash(self, db_manager):
        """Test caching file hash."""
        file_path = "/test/file.jpg"
        file_hash = "abc123"
        file_size = 1024
        file_mtime = 1234567890.0

        # Cache the hash
        db_manager.cache_file_hash(file_path, file_hash, file_size, file_mtime)

        # Retrieve cached hash
        cached = db_manager.get_cached_hash(file_path, file_mtime)
        assert cached == file_hash

    def test_cache_invalidation(self, db_manager):
        """Test that cache is invalidated when mtime changes."""
        file_path = "/test/file.jpg"
        file_hash = "abc123"
        file_size = 1024
        file_mtime = 1234567890.0

        # Cache the hash
        db_manager.cache_file_hash(file_path, file_hash, file_size, file_mtime)

        # Try to get with different mtime
        cached = db_manager.get_cached_hash(file_path, file_mtime + 100)
        assert cached is None
