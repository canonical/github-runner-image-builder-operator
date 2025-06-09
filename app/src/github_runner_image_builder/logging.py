# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Configure logging for GitHub runner image builder."""

import logging
import logging.handlers
import pathlib

LOG_FILE_DIR = pathlib.Path.home() / "github-runner-image-builder/log"
LOG_FILE_PATH = LOG_FILE_DIR / "info.log"


def configure(log_level: str | int) -> None:
    """Configure the global log configurations.

    Args:
        log_level: The logging verbosity level to apply.
    """
    LOG_FILE_DIR.mkdir(parents=True, exist_ok=True)
    # use regular file handlers because rotating within chroot environment may crash the program
    log_handler = logging.handlers.WatchedFileHandler(filename=LOG_FILE_PATH, encoding="utf-8")
    log_level_normalized = log_level.upper() if isinstance(log_level, str) else log_level
    log_handler.setLevel(log_level_normalized)
    logging.basicConfig(
        level=log_level_normalized,
        handlers=(log_handler,),
        encoding="utf-8",
    )
