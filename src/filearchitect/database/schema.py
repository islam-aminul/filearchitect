"""
Database schema definitions for FileArchitect.

This module defines the SQLite database schema including tables, indexes,
and initialization/migration logic.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from ..core.exceptions import DatabaseError
from ..core.constants import DATABASE_NAME


# Current schema version
SCHEMA_VERSION = 1

# SQL statements for creating tables
CREATE_TABLES = [
    # Schema version table for migrations
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT
    )
    """,

    # Sessions table for tracking organization sessions
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        source_path TEXT NOT NULL,
        destination_path TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        files_scanned INTEGER DEFAULT 0,
        files_processed INTEGER DEFAULT 0,
        files_skipped INTEGER DEFAULT 0,
        files_error INTEGER DEFAULT 0,
        duplicates_found INTEGER DEFAULT 0,
        bytes_processed INTEGER DEFAULT 0,
        bytes_total INTEGER DEFAULT 0,
        config_snapshot TEXT,
        error_message TEXT
    )
    """,

    # Files table for tracking all processed files
    """
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        destination_path TEXT,
        file_hash TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        file_type TEXT NOT NULL,
        file_extension TEXT NOT NULL,
        status TEXT NOT NULL,
        category TEXT,
        date_taken TIMESTAMP,
        date_source TEXT,
        camera_make TEXT,
        camera_model TEXT,
        metadata_json TEXT,
        error_message TEXT,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """,

    # File mappings table for undo functionality
    """
    CREATE TABLE IF NOT EXISTS file_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        source_path TEXT NOT NULL,
        destination_path TEXT NOT NULL,
        operation TEXT NOT NULL,
        file_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )
    """,

    # Duplicate groups table for tracking duplicates
    """
    CREATE TABLE IF NOT EXISTS duplicate_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT NOT NULL,
        file_extension TEXT NOT NULL,
        original_file_id INTEGER,
        duplicate_count INTEGER DEFAULT 0,
        first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (original_file_id) REFERENCES files(id)
    )
    """,

    # Cache table for file hashes and metadata
    """
    CREATE TABLE IF NOT EXISTS cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE NOT NULL,
        file_hash TEXT,
        file_size INTEGER,
        file_mtime REAL,
        metadata_json TEXT,
        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

# SQL statements for creating indexes
CREATE_INDEXES = [
    # Files table indexes
    "CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_files_source_path ON files(source_path)",
    "CREATE INDEX IF NOT EXISTS idx_files_session_id ON files(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_files_status ON files(status)",
    "CREATE INDEX IF NOT EXISTS idx_files_hash_ext ON files(file_hash, file_extension)",
    "CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type)",
    "CREATE INDEX IF NOT EXISTS idx_files_category ON files(category)",
    "CREATE INDEX IF NOT EXISTS idx_files_date_taken ON files(date_taken)",

    # Sessions table indexes
    "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source_path)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time)",

    # File mappings table indexes
    "CREATE INDEX IF NOT EXISTS idx_file_mappings_session ON file_mappings(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_file_mappings_source ON file_mappings(source_path)",
    "CREATE INDEX IF NOT EXISTS idx_file_mappings_destination ON file_mappings(destination_path)",

    # Duplicate groups table indexes
    "CREATE INDEX IF NOT EXISTS idx_duplicate_groups_hash ON duplicate_groups(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_duplicate_groups_hash_ext ON duplicate_groups(file_hash, file_extension)",

    # Cache table indexes
    "CREATE INDEX IF NOT EXISTS idx_cache_path ON cache(file_path)",
    "CREATE INDEX IF NOT EXISTS idx_cache_hash ON cache(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_cache_mtime ON cache(file_mtime)",
]


def initialize_database(db_path: Path) -> None:
    """
    Initialize the database with schema and indexes.

    Args:
        db_path: Path to SQLite database file

    Raises:
        DatabaseError: If initialization fails

    Examples:
        >>> initialize_database(Path("/path/to/database.db"))
    """
    try:
        # Ensure database directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        conn.execute("PRAGMA journal_mode = WAL")  # Use Write-Ahead Logging for better concurrency

        cursor = conn.cursor()

        # Create tables
        for create_statement in CREATE_TABLES:
            cursor.execute(create_statement)

        # Create indexes
        for index_statement in CREATE_INDEXES:
            cursor.execute(index_statement)

        # Insert or update schema version
        cursor.execute(
            """
            INSERT OR REPLACE INTO schema_version (version, description)
            VALUES (?, ?)
            """,
            (SCHEMA_VERSION, f"Schema version {SCHEMA_VERSION}")
        )

        conn.commit()
        conn.close()

    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to initialize database: {e}") from e


def get_schema_version(db_path: Path) -> Optional[int]:
    """
    Get the current schema version from the database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Current schema version, or None if not initialized

    Examples:
        >>> version = get_schema_version(Path("/path/to/database.db"))
        >>> print(f"Schema version: {version}")
    """
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()

        conn.close()

        return result[0] if result and result[0] is not None else None

    except sqlite3.Error:
        return None


def migrate_database(db_path: Path, target_version: Optional[int] = None) -> None:
    """
    Migrate database to target version.

    Args:
        db_path: Path to SQLite database file
        target_version: Target schema version (default: latest)

    Raises:
        DatabaseError: If migration fails

    Examples:
        >>> migrate_database(Path("/path/to/database.db"))
    """
    if target_version is None:
        target_version = SCHEMA_VERSION

    current_version = get_schema_version(db_path)

    if current_version is None:
        # Database not initialized, do full initialization
        initialize_database(db_path)
        return

    if current_version >= target_version:
        # Already at or above target version
        return

    # Apply migrations
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Migration logic for future versions
        # Example:
        # if current_version < 2:
        #     apply_migration_v2(cursor)
        #     cursor.execute("INSERT INTO schema_version (version, description) VALUES (2, 'Migration to v2')")
        #     conn.commit()
        #     current_version = 2

        conn.close()

    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to migrate database: {e}") from e


def verify_database_integrity(db_path: Path) -> bool:
    """
    Verify database integrity.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if database is valid, False otherwise

    Examples:
        >>> if verify_database_integrity(Path("/path/to/database.db")):
        ...     print("Database is valid")
    """
    if not db_path.exists():
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()

        conn.close()

        return result and result[0] == "ok"

    except sqlite3.Error:
        return False


def vacuum_database(db_path: Path) -> None:
    """
    Vacuum database to reclaim space and optimize performance.

    Args:
        db_path: Path to SQLite database file

    Raises:
        DatabaseError: If vacuum fails

    Examples:
        >>> vacuum_database(Path("/path/to/database.db"))
    """
    if not db_path.exists():
        return

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("VACUUM")
        conn.close()

    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to vacuum database: {e}") from e


def get_database_size(db_path: Path) -> int:
    """
    Get database file size in bytes.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Database size in bytes, or 0 if not exists

    Examples:
        >>> size = get_database_size(Path("/path/to/database.db"))
        >>> print(f"Database size: {size / (1024**2):.2f} MB")
    """
    if not db_path.exists():
        return 0

    return db_path.stat().st_size


def clear_old_cache_entries(db_path: Path, days: int = 30) -> int:
    """
    Clear cache entries older than specified days.

    Args:
        db_path: Path to SQLite database file
        days: Number of days to keep (default: 30)

    Returns:
        Number of entries deleted

    Raises:
        DatabaseError: If deletion fails

    Examples:
        >>> deleted = clear_old_cache_entries(Path("/path/to/database.db"), days=7)
        >>> print(f"Deleted {deleted} old cache entries")
    """
    if not db_path.exists():
        return 0

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM cache
            WHERE last_accessed < datetime('now', '-' || ? || ' days')
            """,
            (days,)
        )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        return deleted_count

    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to clear cache entries: {e}") from e
