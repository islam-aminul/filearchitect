#!/bin/bash
# Development environment setup script for FileArchitect
# This script sets up the development environment on Unix-like systems

set -e

echo "Setting up FileArchitect development environment..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "Python version: $PYTHON_VERSION ✓"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements-dev.txt

# Install package in editable mode
echo "Installing FileArchitect in editable mode..."
pip install -e .

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Check external dependencies
echo ""
echo "Checking external dependencies..."

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "FFmpeg: $(ffmpeg -version | head -n1) ✓"
else
    echo "FFmpeg: NOT FOUND ✗"
    echo "  Install with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
fi

# Check chromaprint
if command -v fpcalc &> /dev/null; then
    echo "chromaprint: $(fpcalc -version) ✓"
else
    echo "chromaprint: NOT FOUND ✗"
    echo "  Install with: brew install chromaprint (macOS) or apt install libchromaprint-tools (Linux)"
fi

# Check libmagic (Linux/macOS only)
if [[ "$OSTYPE" != "win32" ]] && [[ "$OSTYPE" != "msys" ]]; then
    if [ -f "/usr/share/misc/magic.mgc" ] || [ -f "/usr/local/share/misc/magic.mgc" ]; then
        echo "libmagic: FOUND ✓"
    else
        echo "libmagic: NOT FOUND ✗"
        echo "  Install with: brew install libmagic (macOS) or apt install libmagic1 (Linux)"
    fi
fi

echo ""
echo "Development environment setup complete!"
echo ""
echo "To activate the environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
echo "To start development:"
echo "  See docs/developer/guide.md for getting started"
