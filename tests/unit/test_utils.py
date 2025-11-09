"""
Unit tests for utility functions.

This module tests path utilities, hash calculation, and other helper functions.
"""

import pytest
from pathlib import Path
from datetime import datetime

from filearchitect.utils.path import (
    sanitize_filename, resolve_conflict, is_path_accessible,
    ensure_directory, get_available_space, get_relative_path
)
from filearchitect.utils.hash import calculate_file_hash, verify_file_hash
from filearchitect.utils.filesystem import (
    copy_file_streaming, move_file_safe, copy_file_atomic,
    safe_delete_file, safe_delete_directory, calculate_directory_size,
    check_file_permissions, is_file_locked, create_temp_file,
    create_temp_directory, remove_empty_directories
)
from filearchitect.utils.datetime import (
    parse_filename_date, format_datetime_for_filename,
    parse_exif_date, parse_folder_date, parse_date_with_fallback,
    validate_date, get_year_from_date
)


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

    def test_is_path_accessible(self, temp_dir):
        """Test path accessibility check."""
        # Accessible directory
        assert is_path_accessible(temp_dir) is True

        # Accessible file
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        assert is_path_accessible(test_file) is True

        # Non-existent path
        assert is_path_accessible(temp_dir / "nonexistent") is False

    def test_ensure_directory(self, temp_dir):
        """Test directory creation."""
        new_dir = temp_dir / "new" / "nested" / "dir"
        ensure_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_get_available_space(self, temp_dir):
        """Test getting available disk space."""
        space = get_available_space(temp_dir)

        assert space > 0
        assert isinstance(space, int)

    def test_get_relative_path(self, temp_dir):
        """Test relative path calculation."""
        base = temp_dir
        target = temp_dir / "subdir" / "file.txt"

        rel_path = get_relative_path(target, base)
        assert rel_path == Path("subdir") / "file.txt"


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

    def test_verify_file_hash(self, sample_image_path):
        """Test file hash verification."""
        # Calculate hash
        file_hash = calculate_file_hash(sample_image_path)

        # Verify with correct hash
        assert verify_file_hash(sample_image_path, file_hash) is True

        # Verify with incorrect hash
        assert verify_file_hash(sample_image_path, "0" * 64) is False

    def test_calculate_file_hash_with_progress(self, temp_dir):
        """Test file hash calculation with progress callback."""
        # Create a larger file
        large_file = temp_dir / "large.bin"
        large_file.write_bytes(b"x" * 1024 * 1024)  # 1MB

        progress_calls = []

        def progress_callback(bytes_read, total_bytes):
            progress_calls.append((bytes_read, total_bytes))

        file_hash = calculate_file_hash(large_file, progress_callback=progress_callback)

        assert len(file_hash) == 64
        # Progress callback should have been called
        assert len(progress_calls) > 0


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
        # Create some files
        (temp_dir / "file1.txt").write_text("a" * 100)
        (temp_dir / "file2.txt").write_text("b" * 200)

        size = calculate_directory_size(temp_dir)
        assert size >= 300  # At least 300 bytes

    def test_copy_file_streaming_with_progress(self, temp_dir):
        """Test streaming copy with progress callback."""
        source = temp_dir / "source.bin"
        source.write_bytes(b"x" * 10000)
        dest = temp_dir / "dest.bin"

        progress_calls = []

        def progress(bytes_copied, total_bytes):
            progress_calls.append((bytes_copied, total_bytes))

        copy_file_streaming(source, dest, progress_callback=progress)

        assert dest.exists()
        assert dest.read_bytes() == source.read_bytes()
        assert len(progress_calls) > 0

    def test_move_file_safe(self, temp_dir):
        """Test safe file move."""
        source = temp_dir / "source.txt"
        source.write_text("Move me")
        dest = temp_dir / "subdir" / "dest.txt"

        move_file_safe(source, dest)

        assert not source.exists()
        assert dest.exists()
        assert dest.read_text() == "Move me"

    def test_copy_file_atomic(self, temp_dir):
        """Test atomic file copy."""
        source = temp_dir / "source.txt"
        source.write_text("Atomic copy")
        dest = temp_dir / "dest.txt"

        copy_file_atomic(source, dest)

        assert dest.exists()
        assert dest.read_text() == "Atomic copy"

    def test_safe_delete_directory(self, temp_dir):
        """Test safe directory deletion."""
        test_dir = temp_dir / "delete_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        assert test_dir.exists()
        safe_delete_directory(test_dir, recursive=True)
        assert not test_dir.exists()

    def test_check_file_permissions(self, temp_dir):
        """Test file permissions check."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        # Should have read permission
        has_read = check_file_permissions(test_file, require_read=True)
        assert has_read is True

        # Should have write permission
        has_write = check_file_permissions(test_file, require_write=True)
        assert has_write is True

    def test_is_file_locked(self, temp_dir):
        """Test file lock detection."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        # File should not be locked
        assert is_file_locked(test_file) is False

    def test_create_temp_file(self):
        """Test temporary file creation."""
        temp_file = create_temp_file(suffix=".txt")

        assert temp_file.exists()
        assert temp_file.suffix == ".txt"

        # Clean up
        temp_file.unlink()

    def test_create_temp_directory(self):
        """Test temporary directory creation."""
        temp_dir_path = create_temp_directory(prefix="test_")

        assert temp_dir_path.exists()
        assert temp_dir_path.is_dir()
        assert "test_" in temp_dir_path.name

        # Clean up
        temp_dir_path.rmdir()

    def test_remove_empty_directories(self, temp_dir):
        """Test removal of empty directories."""
        # Create nested empty directories
        (temp_dir / "empty1").mkdir()
        (temp_dir / "empty2" / "nested").mkdir(parents=True)
        (temp_dir / "nonempty").mkdir()
        (temp_dir / "nonempty" / "file.txt").write_text("content")

        remove_empty_directories(temp_dir)

        # Empty directories should be removed
        assert not (temp_dir / "empty1").exists()
        assert not (temp_dir / "empty2").exists()

        # Non-empty directory should remain
        assert (temp_dir / "nonempty").exists()
        assert (temp_dir / "nonempty" / "file.txt").exists()


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
        dt = datetime(2023, 11, 15, 14, 30, 52)
        formatted = format_datetime_for_filename(dt)

        assert "2023" in formatted
        assert "11" in formatted
        assert "15" in formatted

    def test_parse_exif_date(self):
        """Test EXIF date parsing."""
        # Standard EXIF format
        exif_date = "2023:11:15 14:30:52"
        result = parse_exif_date(exif_date)

        assert result is not None
        assert result.year == 2023
        assert result.month == 11
        assert result.day == 15

    def test_parse_folder_date(self):
        """Test folder date parsing."""
        # Test year folder pattern (YYYY)
        assert parse_folder_date("/photos/2023") is not None

        # Test nested path with year and month folders
        assert parse_folder_date("/photos/2023/11") is not None

        # Test nested path with year, month, and day
        assert parse_folder_date("/photos/2023/11/15") is not None

    def test_parse_date_with_fallback(self, temp_dir):
        """Test date parsing with fallback chain."""
        # Create a file with date in filename
        test_file = temp_dir / "IMG_20231115_143052.jpg"
        test_file.touch()

        date, source = parse_date_with_fallback(
            filename=test_file.name,
            folder_path=str(temp_dir)
        )

        assert date is not None
        assert source is not None

    def test_validate_date(self):
        """Test date validation."""
        # Valid date
        valid_date = datetime(2023, 11, 15, 14, 30, 52)
        assert validate_date(valid_date) is True

        # Date too far in future
        future_date = datetime(2050, 1, 1)
        assert validate_date(future_date) is False

        # Date too far in past
        old_date = datetime(1900, 1, 1)
        assert validate_date(old_date) is False

    def test_get_year_from_date(self):
        """Test year extraction from date."""
        test_date = datetime(2023, 11, 15, 14, 30, 52)
        year = get_year_from_date(test_date)

        assert year == "2023"

    def test_parse_filename_date_various_formats(self):
        """Test parsing dates from various filename formats."""
        # WhatsApp format
        assert parse_filename_date("IMG-20231115-WA0001.jpg") is not None

        # Screenshot format
        assert parse_filename_date("Screenshot_2023-11-15_at_14.30.45.png") is not None

        # iPhone format
        assert parse_filename_date("IMG_0123.HEIC") is None  # No date in filename

        # Standard format
        assert parse_filename_date("2023-11-15 14-30-52.jpg") is not None

        # Underscore format
        assert parse_filename_date("20231115_143052.mp4") is not None
