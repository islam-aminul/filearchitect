"""
Custom exception classes for FileArchitect.

This module defines the exception hierarchy used throughout the application
to provide clear, specific error handling.
"""


class FileArchitectError(Exception):
    """Base exception for all FileArchitect errors."""

    pass


class FileAccessError(FileArchitectError):
    """Raised when a file cannot be accessed due to permissions or locks."""

    pass


class FileCorruptedError(FileArchitectError):
    """Raised when a file is corrupted or cannot be read properly."""

    pass


class MetadataError(FileArchitectError):
    """Raised when metadata extraction or processing fails."""

    pass


class DiskSpaceError(FileArchitectError):
    """Raised when there is insufficient disk space."""

    pass


class InsufficientSpaceError(DiskSpaceError):
    """Raised when there is insufficient disk space for operation."""

    pass


class DatabaseError(FileArchitectError):
    """Raised when database operations fail."""

    pass


class ConfigurationError(FileArchitectError):
    """Raised when configuration is invalid or cannot be loaded."""

    pass


class ProcessingError(FileArchitectError):
    """Raised when file processing fails."""

    pass


class ValidationError(FileArchitectError):
    """Raised when input validation fails."""

    pass


class NetworkError(FileArchitectError):
    """Raised when network operations fail (e.g., metadata lookup)."""

    pass


class PipelineError(FileArchitectError):
    """Raised when processing pipeline encounters an error."""

    pass


class OrchestratorError(FileArchitectError):
    """Raised when orchestrator encounters an error."""

    pass
