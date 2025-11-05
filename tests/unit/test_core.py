"""
Unit tests for core components.

Tests scanner, deduplication, detector, and other core functionality.
"""

import pytest
from pathlib import Path

from filearchitect.core.scanner import FileScanner, scan_directory
from filearchitect.core.detector import detect_file_type, classify_file
from filearchitect.core.sidecar import is_sidecar_file, find_sidecar_files
from filearchitect.core.deduplication import DeduplicationEngine
from filearchitect.core.constants import FileType


@pytest.mark.unit
class TestFileScanner:
    """Test FileScanner class."""

    def test_scan_directory_finds_files(self, source_dir, sample_files):
        """Test that scanner finds all files."""
        scanner = FileScanner(source_dir)
        results = list(scanner.scan())

        # Get file paths from scan results
        scanned_paths = [result.file_path for result in results]
        assert len(scanned_paths) >= len(sample_files)

    def test_scan_respects_skip_patterns(self, source_dir, sample_config):
        """Test that scanner respects skip patterns."""
        # Create a file to be skipped
        skip_dir = source_dir / "node_modules"
        skip_dir.mkdir()
        (skip_dir / "package.json").write_text("{}")

        scanner = FileScanner(source_dir, skip_folders=["node_modules"])
        results = list(scanner.scan())

        # node_modules should be skipped
        scanned_paths = [result.file_path for result in results]
        assert not any("node_modules" in str(f) for f in scanned_paths)

    def test_scan_handles_nested_directories(self, source_dir):
        """Test scanning nested directories."""
        # Create nested structure
        nested = source_dir / "level1" / "level2" / "level3"
        nested.mkdir(parents=True)
        test_file = nested / "deep_file.txt"
        test_file.write_text("Deep file")

        scanner = FileScanner(source_dir)
        results = list(scanner.scan())

        scanned_paths = [result.file_path for result in results]
        assert test_file in scanned_paths


@pytest.mark.unit
class TestFileDetector:
    """Test file type detection."""

    def test_detect_image_file(self, sample_image_path):
        """Test image file detection."""
        file_type = detect_file_type(sample_image_path)
        assert file_type == FileType.IMAGE

    def test_detect_text_file(self, temp_dir):
        """Test text file detection."""
        text_file = temp_dir / "test.txt"
        text_file.write_text("Plain text content")

        file_type = detect_file_type(text_file)
        assert file_type in (FileType.DOCUMENT, FileType.UNKNOWN)

    def test_detect_pdf_file(self, temp_dir):
        """Test PDF file detection."""
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')

        file_type = detect_file_type(pdf_file)
        assert file_type == FileType.DOCUMENT

    def test_classify_file(self, sample_image_path):
        """Test file classification."""
        file_type, extension = classify_file(sample_image_path)

        assert file_type == FileType.IMAGE
        assert extension == ".jpg"


@pytest.mark.unit
class TestSidecarFiles:
    """Test sidecar file handling."""

    def test_is_sidecar_file(self):
        """Test sidecar file identification."""
        assert is_sidecar_file(Path("photo.xmp")) is True
        assert is_sidecar_file(Path("photo.aae")) is True
        assert is_sidecar_file(Path("photo.thm")) is True
        assert is_sidecar_file(Path("photo.jpg")) is False

    def test_find_sidecar_files(self, temp_dir):
        """Test finding sidecar files for a main file."""
        # Create main file and sidecars
        main_file = temp_dir / "photo.jpg"
        main_file.touch()
        sidecar1 = temp_dir / "photo.xmp"
        sidecar1.touch()
        sidecar2 = temp_dir / "photo.aae"
        sidecar2.touch()

        sidecars = find_sidecar_files(main_file)
        assert len(sidecars) == 2
        assert sidecar1 in sidecars
        assert sidecar2 in sidecars


@pytest.mark.unit
class TestDeduplication:
    """Test deduplication engine."""

    def test_detect_duplicate_files(self, temp_dir, db_manager, session_id):
        """Test duplicate file detection."""
        from filearchitect.database.models import FileRecord
        from filearchitect.core.constants import ProcessingStatus
        from datetime import datetime

        # Create two identical files
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        content = "Duplicate content" * 100

        file1.write_text(content)
        file2.write_text(content)

        dedup = DeduplicationEngine(db_manager)

        # Calculate hash for first file
        hash1 = dedup.calculate_and_cache_hash(file1)

        # Register first file in database
        file_record = FileRecord(
            session_id=session_id,
            source_path=str(file1),
            destination_path=str(file1),
            file_hash=hash1,
            file_size=file1.stat().st_size,
            file_type=FileType.DOCUMENT,
            file_extension=file1.suffix,
            status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now()
        )
        db_manager.insert_file(file_record)

        # Check if second file is duplicate
        is_dup, original_id = dedup.check_duplicate(file2)
        assert is_dup  # Second file should be detected as duplicate
        assert original_id is not None

    def test_hash_caching(self, temp_dir, db_manager):
        """Test that file hashes are cached."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test content for caching")

        dedup = DeduplicationEngine(db_manager)

        # First call should calculate hash
        hash1 = dedup.calculate_and_cache_hash(test_file)

        # Second call should use cached value (from memory or db)
        hash2 = dedup.calculate_and_cache_hash(test_file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters


def get_default_config():
    """Helper to get default config."""
    from filearchitect.config.manager import get_default_config
    return get_default_config()
