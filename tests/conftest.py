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
