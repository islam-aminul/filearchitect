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


class TestFilesystemUtils:
    """Test filesystem utility functions."""

    def test_copy_file_streaming(self, temp_dir):
        """Test streaming file copy."""
        from filearchitect.utils.filesystem import copy_file_streaming

        source = temp_dir / "source.txt"
        source.write_text("Test content" * 1000)
        dest = temp_dir / "dest.txt"

        copy_file_streaming(source, dest)

        assert dest.exists()
        assert dest.read_text() == source.read_text()

    def test_safe_delete_file(self, temp_dir):
        """Test safe file deletion."""
        from filearchitect.utils.filesystem import safe_delete_file

        test_file = temp_dir / "delete_me.txt"
        test_file.write_text("Delete this")

        assert test_file.exists()
        safe_delete_file(test_file)
        assert not test_file.exists()

    def test_calculate_directory_size(self, temp_dir):
        """Test directory size calculation."""
        from filearchitect.utils.filesystem import calculate_directory_size

        # Create some files
        (temp_dir / "file1.txt").write_text("a" * 100)
        (temp_dir / "file2.txt").write_text("b" * 200)

        size = calculate_directory_size(temp_dir)
        assert size >= 300  # At least 300 bytes


class TestDatetimeUtils:
    """Test datetime utility functions."""

    def test_parse_filename_date(self):
        """Test date parsing from filenames."""
        from filearchitect.utils.datetime import parse_filename_date

        # Test various patterns
        assert parse_filename_date("IMG_20231115_143052.jpg") is not None
        assert parse_filename_date("Screenshot_2023-11-15.png") is not None
        assert parse_filename_date("VID-20231115-WA0001.mp4") is not None

    def test_format_datetime_for_filename(self):
        """Test datetime formatting for filenames."""
        from filearchitect.utils.datetime import format_datetime_for_filename
        from datetime import datetime

        dt = datetime(2023, 11, 15, 14, 30, 52)
        formatted = format_datetime_for_filename(dt)

        assert "2023" in formatted
        assert "11" in formatted
        assert "15" in formatted
