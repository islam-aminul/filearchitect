# FileArchitect

**Intelligent file organization and deduplication tool for personal media collections**

FileArchitect is a cross-platform application that helps you organize, deduplicate, and manage your personal media files (images, videos, audio, documents) from multiple backup sources into a well-structured destination storage.

## Features

- **Intelligent Categorization**: Automatically categorizes files by type, camera, date, and more
- **Smart Deduplication**: Content-based duplicate detection to save storage space
- **Image Export**: Convert and resize images to standardized JPEG format at 4K resolution
- **Metadata Enhancement**: Enrich audio files with metadata from MusicBrainz
- **Preview Mode**: Dry-run to see what will happen before processing
- **Undo Support**: Roll back organization sessions if needed
- **Resume Capability**: Pause and resume long-running operations
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Dual Interface**: Both GUI and CLI modes available

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/filearchitect/filearchitect.git
cd filearchitect

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### External Dependencies

FileArchitect requires some external tools to be installed:

**FFmpeg** (for video processing):
- Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

**chromaprint** (for audio fingerprinting):
- Windows: Download from [acoustid.org](https://acoustid.org/chromaprint)
- macOS: `brew install chromaprint`
- Linux: `sudo apt install libchromaprint-tools`

**libmagic** (for file type detection):
- Windows: Included via python-magic-bin
- macOS: `brew install libmagic`
- Linux: `sudo apt install libmagic1`

### Usage

**GUI Mode:**
```bash
filearchitect-gui
```

**CLI Mode:**
```bash
# Basic usage
filearchitect --source /path/to/source --destination /path/to/destination

# Preview mode (dry-run)
filearchitect --source /path/to/source --destination /path/to/destination --preview

# Resume previous session
filearchitect --source /path/to/source --destination /path/to/destination --resume

# Verbose output
filearchitect --source /path/to/source --destination /path/to/destination --verbose
```

## Project Structure

```
filearchitect/
├── src/filearchitect/          # Main source code
│   ├── core/                   # Core utilities (logging, errors, etc.)
│   ├── processors/             # File type processors
│   ├── database/               # Database layer
│   ├── config/                 # Configuration management
│   ├── ui/                     # User interfaces
│   │   ├── gui/                # PyQt6 GUI
│   │   └── cli/                # Click CLI
│   ├── utils/                  # Utility modules
│   └── smart/                  # Smart features (inference, clustering)
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── fixtures/               # Test fixtures
├── docs/                       # Documentation
│   ├── user/                   # User documentation
│   ├── developer/              # Developer documentation
│   └── api/                    # API documentation
├── scripts/                    # Build and utility scripts
├── resources/                  # Application resources
└── build/                      # Build artifacts
```

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run tests with coverage
pytest --cov=filearchitect --cov-report=html

# Format code
black src/ tests/

# Lint code
pylint src/filearchitect
flake8 src/ tests/

# Type check
mypy src/filearchitect
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_core.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=filearchitect --cov-report=html

# Run parallel tests
pytest -n auto
```

### Building

```bash
# Build wheel
python -m build

# Build executable (PyInstaller)
python scripts/build.py
```

## Documentation

- [User Guide](docs/user/guide.md)
- [API Documentation](docs/api/)
- [Developer Guide](docs/developer/guide.md)
- [Architecture](docs/developer/architecture.md)

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Python and PyQt6
- Uses FFmpeg for video processing
- Uses AcoustID and MusicBrainz for audio metadata
- Inspired by the need to organize decades of personal media

## Support

- Documentation: [https://filearchitect.readthedocs.io](https://filearchitect.readthedocs.io)
- Issues: [GitHub Issues](https://github.com/filearchitect/filearchitect/issues)
- Discussions: [GitHub Discussions](https://github.com/filearchitect/filearchitect/discussions)

## Roadmap

See [IMPLEMENTATION_TASKS.md](../IMPLEMENTATION_TASKS.md) for the complete development roadmap.

### Version 1.0 (In Development)
- Core file organization and deduplication
- Image, video, audio, and document processing
- GUI and CLI interfaces
- Preview and undo functionality
- Smart features (date inference, similar file detection)
- Comprehensive reporting

### Future Versions
- Cloud storage integration
- Face recognition
- Real-time folder monitoring
- Plugin system
- Advanced analytics

---

**FileArchitect** - Organize your memories, preserve your history.
