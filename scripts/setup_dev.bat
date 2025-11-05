@echo off
REM Development environment setup script for FileArchitect (Windows)

echo Setting up FileArchitect development environment...

REM Check Python version
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements-dev.txt

REM Install package in editable mode
echo Installing FileArchitect in editable mode...
pip install -e .

REM Install pre-commit hooks
echo Installing pre-commit hooks...
pre-commit install

echo.
echo Checking external dependencies...

REM Check FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% equ 0 (
    echo FFmpeg: FOUND
) else (
    echo FFmpeg: NOT FOUND
    echo   Download from: https://ffmpeg.org/download.html
)

REM Check chromaprint
where fpcalc >nul 2>&1
if %errorlevel% equ 0 (
    echo chromaprint: FOUND
) else (
    echo chromaprint: NOT FOUND
    echo   Download from: https://acoustid.org/chromaprint
)

echo.
echo Development environment setup complete!
echo.
echo To activate the environment, run:
echo   venv\Scripts\activate.bat
echo.
echo To run tests:
echo   pytest
echo.
echo To start development:
echo   See docs\developer\guide.md for getting started

pause
