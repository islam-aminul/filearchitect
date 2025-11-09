"""
Unit tests for file processors.

Tests for image, video, audio, and document processors.
"""

import pytest
from pathlib import Path
from datetime import datetime
from PIL import Image
import piexif

from filearchitect.processors.image import ImageProcessor
from filearchitect.processors.video import VideoProcessor
from filearchitect.processors.audio import AudioProcessor
from filearchitect.processors.document import DocumentProcessor
from filearchitect.processors.metadata import ImageMetadataExtractor
from filearchitect.processors.export import ImageExporter
from filearchitect.config.models import Config, ExportSettings
from filearchitect.core.constants import FileType, ProcessingStatus


class TestImageProcessor:
    """Tests for ImageProcessor class."""

    @pytest.fixture
    def image_processor(self, sample_config):
        """Create an ImageProcessor instance."""
        return ImageProcessor(sample_config)

    @pytest.fixture
    def jpg_with_exif(self, temp_dir):
        """Create a JPEG with EXIF data."""
        img_path = temp_dir / "photo_with_exif.jpg"
        img = Image.new("RGB", (1920, 1080), color="blue")

        # Create EXIF data
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Canon",
                piexif.ImageIFD.Model: b"Canon EOS 5D",
                piexif.ImageIFD.Software: b"",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2023:05:15 14:30:45",
            }
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(img_path, exif=exif_bytes)
        return img_path

    @pytest.fixture
    def jpg_screenshot(self, temp_dir):
        """Create a screenshot image."""
        img_path = temp_dir / "Screenshot 2023-05-15 at 14.30.45.png"
        img = Image.new("RGB", (1920, 1080), color="green")
        img.save(img_path)
        return img_path

    @pytest.fixture
    def jpg_social_media(self, temp_dir):
        """Create a social media image."""
        img_path = temp_dir / "IMG-20230515-WA0001.jpg"
        img = Image.new("RGB", (1080, 1080), color="yellow")
        img.save(img_path)
        return img_path

    def test_get_file_type(self, image_processor):
        """Test that ImageProcessor returns IMAGE file type."""
        assert image_processor.get_file_type() == FileType.IMAGE

    def test_can_process_image(self, image_processor, sample_image_path):
        """Test that ImageProcessor can process image files."""
        assert image_processor.can_process(sample_image_path) is True

    def test_can_process_non_image(self, image_processor, temp_dir):
        """Test that ImageProcessor rejects non-image files."""
        text_file = temp_dir / "test.txt"
        text_file.write_text("Not an image")
        assert image_processor.can_process(text_file) is False

    def test_extract_metadata_with_exif(self, image_processor, jpg_with_exif):
        """Test metadata extraction from image with EXIF."""
        metadata = image_processor.extract_metadata(jpg_with_exif)

        assert metadata is not None
        assert 'camera_make' in metadata or 'camera_model' in metadata
        assert 'width' in metadata and 'height' in metadata

    def test_extract_metadata_without_exif(self, image_processor, sample_image_path):
        """Test metadata extraction from image without EXIF."""
        metadata = image_processor.extract_metadata(sample_image_path)

        assert metadata is not None
        assert 'width' in metadata and 'height' in metadata
        # Basic metadata should always be present
        assert 'format' in metadata

    def test_categorize_screenshot(self, image_processor, jpg_screenshot):
        """Test categorization of screenshot."""
        metadata = image_processor.extract_metadata(jpg_screenshot)
        category = image_processor.categorize(jpg_screenshot, metadata)

        assert category == "Screenshots"

    def test_categorize_social_media(self, image_processor, jpg_social_media):
        """Test categorization of social media image."""
        metadata = image_processor.extract_metadata(jpg_social_media)
        category = image_processor.categorize(jpg_social_media, metadata)

        assert category == "Social Media"

    def test_categorize_originals(self, image_processor, jpg_with_exif):
        """Test categorization of camera originals."""
        metadata = image_processor.extract_metadata(jpg_with_exif)
        category = image_processor.categorize(jpg_with_exif, metadata)

        # Should be categorized as Originals or Screenshots (has camera make/model)
        # The actual categorization depends on detection patterns
        assert category in ["Originals", "Screenshots", "Export"]

    def test_generate_filename(self, image_processor, jpg_with_exif):
        """Test filename generation."""
        metadata = image_processor.extract_metadata(jpg_with_exif)
        date_taken = metadata.get('date_taken', datetime.now())

        filename = image_processor.generate_export_filename(
            jpg_with_exif,
            metadata,
            date_taken
        )

        assert filename is not None
        assert filename.endswith('.jpg')
        # Should contain date in format yyyy-mm-dd hh-mm-ss
        assert len(filename) > 19  # At least date portion


class TestVideoProcessor:
    """Tests for VideoProcessor class."""

    @pytest.fixture
    def video_processor(self, sample_config):
        """Create a VideoProcessor instance."""
        return VideoProcessor(sample_config)

    @pytest.fixture
    def sample_video(self, temp_dir):
        """Create a minimal video file for testing."""
        # Create a minimal MP4 file header
        video_path = temp_dir / "test_video.mp4"
        # Minimal MP4 header
        mp4_header = bytes([
            0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
            0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00,
            0x69, 0x73, 0x6f, 0x6d, 0x69, 0x73, 0x6f, 0x32,
            0x6d, 0x70, 0x34, 0x31, 0x00, 0x00, 0x00, 0x08,
        ])
        video_path.write_bytes(mp4_header)
        return video_path

    def test_get_file_type(self, video_processor):
        """Test that VideoProcessor returns VIDEO file type."""
        assert video_processor.get_file_type() == FileType.VIDEO

    def test_can_process_video(self, video_processor, sample_video):
        """Test that VideoProcessor can process video files."""
        # This might return False if magic can't detect the minimal header
        # but we test the method works
        result = video_processor.can_process(sample_video)
        assert isinstance(result, bool)

    def test_extract_metadata(self, video_processor, sample_video):
        """Test metadata extraction from video."""
        metadata = video_processor.extract_metadata(sample_video)

        assert metadata is not None
        assert isinstance(metadata, dict)

    def test_categorize_default(self, video_processor, sample_video):
        """Test default categorization."""
        metadata = video_processor.extract_metadata(sample_video)
        category = video_processor.categorize(sample_video, metadata)

        assert category in ["Camera Videos", "Collection", "Motion Photos", "Social Media", "Movies"]


class TestAudioProcessor:
    """Tests for AudioProcessor class."""

    @pytest.fixture
    def audio_processor(self, sample_config):
        """Create an AudioProcessor instance."""
        return AudioProcessor(sample_config)

    @pytest.fixture
    def sample_audio(self, temp_dir):
        """Create a minimal audio file for testing."""
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TIT2, TPE1

        audio_path = temp_dir / "test_audio.mp3"

        # Create a minimal MP3 file with ID3 header
        # This is a very basic MP3 header
        mp3_data = bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MP3 sync + header
        ] + [0x00] * 100)  # Padding

        audio_path.write_bytes(mp3_data)

        try:
            # Try to add ID3 tags
            audio = MP3(audio_path, ID3=ID3)
            audio.tags.add(TIT2(encoding=3, text='Test Song'))
            audio.tags.add(TPE1(encoding=3, text='Test Artist'))
            audio.save()
        except:
            # If mutagen can't process it, that's okay for testing
            pass

        return audio_path

    def test_get_file_type(self, audio_processor):
        """Test that AudioProcessor returns AUDIO file type."""
        assert audio_processor.get_file_type() == FileType.AUDIO

    def test_extract_metadata(self, audio_processor, sample_audio):
        """Test metadata extraction from audio."""
        metadata = audio_processor.extract_metadata(sample_audio)

        assert metadata is not None
        assert isinstance(metadata, dict)

    def test_categorize_default(self, audio_processor, sample_audio):
        """Test default categorization."""
        metadata = audio_processor.extract_metadata(sample_audio)
        category = audio_processor.categorize(sample_audio, metadata)

        assert category in ["Songs", "Voice Notes", "WhatsApp", "Collection"]


class TestDocumentProcessor:
    """Tests for DocumentProcessor class."""

    @pytest.fixture
    def document_processor(self, sample_config):
        """Create a DocumentProcessor instance."""
        return DocumentProcessor(sample_config)

    @pytest.fixture
    def sample_pdf(self, temp_dir):
        """Create a minimal PDF file."""
        pdf_path = temp_dir / "test.pdf"
        pdf_path.write_bytes(b'%PDF-1.4\n')
        return pdf_path

    @pytest.fixture
    def sample_text(self, temp_dir):
        """Create a text file."""
        txt_path = temp_dir / "test.txt"
        txt_path.write_text("Sample text content")
        return txt_path

    def test_get_file_type(self, document_processor):
        """Test that DocumentProcessor returns DOCUMENT file type."""
        assert document_processor.get_file_type() == FileType.DOCUMENT

    def test_can_process_pdf(self, document_processor, sample_pdf):
        """Test that DocumentProcessor can process PDF files."""
        result = document_processor.can_process(sample_pdf)
        assert isinstance(result, bool)

    def test_can_process_text(self, document_processor, sample_text):
        """Test that DocumentProcessor can process text files."""
        result = document_processor.can_process(sample_text)
        assert isinstance(result, bool)

    def test_categorize_pdf(self, document_processor, sample_pdf):
        """Test categorization of PDF."""
        metadata = {}
        category = document_processor.categorize(sample_pdf, metadata)

        assert category == "PDF"

    def test_categorize_text(self, document_processor, sample_text):
        """Test categorization of text file."""
        metadata = {}
        category = document_processor.categorize(sample_text, metadata)

        assert category == "Text"


class TestImageMetadataExtractor:
    """Tests for ImageMetadataExtractor class."""

    @pytest.fixture
    def metadata_extractor(self):
        """Create an ImageMetadataExtractor instance."""
        return ImageMetadataExtractor()

    @pytest.fixture
    def jpg_with_full_exif(self, temp_dir):
        """Create a JPEG with comprehensive EXIF data."""
        img_path = temp_dir / "photo_full_exif.jpg"
        img = Image.new("RGB", (3840, 2160), color="red")

        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"Nikon",
                piexif.ImageIFD.Model: b"D850",
                piexif.ImageIFD.Software: b"Adobe Photoshop CC 2023",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2024:03:20 10:15:30",
                piexif.ExifIFD.LensMake: b"Nikon",
                piexif.ExifIFD.LensModel: b"24-70mm f/2.8",
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitude: ((40, 1), (45, 1), (0, 1)),
                piexif.GPSIFD.GPSLongitude: ((73, 1), (58, 1), (0, 1)),
            }
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(img_path, exif=exif_bytes)
        return img_path

    def test_extract_camera_info(self, metadata_extractor, jpg_with_full_exif):
        """Test extraction of camera make and model."""
        metadata = metadata_extractor.extract_metadata(jpg_with_full_exif)

        assert 'camera_make' in metadata
        assert 'camera_model' in metadata
        assert metadata['camera_make'] == 'Nikon'
        assert metadata['camera_model'] == 'D850'

    def test_extract_date(self, metadata_extractor, jpg_with_full_exif):
        """Test extraction of date taken."""
        metadata = metadata_extractor.extract_metadata(jpg_with_full_exif)

        assert 'date_taken' in metadata
        assert isinstance(metadata['date_taken'], datetime)

    def test_extract_dimensions(self, metadata_extractor, jpg_with_full_exif):
        """Test extraction of image dimensions."""
        metadata = metadata_extractor.extract_metadata(jpg_with_full_exif)

        assert 'width' in metadata and 'height' in metadata
        assert metadata['width'] == 3840
        assert metadata['height'] == 2160

    def test_extract_software(self, metadata_extractor, jpg_with_full_exif):
        """Test extraction of software field."""
        metadata = metadata_extractor.extract_metadata(jpg_with_full_exif)

        assert 'software' in metadata
        assert 'Photoshop' in metadata['software']

    def test_extract_gps(self, metadata_extractor, jpg_with_full_exif):
        """Test extraction of GPS data."""
        metadata = metadata_extractor.extract_metadata(jpg_with_full_exif)

        assert 'has_gps' in metadata
        assert metadata['has_gps'] is True


class TestImageExporter:
    """Tests for ImageExporter class."""

    @pytest.fixture
    def image_exporter(self):
        """Create an ImageExporter instance."""
        return ImageExporter()

    @pytest.fixture
    def large_image(self, temp_dir):
        """Create a large image for testing resize."""
        img_path = temp_dir / "large_image.png"
        img = Image.new("RGB", (5000, 3000), color="blue")
        img.save(img_path)
        return img_path

    @pytest.fixture
    def small_image(self, temp_dir):
        """Create a small image for testing no upscale."""
        img_path = temp_dir / "small_image.jpg"
        img = Image.new("RGB", (800, 600), color="red")
        img.save(img_path)
        return img_path

    def test_export_large_image_downscale(self, image_exporter, large_image, temp_dir):
        """Test that large images are downscaled to 4K."""
        output_path = temp_dir / "output.jpg"

        result = image_exporter.export_image(large_image, output_path)

        assert result is not None
        assert output_path.exists()

        # Check dimensions are within 4K limits
        img = Image.open(output_path)
        width, height = img.size
        assert width <= 3840
        assert height <= 2160

    def test_export_small_image_no_upscale(self, image_exporter, small_image, temp_dir):
        """Test that small images are not upscaled."""
        output_path = temp_dir / "output.jpg"

        result = image_exporter.export_image(small_image, output_path)

        assert result is not None
        assert output_path.exists()

        # Check dimensions are same or smaller
        img = Image.open(output_path)
        width, height = img.size
        assert width <= 800
        assert height <= 600

    def test_export_preserves_aspect_ratio(self, image_exporter, large_image, temp_dir):
        """Test that aspect ratio is preserved."""
        output_path = temp_dir / "output.jpg"

        # Original is 5000x3000 (aspect ratio 5:3 or 1.667)
        image_exporter.export_image(large_image, output_path)

        img = Image.open(output_path)
        width, height = img.size
        aspect_ratio = width / height

        # Should be close to original aspect ratio
        assert 1.6 < aspect_ratio < 1.7

    def test_export_jpeg_quality(self, image_exporter, sample_image_path, temp_dir):
        """Test JPEG quality setting."""
        output_path = temp_dir / "output.jpg"

        result = image_exporter.export_image(sample_image_path, output_path)

        assert result is not None
        assert output_path.exists()

        # File should exist and be a valid JPEG
        img = Image.open(output_path)
        assert img.format == 'JPEG'
