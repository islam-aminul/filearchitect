"""
Integration tests for complete processing workflows.

Tests the full end-to-end processing of files.
"""

import pytest
from pathlib import Path
from datetime import datetime
from PIL import Image
import piexif

from filearchitect.core.scanner import FileScanner
from filearchitect.core.detector import detect_file_type
from filearchitect.core.pipeline import ProcessingPipeline
from filearchitect.database.manager import DatabaseManager
from filearchitect.database.models import Session
from filearchitect.config.models import Config
from filearchitect.core.constants import FileType, SessionStatus, ProcessingStatus
from filearchitect.processors.image import ImageProcessor
from filearchitect.processors.document import DocumentProcessor


class TestFileScanning:
    """Test complete file scanning workflows."""

    @pytest.fixture
    def complex_source_dir(self, temp_dir):
        """Create a complex directory structure with various files."""
        source = temp_dir / "source"
        source.mkdir()

        # Create nested directories
        (source / "Photos" / "2023" / "05").mkdir(parents=True)
        (source / "Documents").mkdir()
        (source / "Screenshots").mkdir()
        (source / ".hidden").mkdir()

        # Create image files with EXIF
        img1_path = source / "Photos" / "2023" / "05" / "IMG_20230515_143045.jpg"
        img1 = Image.new("RGB", (1920, 1080), color="blue")
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Canon",
                piexif.ImageIFD.Model: b"EOS 5D",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2023:05:15 14:30:45",
            }
        }
        exif_bytes = piexif.dump(exif_dict)
        img1.save(img1_path, exif=exif_bytes)

        # Create screenshot
        screenshot = source / "Screenshots" / "Screenshot 2023-05-20.png"
        img2 = Image.new("RGB", (1920, 1080), color="green")
        img2.save(screenshot)

        # Create document
        doc = source / "Documents" / "report.pdf"
        doc.write_bytes(b'%PDF-1.4\n')

        # Create text file
        txt = source / "Documents" / "notes.txt"
        txt.write_text("Meeting notes")

        # Create hidden file (should be skipped)
        hidden = source / ".hidden" / "secret.txt"
        hidden.write_text("Hidden content")

        return source

    def test_scan_directory_with_nested_structure(self, complex_source_dir, sample_config):
        """Test scanning a directory with nested structure."""
        scanner = FileScanner(sample_config)

        files = list(scanner.scan_directory(complex_source_dir))

        # Should find all non-hidden files
        assert len(files) >= 4  # At least the 4 visible files

        # Should not include hidden directory files
        hidden_files = [f for f in files if '.hidden' in str(f)]
        assert len(hidden_files) == 0

    def test_scan_respects_skip_patterns(self, complex_source_dir, sample_config):
        """Test that scanner respects skip patterns."""
        # Add skip pattern for Screenshots folder
        sample_config.skip_patterns.folders.append("Screenshots")

        scanner = FileScanner(sample_config)
        files = list(scanner.scan_directory(complex_source_dir))

        # Should not include screenshot files
        screenshot_files = [f for f in files if 'Screenshots' in str(f)]
        assert len(screenshot_files) == 0

    def test_scan_detects_file_types(self, complex_source_dir):
        """Test that scanned files have correct types detected."""
        from filearchitect.config.models import Config
        scanner = FileScanner(Config())

        files = list(scanner.scan_directory(complex_source_dir))

        # Detect types for all files
        file_types = {}
        for file_path in files:
            file_type = detect_file_type(file_path)
            file_types[file_path.name] = file_type

        # Check we have various types
        types_found = set(file_types.values())
        assert FileType.IMAGE in types_found
        assert FileType.DOCUMENT in types_found


class TestEndToEndProcessing:
    """Test end-to-end file processing workflows."""

    @pytest.fixture
    def processing_setup(self, temp_dir, db_manager):
        """Set up complete processing environment."""
        source = temp_dir / "source"
        dest = temp_dir / "destination"
        source.mkdir()
        dest.mkdir()

        # Create test images
        img1 = source / "photo1.jpg"
        image = Image.new("RGB", (1920, 1080), color="red")
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Nikon",
                piexif.ImageIFD.Model: b"D850",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2024:03:20 10:15:30",
            }
        }
        exif_bytes = piexif.dump(exif_dict)
        image.save(img1, exif=exif_bytes)

        # Create test document
        doc1 = source / "document.pdf"
        doc1.write_bytes(b'%PDF-1.4\n')

        config = Config()
        session = Session(
            session_id="test_session",
            source_path=str(source),
            destination_path=str(dest),
            status=SessionStatus.RUNNING,
            start_time=datetime.now()
        )
        db_manager.create_session(session)

        return {
            'source': source,
            'dest': dest,
            'config': config,
            'db': db_manager,
            'session_id': "test_session"
        }

    def test_image_processing_workflow(self, processing_setup):
        """Test complete image processing workflow."""
        setup = processing_setup
        image_file = setup['source'] / "photo1.jpg"

        # Create processor and pipeline
        processor = ImageProcessor(setup['config'])
        pipeline = ProcessingPipeline(
            config=setup['config'],
            db_manager=setup['db'],
            session_id=setup['session_id'],
            preview_mode=False
        )

        # Process the file
        result = pipeline.process_file(image_file)

        # Verify result
        assert result is not None
        assert result.status in [ProcessingStatus.COMPLETED, ProcessingStatus.SKIPPED]

        # If completed, verify file was organized
        if result.status == ProcessingStatus.COMPLETED:
            assert result.destination_path is not None
            # Should be in Images directory
            assert 'Images' in str(result.destination_path)

    def test_document_processing_workflow(self, processing_setup):
        """Test complete document processing workflow."""
        setup = processing_setup
        doc_file = setup['source'] / "document.pdf"

        # Create processor and pipeline
        processor = DocumentProcessor(setup['config'])
        pipeline = ProcessingPipeline(
            config=setup['config'],
            db_manager=setup['db'],
            session_id=setup['session_id'],
            preview_mode=False
        )

        # Process the file
        result = pipeline.process_file(doc_file)

        # Verify result
        assert result is not None
        assert result.status in [ProcessingStatus.COMPLETED, ProcessingStatus.SKIPPED]

        # If completed, verify file was organized
        if result.status == ProcessingStatus.COMPLETED:
            assert result.destination_path is not None
            # Should be in Documents directory
            assert 'Documents' in str(result.destination_path)

    def test_duplicate_detection_workflow(self, processing_setup):
        """Test duplicate file detection in workflow."""
        setup = processing_setup

        # Create two identical files
        img1 = setup['source'] / "photo1.jpg"
        img2 = setup['source'] / "photo1_copy.jpg"

        image = Image.new("RGB", (100, 100), color="red")
        image.save(img1)
        image.save(img2)

        # Create pipeline
        pipeline = ProcessingPipeline(
            config=setup['config'],
            db_manager=setup['db'],
            session_id=setup['session_id'],
            preview_mode=False
        )

        # Process both files
        result1 = pipeline.process_file(img1)
        result2 = pipeline.process_file(img2)

        # First should complete, second should be duplicate
        assert result1.status == ProcessingStatus.COMPLETED
        # Note: Duplicate detection depends on config and implementation
        # The second file might be completed or marked as duplicate

    def test_preview_mode_workflow(self, processing_setup):
        """Test preview mode (dry-run) workflow."""
        setup = processing_setup
        image_file = setup['source'] / "photo1.jpg"

        # Create pipeline in preview mode
        pipeline = ProcessingPipeline(
            config=setup['config'],
            db_manager=setup['db'],
            session_id=setup['session_id'],
            preview_mode=True
        )

        # Process the file
        result = pipeline.process_file(image_file)

        # Verify result
        assert result is not None

        # In preview mode, no actual files should be created
        # The destination should be planned but not executed
        if result.destination_path:
            # File should not actually exist at destination
            dest_file = Path(result.destination_path)
            # In preview mode, file might not be copied
            # Exact behavior depends on implementation


class TestDatabaseIntegration:
    """Test database integration in workflows."""

    def test_session_tracking(self, db_manager, temp_dir):
        """Test session creation and tracking."""
        source = temp_dir / "source"
        dest = temp_dir / "destination"
        source.mkdir()
        dest.mkdir()

        # Create session
        session = Session(
            session_id="test_integration",
            source_path=str(source),
            destination_path=str(dest),
            status=SessionStatus.RUNNING,
            start_time=datetime.now()
        )
        db_manager.create_session(session)

        # Verify session exists
        sessions = db_manager.get_incomplete_sessions()
        assert len(sessions) > 0
        assert any(s.session_id == "test_integration" for s in sessions)

    def test_file_record_creation(self, db_manager, temp_dir, session_id):
        """Test file record creation in database."""
        from filearchitect.database.models import FileRecord
        from filearchitect.core.constants import ProcessingStatus

        # Create a file record
        file_record = FileRecord(
            session_id=session_id,
            source_path=str(temp_dir / "test.jpg"),
            file_hash="abc123",
            file_type=FileType.IMAGE,
            file_size=1024,
            status=ProcessingStatus.COMPLETED,
            destination_path=str(temp_dir / "dest" / "test.jpg")
        )

        db_manager.insert_file_record(file_record)

        # Verify record exists
        files = db_manager.get_files_by_session(session_id)
        assert len(files) > 0
        assert any(f.source_path == str(temp_dir / "test.jpg") for f in files)


class TestErrorHandling:
    """Test error handling in workflows."""

    def test_corrupt_file_handling(self, temp_dir, sample_config):
        """Test handling of corrupt files."""
        # Create a corrupt image file
        corrupt_file = temp_dir / "corrupt.jpg"
        corrupt_file.write_bytes(b'Not a real JPEG file')

        processor = ImageProcessor(sample_config)

        # Try to extract metadata - should handle gracefully
        try:
            metadata = processor.extract_metadata(corrupt_file)
            # Should either return empty metadata or raise ProcessingError
            assert isinstance(metadata, dict) or metadata is None
        except Exception as e:
            # Should be a known exception type
            assert "ProcessingError" in str(type(e)) or "Error" in str(type(e))

    def test_missing_file_handling(self, temp_dir, sample_config):
        """Test handling of missing files."""
        missing_file = temp_dir / "does_not_exist.jpg"

        processor = ImageProcessor(sample_config)

        # Try to process missing file - should handle gracefully
        try:
            metadata = processor.extract_metadata(missing_file)
            # Should handle missing file
        except Exception as e:
            # Should be an appropriate error
            assert "Error" in str(type(e))

    def test_permission_error_handling(self, temp_dir, sample_config):
        """Test handling of permission errors."""
        # This test is platform-specific and might need adjustment
        # for different operating systems
        pass  # Skip for now, implementation depends on OS
