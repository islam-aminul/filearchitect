"""
Pytest configuration and shared fixtures.

This module provides common fixtures and configuration for all tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_image_path(temp_dir):
    """Create a sample image file for testing."""
    from PIL import Image

    image_path = temp_dir / "test_image.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)
    return image_path


@pytest.fixture
def sample_config():
    """Provide a sample configuration for testing."""
    from filearchitect.config.models import Config

    return Config()


@pytest.fixture
def mock_logger(mocker):
    """Provide a mocked logger for testing."""
    return mocker.patch("filearchitect.core.logging.get_logger")


@pytest.fixture
def source_dir(temp_dir):
    """Create a source directory."""
    source = temp_dir / "source"
    source.mkdir()
    return source


@pytest.fixture
def dest_dir(temp_dir):
    """Create a destination directory."""
    dest = temp_dir / "destination"
    dest.mkdir()
    return dest


@pytest.fixture
def sample_files(source_dir):
    """Create multiple sample files of different types."""
    from PIL import Image

    files = []

    # Image files
    img1 = source_dir / "photo1.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img1)
    files.append(img1)

    img2 = source_dir / "photo2.png"
    img = Image.new("RGB", (200, 150), color="blue")
    img.save(img2)
    files.append(img2)

    # Text file
    txt = source_dir / "document.txt"
    txt.write_text("Sample document content")
    files.append(txt)

    # PDF (minimal header)
    pdf = source_dir / "document.pdf"
    pdf.write_bytes(b'%PDF-1.4\n')
    files.append(pdf)

    return files


@pytest.fixture
def db_manager(temp_dir):
    """Create a test database manager."""
    from filearchitect.database.manager import DatabaseManager

    db_path = temp_dir / "test.db"
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def session_id(db_manager):
    """Create a test session."""
    from datetime import datetime
    from filearchitect.database.models import Session
    from filearchitect.core.constants import SessionStatus
    import uuid

    session = Session(
        session_id=str(uuid.uuid4()),
        source_path="/test/source",
        destination_path="/test/dest",
        status=SessionStatus.RUNNING,
        start_time=datetime.now()
    )
    db_manager.create_session(session)
    return session.session_id
