# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for cron module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest

import cron


def test__should_setup_no_file(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a cron schedule file path that doesn't exist yet.
    act: when _should_setup is called.
    assert: Truthy value is returned.
    """
    cron_path_mock = MagicMock()
    cron_path_mock.exists.return_value = False
    monkeypatch.setattr(cron, "BUILD_SCHEDULE_PATH", cron_path_mock)

    assert cron._should_setup(interval=MagicMock())


@pytest.mark.parametrize(
    "cron_contents, interval, expected",
    [
        pytest.param("0 */1 * * * ubuntu /usr/bin/juju-exec", 1, False, id="same cron interval"),
        pytest.param(
            "0 */1 * * * ubuntu /usr/bin/juju-exec", 2, True, id="different cron interval"
        ),
    ],
)
def test__should_setup(
    monkeypatch: pytest.MonkeyPatch, cron_contents: str, interval: int, expected: bool
):
    """
    arrange: given a monkeypatched cron contents.
    act: when _should_setup is called.
    assert: expected value is returned.
    """
    cron_path_mock = MagicMock()
    cron_path_mock.exists.return_value = True
    cron_path_mock.read_text.return_value = cron_contents
    monkeypatch.setattr(cron, "BUILD_SCHEDULE_PATH", cron_path_mock)

    assert cron._should_setup(interval=interval) == expected


def test_setup_no_setup(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched internal _should_setup function that returns False.
    act: when setup is called.
    assert: cron service is not restarted.
    """
    service_restart_mock = MagicMock()
    monkeypatch.setattr(cron, "service_restart", service_restart_mock)
    monkeypatch.setattr(cron, "_should_setup", MagicMock(return_value=False))

    cron.setup(interval=MagicMock())

    service_restart_mock.assert_not_called()


def test_setup_disable_cron(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a cron interval 0 (disable).
    act: when setup is called.
    assert: cron service is restarted and cron file is deleted.
    """
    cron_path_mock = MagicMock()
    monkeypatch.setattr(cron, "BUILD_SCHEDULE_PATH", cron_path_mock)
    service_restart_mock = MagicMock()
    monkeypatch.setattr(cron, "service_restart", service_restart_mock)
    monkeypatch.setattr(cron, "_should_setup", MagicMock(return_value=True))

    cron.setup(interval=0)

    service_restart_mock.assert_called_once()
    cron_path_mock.unlink.assert_called_once()


def test_setup(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a cron interval.
    act: when setup is called.
    assert: cron file is written and service is restarted.
    """
    cron_path_mock = MagicMock()
    monkeypatch.setattr(cron, "BUILD_SCHEDULE_PATH", cron_path_mock)
    service_restart_mock = MagicMock()
    monkeypatch.setattr(cron, "service_restart", service_restart_mock)
    monkeypatch.setattr(cron, "_should_setup", MagicMock(return_value=True))

    cron.setup(interval=1)

    service_restart_mock.assert_called_once()
    cron_path_mock.write_text.assert_called_once()
