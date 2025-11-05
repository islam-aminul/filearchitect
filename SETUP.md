# FileArchitect - Development Setup Guide

This guide will help you set up your development environment for FileArchitect.

## Prerequisites

### Required Software

1. **Python 3.11 or higher**
   - Download from: https://www.python.org/downloads/
   - Verify installation: `python3 --version` (or `python --version` on Windows)

2. **Git**
   - Download from: https://git-scm.com/downloads
   - Verify installation: `git --version`

### External Dependencies

FileArchitect requires several external tools for full functionality:

#### FFmpeg (Required for video processing)

**Windows:**
1. Download from: https://ffmpeg.org/download.html
2. Extract to a directory (e.g., `C:\ffmpeg`)
3. Add `C:\ffmpeg\bin` to your PATH environment variable

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Verification:**
```bash
ffmpeg -version
```

#### chromaprint/fpcalc (Required for audio fingerprinting)

**Windows:**
1. Download from: https://acoustid.org/chromaprint
2. Extract `fpcalc.exe` to a directory in your PATH

**macOS:**
```bash
brew install chromaprint
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install libchromaprint-tools
```

**Verification:**
```bash
fpcalc -version
```

#### libmagic (Required for file type detection on Linux/macOS)

**macOS:**
```bash
brew install libmagic
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install libmagic1
```

**Windows:**
Automatically installed via `python-magic-bin` package.

## Quick Setup

### Automatic Setup (Recommended)

**Unix-like systems (macOS, Linux):**
```bash
cd filearchitect
chmod +x scripts/setup_dev.sh
./scripts/setup_dev.sh
```

**Windows:**
```cmd
cd filearchitect
scripts\setup_dev.bat
```

The setup script will:
- Create a virtual environment
- Install all Python dependencies
- Install the package in editable mode
- Set up pre-commit hooks
- Check for external dependencies

### Manual Setup

If you prefer manual setup or the automatic script fails:

1. **Clone the repository:**
```bash
git clone https://github.com/filearchitect/filearchitect.git
cd filearchitect
```

2. **Create virtual environment:**
```bash
# Unix-like systems
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate.bat
```

3. **Upgrade pip:**
```bash
pip install --upgrade pip
```

4. **Install dependencies:**
```bash
# Development dependencies (includes all runtime dependencies)
pip install -r requirements-dev.txt

# Or just runtime dependencies
pip install -r requirements.txt
```

5. **Install package in editable mode:**
```bash
pip install -e .
```

6. **Install pre-commit hooks:**
```bash
pre-commit install
```

## Verifying Installation

### Run Tests

```bash
# Activate virtual environment first
source venv/bin/activate  # Unix
# or
venv\Scripts\activate.bat  # Windows

# Run all tests
pytest

# Run with coverage
pytest --cov=filearchitect --cov-report=html

# View coverage report
# Open htmlcov/index.html in a browser
```

### Check Code Quality

```bash
# Format code
black src/ tests/

# Check linting
flake8 src/ tests/
pylint src/filearchitect

# Type checking
mypy src/filearchitect
```

### Try the CLI

```bash
# Check version
filearchitect --version

# Show help
filearchitect --help
```

### Try the GUI

```bash
filearchitect-gui
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-feature
```

### 2. Make Changes

Edit files, add features, fix bugs...

### 3. Run Tests

```bash
pytest
```

### 4. Format and Lint

```bash
black src/ tests/
flake8 src/ tests/
mypy src/filearchitect
```

Pre-commit hooks will automatically run these checks when you commit.

### 5. Commit Changes

```bash
git add .
git commit -m "Add my feature"
```

### 6. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- GitLens

Add to `.vscode/settings.json`:
```json
{
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--line-length=100"],
  "editor.formatOnSave": true,
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false
}
```

### PyCharm

1. Open the project
2. Set Python interpreter to the virtual environment
3. Enable pytest as test runner
4. Configure Black as external tool
5. Enable type checking

## Troubleshooting

### Virtual Environment Issues

**Problem:** `venv/bin/activate` not found

**Solution:** Ensure you created the virtual environment:
```bash
python3 -m venv venv
```

### Dependency Installation Fails

**Problem:** Some packages fail to install

**Solution:**
1. Ensure you have the latest pip: `pip install --upgrade pip`
2. On Linux, you may need development headers:
   ```bash
   sudo apt install python3-dev build-essential
   ```
3. For specific package issues, check the package documentation

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'filearchitect'`

**Solution:** Install in editable mode:
```bash
pip install -e .
```

### FFmpeg/chromaprint Not Found

**Problem:** Tests fail with FFmpeg/chromaprint errors

**Solution:** Install external dependencies (see Prerequisites section)

### Permission Errors (macOS/Linux)

**Problem:** Permission denied when running scripts

**Solution:** Make script executable:
```bash
chmod +x scripts/setup_dev.sh
```

### Windows Long Path Issues

**Problem:** Files with long paths fail

**Solution:** Enable long path support:
1. Run `regedit`
2. Navigate to: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem`
3. Set `LongPathsEnabled` to `1`
4. Restart computer

## Next Steps

1. Read the [Developer Guide](docs/developer/guide.md)
2. Review the [Architecture Documentation](docs/developer/architecture.md)
3. Check the [Implementation Tasks](IMPLEMENTATION_TASKS.md)
4. Look at the [Contributing Guidelines](CONTRIBUTING.md)

## Getting Help

- Check existing [Issues](https://github.com/filearchitect/filearchitect/issues)
- Start a [Discussion](https://github.com/filearchitect/filearchitect/discussions)
- Read the [Documentation](docs/)

---

Happy coding! 🚀
