"""
Unit tests for utility functions.

This module tests path utilities, hash calculation, and other helper functions.
"""

import pytest
from pathlib import Path

from filearchitect.utils.path import sanitize_filename, resolve_conflict
from filearchitect.utils.hash import calculate_file_hash


class TestPathUtils:
    """Test path utility functions."""

    def test_sanitize_filename_removes_invalid_chars(self):
        """Test that invalid characters are removed from filenames."""
        assert sanitize_filename('file<>:"/\\|?*.txt') == "file_________.txt"

    def test_sanitize_filename_handles_empty(self):
        """Test that empty filenames are handled."""
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename("...") == "unnamed"

    def test_sanitize_filename_preserves_valid(self):
        """Test that valid filenames are preserved."""
        assert sanitize_filename("valid_file-123.txt") == "valid_file-123.txt"

    def test_resolve_conflict_no_conflict(self, temp_dir):
        """Test that non-conflicting paths are returned unchanged."""
        path = temp_dir / "file.txt"
        assert resolve_conflict(path) == path

    def test_resolve_conflict_with_conflict(self, temp_dir):
        """Test that conflicts are resolved with sequence numbers."""
        path = temp_dir / "file.txt"
        path.touch()

        new_path = resolve_conflict(path)
        assert new_path == temp_dir / "file--1.txt"

        new_path.touch()
        newer_path = resolve_conflict(path)
        assert newer_path == temp_dir / "file--2.txt"


class TestHashUtils:
    """Test file hashing functions."""

    def test_calculate_file_hash(self, sample_image_path):
        """Test that file hash is calculated correctly."""
        hash1 = calculate_file_hash(sample_image_path)
        hash2 = calculate_file_hash(sample_image_path)

        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_calculate_file_hash_nonexistent(self, temp_dir):
        """Test that nonexistent files raise FileNotFoundError."""
        nonexistent = temp_dir / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            calculate_file_hash(nonexistent)
