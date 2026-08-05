"""Centralized logging configuration for the project.

This module provides a helper function to configure Python's standard logging
module with consistent formatting across all project scripts.

It also loads environment variables from the project's .env file when available.

Pipeline integration:
    A pipeline shell script can create a log file with a unique name and export
    the path via the LOG_FILE_PATH environment variable. Every Python script
    called by that pipeline will then write to the same log file.

Usage:
    from src.logger_config import get_logger

    logger = get_logger(__name__)
    logger.info("This is an info message.")
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv





# -----------------------------------------------------------------------------
# Public logging functions
# -----------------------------------------------------------------------------


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = False,
    log_dir: str = "logs",
    log_filename: Optional[str] = None,
    log_file_path: Optional[str] = None,
) -> None:
    """Configure the root logger for the project.

    Args:
        log_level: Minimum log level to display. Options: DEBUG, INFO, WARNING,
            ERROR, CRITICAL.
        log_to_file: If True, also write logs to a file in the log_dir.
        log_dir: Directory where log files are stored when log_to_file is True.
        log_filename: Name of the log file. If None, a timestamped name is used.
        log_file_path: Full path to an existing log file. When provided, it takes
            precedence over log_dir and log_filename. Useful for pipeline logs.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Determine workspace root relative to this file
    workspace_dir = Path(__file__).resolve().parent.parent

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file_path:
        # Use a log file created and named by a parent pipeline script
        log_file = Path(log_file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="a")
        handlers.append(file_handler)
    elif log_to_file:
        log_path = workspace_dir / log_dir
        log_path.mkdir(parents=True, exist_ok=True)

        if log_filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = f"project_{timestamp}.log"

        file_handler = logging.FileHandler(log_path / log_filename)
        handlers.append(file_handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reset handlers to avoid duplicates if setup_logging is called multiple times
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name.

    If logging has not been explicitly configured, this function applies a
    default configuration using environment variables when available.

    Args:
        name: Usually __name__ from the calling module.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    if not logging.getLogger().handlers:
        workspace_dir = Path(__file__).resolve().parent.parent
        load_dotenv(workspace_dir / ".env")

        log_file_path = os.getenv("LOG_FILE_PATH", "") or None
        log_to_file = log_file_path is not None or os.getenv("LOG_TO_FILE", "false").lower() == "true"
        log_filename = os.getenv("LOG_FILENAME", "") or None

        setup_logging(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_to_file=log_to_file,
            log_dir=os.getenv("LOG_DIR", "logs"),
            log_filename=log_filename,
            log_file_path=log_file_path,
        )

    return logger
