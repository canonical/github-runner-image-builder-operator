# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import logging
import os

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
import subprocess  # nosec
from dataclasses import dataclass
from pathlib import Path

from charms.operator_libs_linux.v0 import apt

from exceptions import GitProxyConfigError
from state import BaseImage, ProxyConfig

logger = logging.getLogger(__name__)

HTTP_PROXY = "HTTP_PROXY"
HTTPS_PROXY = "HTTPS_PROXY"
NO_PROXY = "NO_PROXY"

UBUNTU_USER = "ubuntu"

# nosec: B603 is applied across subprocess.run calls since we are calling with predefined
# inputs.


def _configure_git_proxy(proxy: ProxyConfig | None) -> None:
    """Configure proxy for git.

    Args:
        proxy: The charm proxy configuration.

    Raises:
        GitProxyConfigError: If there was an error configuring git proxy.
    """
    try:
        if not proxy:
            # Git config unset call is not idempotent, hence check=False
            subprocess.run(  # nosec: B603
                ["/usr/bin/sudo", "/usr/bin/git", "config", "--global", "--unset", "http.proxy"],
                check=False,
                timeout=60,
                user=UBUNTU_USER,
            )
            subprocess.run(  # nosec: B603
                ["/usr/bin/sudo", "/usr/bin/git", "config", "--global", "--unset", "https.proxy"],
                check=False,
                timeout=60,
                user=UBUNTU_USER,
            )
            return
        subprocess.run(  # nosec: B603
            ["/usr/bin/sudo", "/usr/bin/git", "config", "--global", "http.proxy", proxy.http],
            check=True,
            timeout=60,
            user=UBUNTU_USER,
        )
        subprocess.run(  # nosec: B603
            ["/usr/bin/sudo", "/usr/bin/git", "config", "--global", "https.proxy", proxy.https],
            check=True,
            timeout=60,
            user=UBUNTU_USER,
        )
    except subprocess.CalledProcessError as exc:
        raise GitProxyConfigError from exc


def configure_proxy(proxy: ProxyConfig | None) -> None:
    """Enable proxy configurations on the charm environment.

    Sets up proxy for apt.
    Sets up HTTP(S)_PROXY environment variable.

    Args:
        proxy: The charm proxy configuration.
    """
    _configure_git_proxy(proxy=proxy)
    if not proxy:
        os.environ.pop(HTTP_PROXY, None)
        os.environ.pop(HTTPS_PROXY, None)
        os.environ.pop(NO_PROXY, None)
        # go proxy variables are in lowercase
        os.environ.pop(HTTP_PROXY.lower(), None)
        os.environ.pop(HTTPS_PROXY.lower(), None)
        os.environ.pop(NO_PROXY.lower(), None)
        return
    os.environ[HTTP_PROXY] = proxy.http
    os.environ[HTTPS_PROXY] = proxy.https
    os.environ[NO_PROXY] = proxy.no_proxy
    os.environ[HTTP_PROXY.lower()] = proxy.http
    os.environ[HTTPS_PROXY.lower()] = proxy.https
    os.environ[NO_PROXY.lower()] = proxy.no_proxy


APT_DEPENDENCIES = [
    "pipx",
    # Required to build using pipx
    "python3-dev",
    "gcc",
]


# nosec: B603: All subprocess runs are run with trusted executables.
class DependencyInstallError(Exception):
    """Represents an error while installing required dependencies."""


def _install_dependencies() -> None:
    """Install required dependencies to run qemu image build.

    Raises:
        DependencyInstallError: If there was an error installing apt packages.
    """
    try:
        apt.add_package(APT_DEPENDENCIES, update_cache=True)
        subprocess.run(  # nosec: B603
            [
                "/usr/bin/pipx",
                "install",
                "git+https://github.com/canonical/github-runner-image-builder@chore/timeout",
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except (apt.PackageNotFoundError, subprocess.CalledProcessError) as exc:
        raise DependencyInstallError from exc


GITHUB_RUNNER_IMAGE_BUILDER = Path(
    Path(f"/home/{UBUNTU_USER}") / ".local/bin/github-runner-image-builder"
)


class ImageBuilderInstallError(Exception):
    """Represents an error while installing github-runner-image-builder app."""


def _install_image_builder() -> None:
    """Install github-runner-image-builder app..

    Raises:
        ImageBuilderInstallError: If there was an error installing the app.
    """
    try:
        subprocess.run(
            ["/usr/bin/sudo", str(GITHUB_RUNNER_IMAGE_BUILDER), "install"],
            check=True,
            user=UBUNTU_USER,
            timeout=10 * 60,
            env=os.environ,
        )  # nosec: B603
    except subprocess.CalledProcessError as exc:
        raise ImageBuilderInstallError from exc


class BuilderSetupError(Exception):
    """Represents an error while setting up host machine as builder."""


def setup_builder() -> None:
    """Configure the host machine to build images.

    Raises:
        BuilderSetupError: If there was an error setting up the host device for building images.
    """
    try:
        _install_dependencies()
        _install_image_builder()
    except (DependencyInstallError, ImageBuilderInstallError) as exc:
        raise BuilderSetupError from exc


@dataclass
class RunBuilderConfig:
    """Configurations for building a runner.

    Attributes:
        base: Ubuntu OS image to build from.
        output: The Image output Path.
        proxy: The proxy to use when building image.
    """

    base: BaseImage
    output: Path
    proxy: str


IMAGE_NAME_TMPL = "{IMAGE_BASE}-{APP_NAME}-{ARCH}"


class BuildImageError(Exception):
    """Represents an error while buildling an image."""


def run_builder(config: RunBuilderConfig) -> None:
    """Run builder and write image to output path.

    Args:
        config: The builder run arguments.

    Raises:
        BuildImageError: if there was an error running the github-runner-image-builder.
    """
    try:
        # Go mod requires HOME env var to locate GOPATH and GOMODCACHE
        subprocess.run(  # nosec: B603
            [
                "/usr/bin/sudo",
                "--preserve-env",
                str(GITHUB_RUNNER_IMAGE_BUILDER),
                "build",
                "--image-base",
                config.base.value,
                "--output",
                str(config.output),
            ],
            encoding="utf-8",
            check=True,
            user=UBUNTU_USER,
            timeout=60 * 60,
            env={**os.environ, "HOME": f"/home/{UBUNTU_USER}"},
        )
    except subprocess.CalledProcessError as exc:
        raise BuildImageError from exc
