# Contributing to FileArchitect

Thank you for your interest in contributing to FileArchitect! This document provides guidelines and instructions for contributing.

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please be respectful and constructive in all interactions.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- Clear, descriptive title
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Screenshots (if applicable)
- Environment details (OS, Python version, FileArchitect version)
- Relevant log files

### Suggesting Features

Feature suggestions are welcome! Please provide:

- Clear description of the feature
- Use case and benefits
- Possible implementation approach
- Any relevant examples or mockups

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Follow the coding style** (see below)
3. **Add tests** for any new functionality
4. **Update documentation** as needed
5. **Ensure all tests pass**
6. **Submit the pull request**

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/filearchitect.git
cd filearchitect

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

## Coding Standards

### Python Style

- Follow PEP 8 style guide
- Use Black for code formatting (line length: 100)
- Use type hints where appropriate
- Write docstrings for all public functions/classes (Google style)

### Code Quality

Before submitting, ensure:

```bash
# Format code
black src/ tests/

# Check linting
pylint src/filearchitect
flake8 src/ tests/

# Type check
mypy src/filearchitect

# Run tests
pytest

# Check coverage
pytest --cov=filearchitect --cov-report=html
```

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in present tense ("Add", "Fix", "Update", "Remove")
- Reference issues when applicable (#123)
- Keep first line under 72 characters

Example:
```
Add preview mode for file organization (#45)

- Implement dry-run functionality
- Add preview window in GUI
- Update CLI with --preview flag
- Add tests for preview mode
```

## Testing

### Writing Tests

- Write unit tests for all new functionality
- Add integration tests for complex workflows
- Use pytest fixtures for common setup
- Aim for >80% code coverage

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_processors.py

# Run with coverage
pytest --cov=filearchitect

# Run parallel
pytest -n auto
```

## Documentation

### Docstrings

Use Google style docstrings:

```python
def process_file(file_path: str, options: dict) -> bool:
    """Process a single file according to options.

    Args:
        file_path: Absolute path to the file to process
        options: Dictionary of processing options

    Returns:
        True if processing succeeded, False otherwise

    Raises:
        FileNotFoundError: If file_path does not exist
        ProcessingError: If processing fails
    """
    pass
```

### User Documentation

- Update user guide for new features
- Add examples and screenshots
- Keep language clear and simple

### Developer Documentation

- Document architecture decisions
- Update API documentation
- Add inline comments for complex logic

## Project Structure

Organize code logically:

- `src/filearchitect/core/` - Core utilities
- `src/filearchitect/processors/` - File type processors
- `src/filearchitect/database/` - Database operations
- `src/filearchitect/config/` - Configuration management
- `src/filearchitect/ui/` - User interfaces
- `src/filearchitect/utils/` - Helper utilities
- `src/filearchitect/smart/` - Smart features

## Git Workflow

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Commit with descriptive messages
4. Push to your fork: `git push origin feature/my-feature`
5. Create a Pull Request

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test improvements

## Review Process

1. Automated checks must pass (tests, linting)
2. At least one maintainer review required
3. Address all review comments
4. Maintainer will merge when approved

## Release Process

Maintainers follow semantic versioning (SemVer):

- MAJOR version for incompatible API changes
- MINOR version for new functionality (backward compatible)
- PATCH version for bug fixes (backward compatible)

## Questions?

Feel free to ask questions by:

- Opening an issue
- Starting a discussion on GitHub Discussions
- Reaching out to maintainers

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to FileArchitect!
