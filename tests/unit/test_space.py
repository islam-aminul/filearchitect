"""
Unit tests for disk space management.

This module tests space checking, monitoring, and threshold alerts.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import shutil

from filearchitect.core.space import SpaceManager, SpaceInfo
from filearchitect.core.exceptions import InsufficientSpaceError


@pytest.mark.unit
class TestSpaceInfo:
    """Test SpaceInfo dataclass."""

    def test_space_info_creation(self):
        """Test creating SpaceInfo object."""
        info = SpaceInfo(
            path=Path("/test"),
            total_bytes=1024 ** 3 * 100,  # 100GB
            used_bytes=1024 ** 3 * 60,    # 60GB
            free_bytes=1024 ** 3 * 40,    # 40GB
            percent_used=60.0
        )

        assert info.path == Path("/test")
        assert info.total_bytes == 1024 ** 3 * 100
        assert info.percent_used == 60.0

    def test_total_gb_property(self):
        """Test total_gb property."""
        info = SpaceInfo(
            path=Path("/test"),
            total_bytes=1024 ** 3 * 100,  # 100GB
            used_bytes=1024 ** 3 * 60,
            free_bytes=1024 ** 3 * 40,
            percent_used=60.0
        )

        assert info.total_gb == pytest.approx(100.0, rel=0.01)

    def test_used_gb_property(self):
        """Test used_gb property."""
        info = SpaceInfo(
            path=Path("/test"),
            total_bytes=1024 ** 3 * 100,
            used_bytes=1024 ** 3 * 60,  # 60GB
            free_bytes=1024 ** 3 * 40,
            percent_used=60.0
        )

        assert info.used_gb == pytest.approx(60.0, rel=0.01)

    def test_free_gb_property(self):
        """Test free_gb property."""
        info = SpaceInfo(
            path=Path("/test"),
            total_bytes=1024 ** 3 * 100,
            used_bytes=1024 ** 3 * 60,
            free_bytes=1024 ** 3 * 40,  # 40GB
            percent_used=60.0
        )

        assert info.free_gb == pytest.approx(40.0, rel=0.01)

    def test_repr(self):
        """Test string representation."""
        info = SpaceInfo(
            path=Path("/test"),
            total_bytes=1024 ** 3 * 100,
            used_bytes=1024 ** 3 * 60,
            free_bytes=1024 ** 3 * 40,
            percent_used=60.0
        )

        repr_str = repr(info)

        assert "40.00GB free" in repr_str
        assert "100.00GB total" in repr_str
        assert "60.0% used" in repr_str


@pytest.mark.unit
class TestSpaceManager:
    """Test SpaceManager functionality."""

    def test_initialization_defaults(self):
        """Test initialization with default values."""
        manager = SpaceManager()

        assert manager.min_free_gb == 5.0
        assert manager.buffer_percent == 10
        assert manager.export_overhead == 0.3

    def test_initialization_custom(self):
        """Test initialization with custom values."""
        manager = SpaceManager(
            min_free_gb=10.0,
            buffer_percent=15,
            export_overhead=0.5
        )

        assert manager.min_free_gb == 10.0
        assert manager.buffer_percent == 15
        assert manager.export_overhead == 0.5

    def test_get_space_info(self, temp_dir):
        """Test getting space information."""
        manager = SpaceManager()

        space_info = manager.get_space_info(temp_dir)

        assert isinstance(space_info, SpaceInfo)
        assert space_info.path == temp_dir
        assert space_info.total_bytes > 0
        assert space_info.free_bytes > 0
        assert 0 <= space_info.percent_used <= 100

    def test_check_available_space_sufficient(self, temp_dir):
        """Test checking space when sufficient space is available."""
        manager = SpaceManager(min_free_gb=1.0)  # Set low threshold

        # Request 1MB
        required_bytes = 1024 * 1024

        result = manager.check_available_space(
            destination=temp_dir,
            required_bytes=required_bytes,
            include_exports=False
        )

        assert result['sufficient'] is True
        assert 'space_info' in result
        assert 'required_gb' in result
        assert 'available_gb' in result

    def test_check_available_space_with_exports(self, temp_dir):
        """Test checking space with export overhead."""
        manager = SpaceManager(min_free_gb=1.0, export_overhead=0.3)

        required_bytes = 1024 * 1024  # 1MB

        result = manager.check_available_space(
            destination=temp_dir,
            required_bytes=required_bytes,
            include_exports=True
        )

        # Required should include export overhead
        assert result['required_gb'] > (required_bytes / (1024 ** 3))

    def test_check_available_space_insufficient(self, temp_dir):
        """Test checking space when insufficient."""
        manager = SpaceManager(min_free_gb=1000000.0)  # Impossibly high

        required_bytes = 1024 * 1024

        result = manager.check_available_space(
            destination=temp_dir,
            required_bytes=required_bytes,
            include_exports=False
        )

        assert result['sufficient'] is False
        assert 'deficit_gb' in result
        assert result['deficit_gb'] > 0

    def test_check_preflight_success(self, temp_dir):
        """Test pre-flight check with sufficient space."""
        manager = SpaceManager(min_free_gb=1.0)

        # Request 1MB - should pass
        total_source_bytes = 1024 * 1024

        result = manager.check_preflight(
            destination=temp_dir,
            total_source_bytes=total_source_bytes,
            include_exports=False
        )

        assert result is True

    def test_check_preflight_failure(self, temp_dir):
        """Test pre-flight check with insufficient space."""
        manager = SpaceManager(min_free_gb=1000000.0)  # Impossibly high

        total_source_bytes = 1024 * 1024

        with pytest.raises(InsufficientSpaceError) as exc_info:
            manager.check_preflight(
                destination=temp_dir,
                total_source_bytes=total_source_bytes,
                include_exports=False
            )

        assert "Insufficient disk space" in str(exc_info.value)
        assert "Deficit:" in str(exc_info.value)

    def test_is_low_space_false(self, temp_dir):
        """Test low space check when space is sufficient."""
        manager = SpaceManager(min_free_gb=1.0)  # Low threshold

        is_low = manager.is_low_space(temp_dir)

        # Should have more than 1GB free
        assert is_low is False

    def test_is_low_space_true(self, temp_dir):
        """Test low space check when space is low."""
        manager = SpaceManager(min_free_gb=1000000.0)  # Impossibly high

        is_low = manager.is_low_space(temp_dir)

        assert is_low is True

    def test_get_space_warning_message_no_warning(self, temp_dir):
        """Test getting warning message when space is sufficient."""
        manager = SpaceManager(min_free_gb=1.0)

        message = manager.get_space_warning_message(temp_dir)

        assert message is None

    def test_get_space_warning_message_with_warning(self, temp_dir):
        """Test getting warning message when space is low."""
        manager = SpaceManager(min_free_gb=1000000.0)

        message = manager.get_space_warning_message(temp_dir)

        assert message is not None
        assert "Low disk space" in message
        assert "Free:" in message
        assert "Total:" in message

    def test_estimate_space_needed_basic(self):
        """Test estimating space needed without exports."""
        manager = SpaceManager(buffer_percent=10)

        file_sizes = {
            'images': 1024 ** 3,  # 1GB
            'videos': 2 * 1024 ** 3  # 2GB
        }

        estimate = manager.estimate_space_needed(
            file_sizes=file_sizes,
            include_exports=False
        )

        assert estimate['source_size_gb'] == pytest.approx(3.0, rel=0.01)
        assert estimate['export_overhead_gb'] == 0.0
        assert estimate['buffer_gb'] > 0
        assert estimate['total_needed_gb'] > 3.0  # Should include buffer

    def test_estimate_space_needed_with_exports(self):
        """Test estimating space with export overhead."""
        manager = SpaceManager(buffer_percent=10, export_overhead=0.3)

        file_sizes = {
            'images': 1024 ** 3,  # 1GB images
            'videos': 1024 ** 3   # 1GB videos
        }

        estimate = manager.estimate_space_needed(
            file_sizes=file_sizes,
            include_exports=True
        )

        assert estimate['source_size_gb'] == pytest.approx(2.0, rel=0.01)
        # Should have export overhead for images only
        assert estimate['export_overhead_gb'] > 0
        assert estimate['export_overhead_gb'] == pytest.approx(0.3, rel=0.01)
        assert estimate['total_needed_gb'] > 2.3  # Source + exports + buffer

    def test_estimate_space_breakdown(self):
        """Test estimate breakdown."""
        manager = SpaceManager(buffer_percent=10, export_overhead=0.3)

        file_sizes = {'images': 1024 ** 3}

        estimate = manager.estimate_space_needed(
            file_sizes=file_sizes,
            include_exports=True
        )

        assert 'breakdown' in estimate
        assert 'source' in estimate['breakdown']
        assert 'exports' in estimate['breakdown']
        assert 'buffer' in estimate['breakdown']

    def test_format_space_info(self, temp_dir):
        """Test formatting space info."""
        manager = SpaceManager()

        space_info = manager.get_space_info(temp_dir)
        formatted = manager.format_space_info(space_info)

        assert f"Disk Space at {temp_dir}" in formatted
        assert "Total:" in formatted
        assert "Used:" in formatted
        assert "Free:" in formatted
        assert "GB" in formatted

    def test_format_estimate(self):
        """Test formatting space estimate."""
        manager = SpaceManager()

        estimate = {
            'source_size_gb': 10.5,
            'export_overhead_gb': 3.15,
            'buffer_gb': 1.37,
            'total_needed_gb': 15.02
        }

        formatted = manager.format_estimate(estimate)

        assert "Space Estimate:" in formatted
        assert "Source files: 10.50 GB" in formatted
        assert "Export overhead: 3.15 GB" in formatted
        assert "Safety buffer: 1.37 GB" in formatted
        assert "Total needed: 15.02 GB" in formatted

    def test_check_available_space_with_buffer(self, temp_dir):
        """Test that buffer is correctly applied."""
        manager = SpaceManager(min_free_gb=1.0, buffer_percent=20)

        required_bytes = 1024 ** 3  # 1GB

        result = manager.check_available_space(
            destination=temp_dir,
            required_bytes=required_bytes,
            include_exports=False
        )

        # Required should be more than 1GB due to 20% buffer
        assert result['required_gb'] > 1.0
        # Should be approximately 1.2GB (1GB + 20% buffer)
        assert result['required_gb'] == pytest.approx(1.2, rel=0.01)

    def test_multiple_space_checks(self, temp_dir):
        """Test multiple consecutive space checks."""
        manager = SpaceManager(min_free_gb=1.0)

        # First check
        result1 = manager.check_available_space(
            destination=temp_dir,
            required_bytes=1024 * 1024,
            include_exports=False
        )

        # Second check
        result2 = manager.check_available_space(
            destination=temp_dir,
            required_bytes=1024 * 1024 * 2,
            include_exports=False
        )

        # Both should be based on same disk, so free space should be similar
        assert result1['available_gb'] == pytest.approx(result2['available_gb'], rel=0.01)
        # But required should be different
        assert result2['required_gb'] > result1['required_gb']
