"""
Unit tests for core components.

Tests scanner, deduplication, detector, and other core functionality.
"""

import pytest
from pathlib import Path
from datetime import datetime

from filearchitect.core.scanner import FileScanner, ScanResult, ScanStatistics
from filearchitect.core.detector import (
    detect_file_type, classify_file, is_supported_file_type,
    get_mime_type, detect_file_type_by_extension, validate_file_format
)
from filearchitect.core.sidecar import (
    is_sidecar_file, find_sidecar_files, copy_sidecar_files,
    has_sidecar_files, get_sidecar_types, filter_sidecar_files
)
from filearchitect.core.deduplication import DeduplicationEngine
from filearchitect.core.constants import FileType
from filearchitect.config.models import Config


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

    def test_scan_statistics(self, source_dir, sample_files):
        """Test that scanner tracks statistics."""
        scanner = FileScanner(source_dir)
        results = list(scanner.scan())

        # Statistics should be populated
        stats = scanner.statistics
        assert stats.total_files > 0
        assert stats.total_size > 0
        assert stats.directories_scanned > 0

    def test_scan_respects_hidden_files_setting(self, source_dir):
        """Test hidden file handling."""
        # Create hidden file
        hidden_file = source_dir / ".hidden_file.txt"
        hidden_file.write_text("Hidden content")

        # Scanner should skip hidden files by default
        scanner1 = FileScanner(source_dir, include_hidden=False)
        results1 = list(scanner1.scan())
        paths1 = [r.file_path for r in results1]
        assert hidden_file not in paths1

        # Scanner should include hidden files when configured
        scanner2 = FileScanner(source_dir, include_hidden=True)
        results2 = list(scanner2.scan())
        paths2 = [r.file_path for r in results2]
        assert hidden_file in paths2

    def test_scan_with_progress_callback(self, source_dir, sample_files):
        """Test scanner progress callback."""
        progress_calls = []

        def progress_callback(files_scanned, total_size):
            progress_calls.append((files_scanned, total_size))

        scanner = FileScanner(source_dir)
        list(scanner.scan(progress_callback=progress_callback))

        # Progress callback should have been called
        assert len(progress_calls) > 0

    def test_scan_filter_supported_only(self, source_dir, sample_files):
        """Test filtering for supported file types only."""
        # Add some unsupported files
        (source_dir / "test.xyz").write_text("unknown")
        (source_dir / "test.abc").write_text("unknown")

        scanner = FileScanner(source_dir)

        # Scan all files
        all_results = list(scanner.scan(filter_supported_only=False))

        # Scan supported only
        supported_results = list(scanner.scan(filter_supported_only=True))

        # Should have fewer supported files
        assert len(supported_results) <= len(all_results)

    def test_should_skip_folder(self, temp_dir):
        """Test folder skip logic."""
        scanner = FileScanner(temp_dir, skip_folders=["node_modules", "*.tmp"])

        # Should skip matching folders
        assert scanner.should_skip_folder(Path("node_modules")) is True
        assert scanner.should_skip_folder(Path("cache.tmp")) is True

        # Should not skip non-matching folders
        assert scanner.should_skip_folder(Path("src")) is False

    def test_should_skip_file(self, temp_dir):
        """Test file skip logic."""
        scanner = FileScanner(temp_dir, skip_files=["*.tmp", "thumbs.db"])

        # Should skip matching files
        assert scanner.should_skip_file(Path("cache.tmp")) is True
        assert scanner.should_skip_file(Path("thumbs.db")) is True

        # Should not skip non-matching files
        assert scanner.should_skip_file(Path("photo.jpg")) is False

    def test_scan_handles_symlinks(self, temp_dir):
        """Test symlink handling."""
        # Create a file and a symlink to it
        real_file = temp_dir / "real.txt"
        real_file.write_text("real content")

        link_file = temp_dir / "link.txt"
        try:
            link_file.symlink_to(real_file)
        except OSError:
            # Symlink creation may fail on some systems
            pytest.skip("Symlink creation not supported")

        # Scan without following symlinks
        scanner1 = FileScanner(temp_dir, follow_symlinks=False)
        results1 = list(scanner1.scan())

        # Scan with following symlinks
        scanner2 = FileScanner(temp_dir, follow_symlinks=True)
        results2 = list(scanner2.scan())

        # Both should find files
        assert len(results1) > 0
        assert len(results2) > 0


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

    def test_is_supported_file_type(self, sample_image_path, temp_dir):
        """Test supported file type checking."""
        assert is_supported_file_type(sample_image_path) is True

        unknown_file = temp_dir / "test.xyz"
        unknown_file.write_text("unknown")
        # Unknown files may not be supported
        result = is_supported_file_type(unknown_file)
        assert isinstance(result, bool)

    def test_get_mime_type(self, sample_image_path):
        """Test MIME type detection."""
        mime_type = get_mime_type(sample_image_path)

        assert mime_type is not None
        assert "image" in mime_type.lower()

    def test_detect_file_type_by_extension(self, temp_dir):
        """Test file type detection by extension."""
        # Image extensions
        jpg_file = temp_dir / "test.jpg"
        jpg_file.touch()
        assert detect_file_type_by_extension(jpg_file) == FileType.IMAGE

        # Video extensions
        mp4_file = temp_dir / "test.mp4"
        mp4_file.touch()
        assert detect_file_type_by_extension(mp4_file) == FileType.VIDEO

        # Audio extensions
        mp3_file = temp_dir / "test.mp3"
        mp3_file.touch()
        assert detect_file_type_by_extension(mp3_file) == FileType.AUDIO

        # Document extensions
        pdf_file = temp_dir / "test.pdf"
        pdf_file.touch()
        assert detect_file_type_by_extension(pdf_file) == FileType.DOCUMENT

    def test_validate_file_format(self, sample_image_path):
        """Test file format validation."""
        # Valid - is an image
        assert validate_file_format(sample_image_path, FileType.IMAGE) is True

        # Invalid - not a video
        assert validate_file_format(sample_image_path, FileType.VIDEO) is False

    def test_detect_various_image_formats(self, temp_dir):
        """Test detection of various image formats."""
        from PIL import Image

        # JPEG
        jpg = temp_dir / "test.jpg"
        Image.new("RGB", (10, 10)).save(jpg)
        assert detect_file_type(jpg) == FileType.IMAGE

        # PNG
        png = temp_dir / "test.png"
        Image.new("RGB", (10, 10)).save(png)
        assert detect_file_type(png) == FileType.IMAGE

    def test_detect_unknown_file(self, temp_dir):
        """Test detection of unknown file types."""
        unknown_file = temp_dir / "test.xyz"
        unknown_file.write_bytes(b'\x00\x01\x02\x03random binary data')

        file_type = detect_file_type(unknown_file)
        # Should return UNKNOWN for unrecognized types
        assert file_type in (FileType.UNKNOWN, FileType.DOCUMENT)


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

    def test_find_sidecar_files_none_exist(self, temp_dir):
        """Test finding sidecar files when none exist."""
        main_file = temp_dir / "photo.jpg"
        main_file.touch()

        sidecars = find_sidecar_files(main_file)
        assert len(sidecars) == 0

    def test_copy_sidecar_files(self, temp_dir):
        """Test copying sidecar files."""
        source_dir = temp_dir / "source"
        dest_dir = temp_dir / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()

        # Create main file and sidecar
        main_file = source_dir / "photo.jpg"
        main_file.write_text("image")
        sidecar = source_dir / "photo.xmp"
        sidecar.write_text("metadata")

        # Copy sidecars
        dest_main = dest_dir / "photo.jpg"
        result = copy_sidecar_files(main_file, dest_main)

        # Sidecar should be copied
        dest_sidecar = dest_dir / "photo.xmp"
        assert dest_sidecar.exists()
        assert dest_sidecar.read_text() == "metadata"

    def test_has_sidecar_files(self, temp_dir):
        """Test checking if file has sidecars."""
        # File without sidecars
        main_file = temp_dir / "photo.jpg"
        main_file.touch()
        assert has_sidecar_files(main_file) is False

        # File with sidecars
        sidecar = temp_dir / "photo.xmp"
        sidecar.touch()
        assert has_sidecar_files(main_file) is True

    def test_get_sidecar_types(self, temp_dir):
        """Test getting sidecar types."""
        main_file = temp_dir / "photo.jpg"
        main_file.touch()

        # Create various sidecars
        (temp_dir / "photo.xmp").touch()
        (temp_dir / "photo.aae").touch()

        sidecar_types = get_sidecar_types(main_file)
        assert isinstance(sidecar_types, set)

    def test_filter_sidecar_files(self, temp_dir):
        """Test filtering sidecar files from list."""
        # Create main files and sidecars
        main1 = temp_dir / "photo1.jpg"
        main2 = temp_dir / "photo2.jpg"
        sidecar1 = temp_dir / "photo1.xmp"
        sidecar2 = temp_dir / "photo2.aae"

        for f in [main1, main2, sidecar1, sidecar2]:
            f.touch()

        all_files = [main1, main2, sidecar1, sidecar2]
        main_files, sidecar_files = filter_sidecar_files(all_files)

        assert main1 in main_files
        assert main2 in main_files
        assert sidecar1 in sidecar_files
        assert sidecar2 in sidecar_files

    def test_sidecar_various_types(self):
        """Test various sidecar file types."""
        # XMP (Adobe)
        assert is_sidecar_file(Path("photo.xmp")) is True

        # AAE (Apple)
        assert is_sidecar_file(Path("photo.aae")) is True

        # THM (Thumbnail)
        assert is_sidecar_file(Path("photo.thm")) is True


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

    def test_no_duplicates_for_different_files(self, temp_dir, db_manager, session_id):
        """Test that different files are not marked as duplicates."""
        from filearchitect.database.models import FileRecord
        from filearchitect.core.constants import ProcessingStatus

        # Create two different files
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        file1.write_text("Content A" * 100)
        file2.write_text("Content B" * 100)

        dedup = DeduplicationEngine(db_manager)

        # Register first file
        hash1 = dedup.calculate_and_cache_hash(file1)
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

        # Check second file - should not be duplicate
        is_dup, original_id = dedup.check_duplicate(file2)
        assert is_dup is False

    def test_hash_for_different_files(self, temp_dir, db_manager):
        """Test that different files have different hashes."""
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B that is different")

        dedup = DeduplicationEngine(db_manager)

        # Calculate hashes for different files
        hash1 = dedup.calculate_and_cache_hash(file1)
        hash2 = dedup.calculate_and_cache_hash(file2)

        # Different files should have different hashes
        assert hash1 != hash2

    def test_hash_calculation_for_file(self, temp_dir, db_manager):
        """Test hash calculation."""
        test_file = temp_dir / "test.txt"
        content = "Test content" * 100
        test_file.write_text(content)

        dedup = DeduplicationEngine(db_manager)

        # Calculate hash
        file_hash = dedup.calculate_and_cache_hash(test_file)

        assert len(file_hash) == 64  # SHA-256
        assert isinstance(file_hash, str)

    def test_multiple_duplicates(self, temp_dir, db_manager, session_id):
        """Test handling of multiple duplicate files."""
        from filearchitect.database.models import FileRecord
        from filearchitect.core.constants import ProcessingStatus

        # Create three identical files
        files = []
        content = "Shared content" * 100
        for i in range(3):
            f = temp_dir / f"file{i}.txt"
            f.write_text(content)
            files.append(f)

        dedup = DeduplicationEngine(db_manager)

        # Register first file
        hash1 = dedup.calculate_and_cache_hash(files[0])
        file_record = FileRecord(
            session_id=session_id,
            source_path=str(files[0]),
            destination_path=str(files[0]),
            file_hash=hash1,
            file_size=files[0].stat().st_size,
            file_type=FileType.DOCUMENT,
            file_extension=files[0].suffix,
            status=ProcessingStatus.COMPLETED,
            processed_at=datetime.now()
        )
        db_manager.insert_file(file_record)

        # Check other files - all should be duplicates
        for f in files[1:]:
            is_dup, original_id = dedup.check_duplicate(f)
            assert is_dup is True


def get_default_config():
    """Helper to get default config."""
    from filearchitect.config.manager import get_default_config
    return get_default_config()
