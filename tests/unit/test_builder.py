# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for builder module."""

# Need access to protected functions for testing
# pylint:disable=protected-access

from unittest.mock import MagicMock, _Call, call

import pytest

import builder
from builder import (
    BuilderSetupError,
    BuildImageError,
    DependencyInstallError,
    GitProxyConfigError,
    ImageBuilderInstallError,
    ProxyConfig,
    apt,
    os,
    subprocess,
)


def test__configure_git_proxy_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess.run that raises CalledProcessError.
    act: when _configure_git_proxy is called.
    assert: GitProxyConfigError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(
            side_effect=subprocess.CalledProcessError(1, [], "", "error configuring git proxy")
        ),
    )

    with pytest.raises(GitProxyConfigError) as exc:
        builder._configure_git_proxy(proxy=MagicMock())

    assert "error configuring git proxy" in str(exc.getrepr())


@pytest.mark.parametrize(
    "proxy, expected",
    [
        pytest.param(
            None,
            [
                call(
                    [
                        "/usr/bin/sudo",
                        "/usr/bin/git",
                        "config",
                        "--global",
                        "--unset",
                        "http.proxy",
                    ],
                    check=False,
                    timeout=60,
                ),
                call(
                    [
                        "/usr/bin/sudo",
                        "/usr/bin/git",
                        "config",
                        "--global",
                        "--unset",
                        "https.proxy",
                    ],
                    check=False,
                    timeout=60,
                ),
            ],
            id="Unset proxy",
        ),
        pytest.param(
            ProxyConfig(http="test", https="test", no_proxy="test"),
            [
                call(
                    ["/usr/bin/sudo", "/usr/bin/git", "config", "--global", "http.proxy", "test"],
                    check=True,
                    timeout=60,
                ),
                call(
                    ["/usr/bin/sudo", "/usr/bin/git", "config", "--global", "https.proxy", "test"],
                    check=True,
                    timeout=60,
                ),
            ],
            id="Configure proxy",
        ),
    ],
)
def test__configure_git_proxy(
    monkeypatch: pytest.MonkeyPatch, proxy: ProxyConfig | None, expected: list[_Call]
):
    """
    arrange: given proxy configuration to apply.
    act: when _configure_git_proxy is called.
    assert: expected calls are made.
    """
    monkeypatch.setattr(subprocess, "run", (run_mock := MagicMock()))

    builder._configure_git_proxy(proxy=proxy)

    run_mock.assert_has_calls(expected)


@pytest.mark.parametrize(
    "proxy, env, expected",
    [
        pytest.param(
            None,
            {"HTTP_PROXY": "test", "HTTPS_PROXY": "test", "NO_PROXY": "test"},
            {},
            id="No proxy",
        ),
        pytest.param(
            ProxyConfig(http="test", https="test", no_proxy="test"),
            {},
            {"HTTP_PROXY": "test", "HTTPS_PROXY": "test", "NO_PROXY": "test"},
            id="No proxy",
        ),
    ],
)
def test_configure_proxy(
    monkeypatch: pytest.MonkeyPatch,
    proxy: ProxyConfig | None,
    env: dict[str, str],
    expected: dict[str, str],
):
    """
    arrange: given different proxy configurations.
    act: when configure proxy is called.
    assert: proxy environment variables are set/unset.
    """
    monkeypatch.setattr(builder, "_configure_git_proxy", MagicMock())
    monkeypatch.setattr(os, "environ", env)

    builder.configure_proxy(proxy)

    assert env == expected


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


def test_run_builder_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess.run function that raises an error.
    act: when run_builder is called.
    assert: BuildImageError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, [], "", "Error building image.")),
    )

    with pytest.raises(BuildImageError) as exc:
        builder.run_builder(MagicMock())

    assert "Error building image." in str(exc.getrepr())
