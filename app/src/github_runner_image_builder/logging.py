# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Configure logging for GitHub runner image builder."""

import logging
import logging.handlers
import pathlib

LOG_FILE_DIR = pathlib.Path.home() / "github-runner-image-builder/log"
LOG_FILE_PATH = LOG_FILE_DIR / "info.log"
ERROR_LOG_FILE_PATH = LOG_FILE_DIR / "error.log"


def configure(log_level: str | int) -> None:
    """Configure the global log configurations.

    Args:
        log_level: The logging verbosity level to apply.
    """
    LOG_FILE_DIR.mkdir(parents=True, exist_ok=True)
    # use regular file handlers because rotating within chroot environment may crash the program
    log_handler = logging.FileHandler(filename=LOG_FILE_PATH, encoding="utf-8")
    log_level_normalized = log_level.upper() if isinstance(log_level, str) else log_level
    log_handler.setLevel(log_level_normalized)
    error_log_handler = logging.FileHandler(filename=ERROR_LOG_FILE_PATH, encoding="utf-8")
    logging.basicConfig(
        level=log_level_normalized,
        handlers=(log_handler, error_log_handler),
        encoding="utf-8",
    )
