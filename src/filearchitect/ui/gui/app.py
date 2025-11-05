"""
Main GUI application for FileArchitect.

Entry point for the PyQt6-based graphical user interface.
"""

import sys
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ...core.logging import setup_logging
from ...database.manager import DatabaseManager
from .main_window import MainWindow

logger = logging.getLogger(__name__)


def run_gui():
    """
    Run the GUI application.

    This is the main entry point for the GUI mode.
    """
    # Set up logging
    log_file = Path.home() / '.filearchitect' / 'logs' / 'filearchitect.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    setup_logging(log_file=log_file, level='INFO')

    logger.info("Starting FileArchitect GUI")

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("FileArchitect")
    app.setOrganizationName("FileArchitect")

    # Set application style
    app.setStyle("Fusion")

    try:
        # Initialize database
        db_manager = DatabaseManager.get_instance()
        logger.info("Database initialized")

        # Create and show main window
        window = MainWindow()
        window.show()

        logger.info("Main window shown")

        # Run application
        sys.exit(app.exec())

    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_gui()
