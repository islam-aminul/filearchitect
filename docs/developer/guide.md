# FileArchitect Developer Guide

This guide provides information for developers contributing to FileArchitect.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Development Guidelines](#development-guidelines)
4. [Testing Strategy](#testing-strategy)
5. [Adding New Features](#adding-new-features)
6. [Performance Considerations](#performance-considerations)

## Architecture Overview

FileArchitect follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│           User Interface Layer          │
│         (GUI - PyQt6 / CLI - Click)     │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│        Processing Engine Layer          │
│   (Orchestration, Pipeline, Workers)    │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         Processor Layer                 │
│  (Image, Video, Audio, Document)        │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│          Core Services Layer            │
│ (Database, Config, Utils, Logging)      │
└─────────────────────────────────────────┘
```

## Project Structure

```
src/filearchitect/
├── core/               # Core utilities (logging, errors, constants)
├── config/             # Configuration management
├── database/           # Database layer (SQLite)
├── processors/         # File type processors
│   ├── base.py         # Base processor class
│   ├── image.py        # Image processing
│   ├── video.py        # Video processing
│   ├── audio.py        # Audio processing
│   └── document.py     # Document processing
├── ui/                 # User interfaces
│   ├── gui/            # PyQt6 GUI
│   └── cli/            # Click CLI
├── utils/              # Utility functions
└── smart/              # Smart features (inference, clustering)
```

## Development Guidelines

### Coding Standards

1. **Follow PEP 8**: Python style guide
2. **Use Type Hints**: Add type hints to all functions
3. **Write Docstrings**: Use Google style docstrings
4. **Keep Functions Small**: Single Responsibility Principle
5. **Use Meaningful Names**: Clear, descriptive variable and function names

### Example Code Style

```python
from pathlib import Path
from typing import Optional

def process_image(
    image_path: Path,
    output_path: Path,
    quality: int = 85
) -> Optional[Path]:
    """
    Process an image and save to output path.

    Args:
        image_path: Path to input image
        output_path: Path to save processed image
        quality: JPEG quality (1-100)

    Returns:
        Path to processed image, or None if processing failed

    Raises:
        FileNotFoundError: If image_path does not exist
        ValueError: If quality is out of range
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if not 1 <= quality <= 100:
        raise ValueError(f"Quality must be 1-100, got {quality}")

    # Processing logic here...

    return output_path
```

### Error Handling

Always use specific exceptions:

```python
from filearchitect.core.exceptions import (
    FileAccessError,
    FileCorruptedError,
    ProcessingError
)

try:
    process_file(file_path)
except PermissionError as e:
    raise FileAccessError(f"Cannot access {file_path}: {e}")
except ValueError as e:
    raise ProcessingError(f"Invalid file format: {e}")
```

### Logging

Use structured logging:

```python
from filearchitect.core.logging import get_logger

logger = get_logger(__name__)

logger.info("Processing started", file_path=str(file_path))
logger.warning("No EXIF data found", file_path=str(file_path))
logger.error("Processing failed", file_path=str(file_path), error=str(e))
```

## Testing Strategy

### Unit Tests

Test individual functions and classes in isolation:

```python
import pytest
from filearchitect.utils.path import sanitize_filename

def test_sanitize_filename():
    """Test filename sanitization."""
    assert sanitize_filename("file<>?.txt") == "file___.txt"
    assert sanitize_filename("") == "unnamed"
```

### Integration Tests

Test interactions between components:

```python
def test_image_processing_pipeline(temp_dir):
    """Test complete image processing workflow."""
    # Setup
    source = create_test_image(temp_dir / "source.jpg")
    destination = temp_dir / "dest.jpg"

    # Execute
    processor = ImageProcessor()
    result = processor.process(source, destination)

    # Assert
    assert result.success
    assert destination.exists()
```

### Fixtures

Use pytest fixtures for common setup:

```python
@pytest.fixture
def sample_config():
    """Provide test configuration."""
    from filearchitect.config.models import Config
    return Config()

@pytest.fixture
def temp_database(temp_dir):
    """Provide temporary test database."""
    from filearchitect.database.manager import DatabaseManager

    db_path = temp_dir / "test.db"
    db = DatabaseManager(db_path)
    db.initialize()

    yield db

    db.close()
```

## Adding New Features

### 1. Adding a New File Type Processor

1. Create processor class in `processors/`:

```python
# processors/newtype.py
from filearchitect.processors.base import BaseProcessor

class NewTypeProcessor(BaseProcessor):
    """Processor for new file type."""

    def can_process(self, file_path: Path) -> bool:
        """Check if file can be processed."""
        return file_path.suffix.lower() in ['.ext1', '.ext2']

    def process(self, file_path: Path, destination: Path) -> bool:
        """Process the file."""
        # Implementation here
        pass
```

2. Register processor in `processors/__init__.py`:

```python
from filearchitect.processors.newtype import NewTypeProcessor

__all__ = [..., "NewTypeProcessor"]
```

3. Add tests in `tests/unit/test_processors.py`:

```python
def test_newtype_processor():
    """Test new type processor."""
    processor = NewTypeProcessor()
    # Test implementation
```

### 2. Adding Configuration Options

1. Update configuration model in `config/models.py`:

```python
class Config(BaseModel):
    """Main configuration."""

    new_option: str = Field(default="default_value")
    new_section: NewSection = Field(default_factory=NewSection)
```

2. Update configuration loader to handle new fields

3. Add validation if needed

4. Update documentation

### 3. Adding Smart Features

1. Create feature module in `smart/`:

```python
# smart/new_feature.py
from pathlib import Path
from typing import List

def detect_something(files: List[Path]) -> dict:
    """Detect something smart about files."""
    # Implementation
    return result
```

2. Integrate with processing pipeline

3. Add configuration options

4. Add tests

## Performance Considerations

### File I/O Optimization

1. **Use Streaming**: Don't load entire files into memory
2. **Batch Operations**: Process multiple files in batches
3. **Minimize Seeks**: Read files sequentially when possible

```python
# Good: Streaming
def calculate_hash(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open('rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

# Bad: Loading entire file
def calculate_hash_bad(file_path: Path) -> str:
    data = file_path.read_bytes()  # Loads entire file!
    return hashlib.sha256(data).hexdigest()
```

### Database Optimization

1. **Use Indexes**: Index frequently queried columns
2. **Batch Inserts**: Insert multiple records at once
3. **Use Transactions**: Group related operations

```python
# Good: Batch insert
with db.transaction():
    for record in records:
        db.insert(record)

# Bad: Individual commits
for record in records:
    db.insert(record)
    db.commit()  # Slow!
```

### Parallel Processing

1. **Use Thread Pool**: For I/O-bound operations
2. **Limit Threads**: Don't create too many threads
3. **Thread Safety**: Use locks for shared resources

```python
from concurrent.futures import ThreadPoolExecutor

def process_files_parallel(files: List[Path], max_workers: int = 4):
    """Process files in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_file, files)
    return list(results)
```

### Memory Management

1. **Use Generators**: For large collections
2. **Clear Buffers**: After processing each file
3. **Limit Cache Size**: Use LRU cache with size limits

```python
# Good: Generator (memory efficient)
def scan_files(directory: Path):
    """Scan files using generator."""
    for file in directory.rglob("*"):
        if file.is_file():
            yield file

# Bad: List (loads all into memory)
def scan_files_bad(directory: Path):
    return list(directory.rglob("*"))
```

## Profiling

### CPU Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
process_files(files)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Function to profile
    pass
```

## Debugging Tips

1. **Use Logging**: Add detailed logging throughout
2. **Use Debugger**: Set breakpoints in IDE
3. **Check Logs**: Review log files for errors
4. **Test with Small Datasets**: Start small before scaling
5. **Profile Performance**: Identify bottlenecks early

## Resources

- [Python Style Guide (PEP 8)](https://pep8.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [pytest Documentation](https://docs.pytest.org/)
- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Click Documentation](https://click.palletsprojects.com/)

## Getting Help

- Review existing code for examples
- Check the [Architecture Documentation](architecture.md)
- Ask questions in GitHub Discussions
- Read the [Implementation Tasks](../../IMPLEMENTATION_TASKS.md)

---

Happy developing!
