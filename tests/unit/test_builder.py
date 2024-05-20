# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock

import pytest

import builder
from builder import (
    BuilderSetupError,
    DependencyInstallError,
    ImageBuilderInstallError,
    apt,
    subprocess,
)


def test__install_dependencies_fail(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: monkeypatched subprocess.run function.
    act: when _install_dependencies is called.
    assert: DependencyInstallError is raised.
    """
    monkeypatch.setattr(apt, "add_package", MagicMock())
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "", "error installing deps")),
    )

    with pytest.raises(DependencyInstallError) as exc:
        builder._install_dependencies()

    assert "error installing deps" in str(exc.getrepr())


def test__install_dependencies(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: monkeypatched apt.add_package function.
    act: when _install_dependencies is called.
    assert: mocked functions are called.
    """
    monkeypatch.setattr(apt, "add_package", (apt_mock := MagicMock()))
    monkeypatch.setattr(subprocess, "run", (run_mock := MagicMock()))

    builder._install_dependencies()

    apt_mock.assert_called_once()
    run_mock.assert_called_once()


def test__install_image_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess.run function that raises an error.
    act: when _install_image_builder is called.
    assert: ImageBuilderInstallError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=subprocess.CalledProcessError(
                1, [], "", "error running image builder install"
            )
        ),
    )

    with pytest.raises(ImageBuilderInstallError) as exc:
        builder._install_image_builder()

    assert "error running image builder install" in str(exc.getrepr())


def test_setup_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs that raises an error.
    act: when setup_builder is called.
    assert: BuilderSetupError is raised.
    """
    monkeypatch.setattr(
        builder,
        "_install_image_builder",
        MagicMock(side_effect=ImageBuilderInstallError("Failed to install image builder.")),
    )

    with pytest.raises(BuilderSetupError) as exc:
        builder.setup_builder()

    assert "Failed to install image builder." in str(exc.getrepr())


def test_setup_builder(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched internal funcs.
    act: when setup_builder is called.
    assert: expected mocks are called.
    """
    monkeypatch.setattr(
        builder,
        "_install_dependencies",
        (deps_mock := MagicMock()),
    )
    monkeypatch.setattr(
        builder,
        "_install_image_builder",
        (image_mock := MagicMock()),
    )

    builder.setup_builder()

    deps_mock.assert_called_once()
    image_mock.assert_called_once()
