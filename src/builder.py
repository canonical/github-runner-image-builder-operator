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

from exceptions import BuilderSetupError, BuildImageError, ImageBuilderInstallError
from state import BaseImage

logger = logging.getLogger(__name__)


UBUNTU_USER = "ubuntu"

# nosec: B603 is applied across subprocess.run calls since we are calling with predefined
# inputs.


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
    """

    base: BaseImage
    output: Path


IMAGE_NAME_TMPL = "{IMAGE_BASE}-{APP_NAME}-{ARCH}"


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
