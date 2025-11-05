"""
Database layer for FileArchitect.

This module handles all database operations including schema creation,
file tracking, session management, and deduplication.
"""

from filearchitect.database.manager import DatabaseManager
from filearchitect.database.models import (
    Session,
    FileRecord,
    FileMapping,
    DuplicateGroup,
    CacheEntry,
    SessionStatistics,
    DuplicateInfo
)
from filearchitect.database.schema import (
    initialize_database,
    get_schema_version,
    verify_database_integrity,
    vacuum_database
)

__all__ = [
    "DatabaseManager",
    "Session",
    "FileRecord",
    "FileMapping",
    "DuplicateGroup",
    "CacheEntry",
    "SessionStatistics",
    "DuplicateInfo",
    "initialize_database",
    "get_schema_version",
    "verify_database_integrity",
    "vacuum_database",
]
