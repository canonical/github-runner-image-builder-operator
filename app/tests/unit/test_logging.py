# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for logging module."""

import logging as logging_module
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from github_runner_image_builder import logging
from github_runner_image_builder.logging import configure


@pytest.fixture(autouse=True, name="patched_log_directory")
def patched_log_directory_fixture(tmp_path, monkeypatch):
    """Automatically patch LOG_FILE_DIR to use a temporary directory."""
    monkeypatch.setattr(
        logging, "LOG_FILE_DIR", (log_path := tmp_path / "github-runner-image-builder/log")
    )
    return log_path


@pytest.fixture(autouse=True)
def patched_log_path(patched_log_directory, monkeypatch):
    """Automatically patch LOG_FILE_PATH to use a temporary directory."""
    monkeypatch.setattr(logging, "LOG_FILE_PATH", patched_log_directory / "info.log")


def test_configure_logging_creates_log_directory(patched_log_directory: Path):
    """
    arrange: none.
    act: when logging configure is called.
    assert: log file dir is created.
    """
    configure("INFO")

    patched_log_directory.exists()


def test_configure_logging_uses_formatted_logs(monkeypatch):
    """
    arrange: none.
    act: when logging configure is called.
    assert: log formatter is called with timestamped log format.
    """
    mock_formatter = MagicMock()
    monkeypatch.setattr(logging_module, "Formatter", mock_formatter)
    configure("DEBUG")

    mock_formatter.assert_called_with("%(asctime)s - %(levelname)s - %(message)s")
