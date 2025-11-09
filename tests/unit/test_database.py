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

    def test_cache_multiple_files(self, db_manager):
        """Test caching multiple file hashes."""
        files = [
            ("/test/file1.jpg", "hash1", 1024, 1000.0),
            ("/test/file2.png", "hash2", 2048, 2000.0),
            ("/test/file3.mp4", "hash3", 4096, 3000.0),
        ]

        # Cache all files
        for path, hash_val, size, mtime in files:
            db_manager.cache_file_hash(path, hash_val, size, mtime)

        # Verify all can be retrieved
        for path, expected_hash, size, mtime in files:
            cached = db_manager.get_cached_hash(path, mtime)
            assert cached == expected_hash

    def test_cache_update(self, db_manager):
        """Test updating cached hash."""
        file_path = "/test/file.jpg"

        # Cache initial hash
        db_manager.cache_file_hash(file_path, "hash1", 1024, 1000.0)

        # Update with new hash (file modified)
        db_manager.cache_file_hash(file_path, "hash2", 2048, 2000.0)

        # Should get new hash with new mtime
        cached = db_manager.get_cached_hash(file_path, 2000.0)
        assert cached == "hash2"


@pytest.mark.unit
class TestSessionOperations:
    """Test additional session operations."""

    def test_list_incomplete_sessions(self, db_manager):
        """Test listing incomplete sessions."""
        # Create multiple sessions with different statuses
        running_sessions = []
        for i in range(5):
            session = Session(
                session_id=str(uuid.uuid4()),
                source_path=f"/test/source{i}",
                destination_path=f"/test/dest{i}",
                status=SessionStatus.RUNNING if i < 3 else SessionStatus.COMPLETED,
                start_time=datetime.now()
            )
            db_manager.create_session(session)
            if i < 3:
                running_sessions.append(session.session_id)

        # Get incomplete sessions
        incomplete = db_manager.get_incomplete_sessions()
        assert len(incomplete) >= 3
        incomplete_ids = [s.session_id for s in incomplete]
        for sid in running_sessions:
            assert sid in incomplete_ids

    def test_session_retrieval(self, db_manager, session_id):
        """Test retrieving session by ID."""
        # Verify session exists
        session = db_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id

        # Try to get non-existent session
        fake_id = str(uuid.uuid4())
        non_existent = db_manager.get_session(fake_id)
        assert non_existent is None

    def test_session_with_statistics(self, db_manager, session_id):
        """Test session statistics tracking."""
        # Update with various statistics
        db_manager.update_session_progress(
            session_id,
            files_scanned=500,
            files_processed=450,
            files_skipped=30,
            files_error=20,
            bytes_processed=1024 * 1024 * 100  # 100 MB
        )

        session = db_manager.get_session(session_id)
        assert session.files_scanned == 500
        assert session.files_processed == 450
        assert session.files_skipped == 30
        assert session.files_error == 20
        assert session.bytes_processed == 1024 * 1024 * 100

    def test_session_timing(self, db_manager):
        """Test session timing fields."""
        import time

        session = Session(
            session_id=str(uuid.uuid4()),
            source_path="/test/source",
            destination_path="/test/dest",
            status=SessionStatus.RUNNING,
            start_time=datetime.now()
        )
        db_manager.create_session(session)

        # Small delay
        time.sleep(0.1)

        # Complete session
        db_manager.update_session_status(session.session_id, SessionStatus.COMPLETED)

        # Get updated session
        updated = db_manager.get_session(session.session_id)
        assert updated.end_time is not None
        assert updated.end_time > updated.start_time


@pytest.mark.unit
class TestFileOperations:
    """Test additional file record operations."""

    def test_insert_multiple_files(self, db_manager, session_id):
        """Test inserting multiple file records."""
        # Create multiple file records
        file_hashes = []
        for i in range(3):
            file_record = FileRecord(
                session_id=session_id,
                source_path=f"/test/source{i}.jpg",
                destination_path=f"/test/dest{i}.jpg",
                file_hash=f"hash{i}",
                file_size=1024 * (i + 1),
                file_type=FileType.IMAGE,
                file_extension=".jpg",
                status=ProcessingStatus.COMPLETED,
                processed_at=datetime.now()
            )
            file_id = db_manager.insert_file(file_record)
            assert file_id > 0
            file_hashes.append(f"hash{i}")

        # Verify all files were inserted
        files = db_manager.get_files_by_session(session_id)
        assert len(files) >= 3
        retrieved_hashes = [f.file_hash for f in files]
        for hash_val in file_hashes:
            assert hash_val in retrieved_hashes

    def test_get_files_by_type(self, db_manager, session_id):
        """Test retrieving files by type."""
        # Insert various file types
        types_to_create = [
            (FileType.IMAGE, ".jpg"),
            (FileType.IMAGE, ".png"),
            (FileType.VIDEO, ".mp4"),
            (FileType.AUDIO, ".mp3"),
            (FileType.DOCUMENT, ".pdf"),
        ]

        for file_type, ext in types_to_create:
            file_record = FileRecord(
                session_id=session_id,
                source_path=f"/test/file{ext}",
                destination_path=f"/dest/file{ext}",
                file_hash=f"hash{ext}",
                file_size=1024,
                file_type=file_type,
                file_extension=ext,
                status=ProcessingStatus.COMPLETED,
                processed_at=datetime.now()
            )
            db_manager.insert_file(file_record)

        # Get all files and filter by type
        all_files = db_manager.get_files_by_session(session_id)
        image_files = [f for f in all_files if f.file_type == FileType.IMAGE]
        video_files = [f for f in all_files if f.file_type == FileType.VIDEO]

        assert len(image_files) == 2  # jpg and png
        assert len(video_files) == 1  # mp4

    def test_get_duplicate_files(self, db_manager, session_id):
        """Test finding duplicate files."""
        shared_hash = "duplicate_hash_123"

        # Insert duplicate files
        for i in range(3):
            file_record = FileRecord(
                session_id=session_id,
                source_path=f"/test/duplicate{i}.jpg",
                destination_path=f"/dest/duplicate{i}.jpg",
                file_hash=shared_hash,
                file_size=1024,
                file_type=FileType.IMAGE,
                file_extension=".jpg",
                status=ProcessingStatus.COMPLETED,
                processed_at=datetime.now()
            )
            db_manager.insert_file(file_record)

        # Check for duplicates
        duplicate_id = db_manager.check_duplicate(shared_hash, ".jpg")
        assert duplicate_id is not None


@pytest.mark.unit
class TestDatabaseErrors:
    """Test database error handling."""

    def test_get_nonexistent_session(self, db_manager):
        """Test getting a non-existent session."""
        session = db_manager.get_session("nonexistent_id")
        assert session is None

    def test_invalid_session_id_format(self, db_manager):
        """Test handling invalid session ID."""
        # Try to get session with various invalid IDs
        for invalid_id in [None, "", "   "]:
            session = db_manager.get_session(invalid_id)
            assert session is None or session == invalid_id  # Depends on implementation

    def test_concurrent_transactions(self, db_manager):
        """Test that concurrent transactions work correctly."""
        session_id1 = str(uuid.uuid4())
        session_id2 = str(uuid.uuid4())

        # Create two sessions
        with db_manager.transaction() as cursor:
            cursor.execute(
                """INSERT INTO sessions (session_id, source_path, destination_path, status, start_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id1, "/src1", "/dst1", SessionStatus.RUNNING.value, datetime.now().isoformat())
            )

        with db_manager.transaction() as cursor:
            cursor.execute(
                """INSERT INTO sessions (session_id, source_path, destination_path, status, start_time)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id2, "/src2", "/dst2", SessionStatus.RUNNING.value, datetime.now().isoformat())
            )

        # Verify both exist
        assert db_manager.get_session(session_id1) is not None
        assert db_manager.get_session(session_id2) is not None


@pytest.mark.unit
class TestDatabaseMaintenance:
    """Test database maintenance operations."""

    def test_query_incomplete_sessions(self, db_manager):
        """Test querying incomplete sessions for maintenance."""
        # Create a mix of sessions
        for i in range(3):
            session = Session(
                session_id=str(uuid.uuid4()),
                source_path=f"/test/source{i}",
                destination_path=f"/test/dest{i}",
                status=SessionStatus.RUNNING if i < 2 else SessionStatus.COMPLETED,
                start_time=datetime.now()
            )
            db_manager.create_session(session)

        # Query incomplete sessions
        incomplete = db_manager.get_incomplete_sessions()
        assert isinstance(incomplete, list)
        assert len(incomplete) >= 2

    def test_database_size(self, temp_dir):
        """Test checking database file size."""
        db_path = temp_dir / "test.db"
        manager = DatabaseManager(db_path)

        # Trigger database creation
        manager._get_connection()

        # Check file exists and has size
        assert db_path.exists()
        assert db_path.stat().st_size > 0

        manager.close()

    def test_vacuum_database(self, db_manager):
        """Test database vacuum operation."""
        # Execute vacuum if the method exists
        with db_manager.transaction() as cursor:
            cursor.execute("VACUUM")

        # Should complete without error
        assert True
