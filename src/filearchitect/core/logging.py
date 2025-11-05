"""
Logging configuration and utilities for FileArchitect.

This module provides structured logging using structlog with support for
file and console output, log levels, and context-aware logging.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import structlog


def setup_logging(
    log_file: Optional[Path] = None,
    level: str = "INFO",
    verbose: bool = False,
    json_output: bool = False,
) -> None:
    """
    Configure logging for FileArchitect.

    Args:
        log_file: Path to log file. If None, only console logging is enabled
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        verbose: If True, set level to DEBUG and add more context
        json_output: If True, output logs as JSON (useful for machine parsing)
    """
    if verbose:
        level = "DEBUG"

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper()),
        stream=sys.stdout,
    )

    # Add file handler if log_file specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))

        # Use simple format for file logs
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        # Add to root logger
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> Any:
    """
    Get a logger instance for the specified module.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
