# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import logging
import os

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
# nosec: B603 is applied across subprocess.run calls since we are calling with predefined
# inputs.
import subprocess  # nosec
from dataclasses import dataclass
from pathlib import Path

import yaml
from charms.operator_libs_linux.v0 import apt
from charms.operator_libs_linux.v1 import systemd

from exceptions import (
    BuilderSetupError,
    DependencyInstallError,
    GetLatestImageError,
    ImageBuilderInitializeError,
)
from state import Arch, BaseImage

logger = logging.getLogger(__name__)


UBUNTU_USER = "ubuntu"
UBUNTU_HOME = Path(f"/home/{UBUNTU_USER}")

APT_DEPENDENCIES = [
    "pipx",
    # Required to build using pipx
    "python3-dev",
    "gcc",
]
CALLBACK_SCRIPT_PATH = UBUNTU_HOME / "on_build_success_callback.sh"
CRON_PATH = Path("/etc/cron.d")
CRON_BUILD_SCHEDULE_PATH = CRON_PATH / "build-runner-image"
GITHUB_RUNNER_IMAGE_BUILDER = UBUNTU_HOME / ".local/bin/github-runner-image-builder"
OPENSTACK_CLOUDS_YAML_PATH = UBUNTU_HOME / "clouds.yaml"
OUTPUT_LOG_PATH = UBUNTU_HOME / "github-runner-image-builder.log"
IMAGE_NAME_TMPL = "{IMAGE_BASE}-{APP_NAME}-{ARCH}"


@dataclass
class BuildConfig:
    """Configurations for running builder periodically.

    Attributes:
        arch: The machine architecture of the image to build with.
        app_name: The charm application name, used to name Openstack image.
        base: Ubuntu OS image to build from.
        cloud_name: The Openstack cloud name to connect to from clouds.yaml.
        num_revisions: Number of images to keep before deletion.
        callback_script: Path to callback script.
    """

    arch: Arch
    base: BaseImage
    cloud_name: str
    num_revisions: int
    callback_script: Path = CALLBACK_SCRIPT_PATH


def setup_builder(build_config: BuildConfig, cloud_config: dict, interval: int) -> None:
    """Configure the host machine to build images.

    Args:
        build_config: Configuration values to register cron to build images periodically.
        cloud_config: The openstack clouds.yaml contents
        interval: The frequency in which the image builder should be triggered.

    Raises:
        BuilderSetupError: If there was an error setting up the host device for building images.
    """
    try:
        _install_dependencies()
        _initialize_image_builder()
        install_clouds_yaml(cloud_config=cloud_config)
        configure_cron(build_config=build_config, interval=interval)
    except (DependencyInstallError, ImageBuilderInitializeError) as exc:
        raise BuilderSetupError from exc


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
                "git+https://github.com/canonical/github-runner-image-builder@feat/app",
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except (apt.PackageNotFoundError, subprocess.CalledProcessError) as exc:
        raise DependencyInstallError from exc


def _initialize_image_builder() -> None:
    """Initialize github-runner-image-builder app.

    Raises:
        ImageBuilderInitializeError: If there was an error Initialize the app.
    """
    try:
        subprocess.run(
            ["/usr/bin/sudo", str(GITHUB_RUNNER_IMAGE_BUILDER), "init"],
            check=True,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
        )  # nosec: B603
    except subprocess.CalledProcessError as exc:
        raise ImageBuilderInitializeError from exc


def install_clouds_yaml(cloud_config: dict) -> None:
    """Install clouds.yaml for Openstack used by the image builder.

    Args:
        cloud_config: The contents of clouds.yaml parsed as dict.
    """
    if not OPENSTACK_CLOUDS_YAML_PATH.exists():
        OPENSTACK_CLOUDS_YAML_PATH.write_text(yaml.safe_dump(cloud_config), encoding="utf-8")
        return
    if yaml.safe_load(OPENSTACK_CLOUDS_YAML_PATH.read_text(encoding="utf-8")) != cloud_config:
        OPENSTACK_CLOUDS_YAML_PATH.write_text(yaml.safe_dump(cloud_config), encoding="utf-8")


def configure_cron(build_config: BuildConfig, interval: int) -> bool:
    """Configure cron to run builder.

    Args:
        build_config: The configuration required to run builder.
        interval: Number of hours in between image build runs.

    Returns:
        True if cron is reconfigured. False otherwise.
    """
    if not _should_configure_cron(
        interval=interval,
        image_base=build_config.base,
        cloud_name=build_config.cloud_name,
        num_revisions=build_config.num_revisions,
    ):
        return False

    builder_exec_command: str = " ".join(
        [
            # HOME path is required for GO modules.
            f"HOME={UBUNTU_HOME}",
            "/usr/bin/run-one",
            "/usr/bin/sudo",
            "--preserve-env",
            str(GITHUB_RUNNER_IMAGE_BUILDER),
            "run",
            build_config.cloud_name,
            IMAGE_NAME_TMPL.format(
                IMAGE_BASE=build_config.base.value,
                APP_NAME=build_config.app_name,
                ARCH=build_config.arch.value,
            ),
            "--base-image",
            build_config.base.value,
            "--keep-revisions",
            str(build_config.num_revisions),
            "--callback-script",
            str(build_config.callback_script),
        ]
    )
    cron_text = (
        f"0 */{interval} * * * {UBUNTU_USER} {builder_exec_command} "
        f">> {OUTPUT_LOG_PATH} 2>&1\n"
    )
    CRON_BUILD_SCHEDULE_PATH.write_text(cron_text, encoding="utf-8")
    systemd.service_restart("cron")
    return True


def _should_configure_cron(
    interval: int, image_base: BaseImage, cloud_name: str, num_revisions: int
) -> bool:
    """Determine whether changes to cron should be applied.

    Args:
        interval: Incoming interval configuration to compare with current.
        image_base: Incoming image_base configuration to compare with current.
        cloud_name: Incoming cloud_name configuration to compare with current.
        num_revisions: Incoming num_revisions configuration to compare with current.

    Returns:
        True if interval has changed. False otherwise.
    """
    if not CRON_BUILD_SCHEDULE_PATH.exists():
        return True

    cron_args = CRON_BUILD_SCHEDULE_PATH.read_text(encoding="utf-8").split()
    installed_interval = int(cron_args[1].split("/")[1])
    installed_cloud_name = cron_args[12]
    installed_image_base = cron_args[15]
    installed_num_revisions = int(cron_args[17])
    return (
        installed_interval != interval
        or installed_image_base != image_base.value
        or installed_cloud_name != cloud_name
        or num_revisions != installed_num_revisions
    )


def build_immediate(config: BuildConfig) -> None:
    """Run a build immediately.

    Args:
        config: The configuration values for running image builder.
    """
    # The callback invotes another hook - which cannot be run when another hook is already running.
    # Call the process as a background and exit immediately.
    subprocess.Popen(  # pylint: disable=consider-using-with
        " ".join(
            [
                # HOME path is required for GO modules.
                f"HOME={UBUNTU_HOME}",
                "/usr/bin/run-one",
                "/usr/bin/sudo",
                "--preserve-env",
                str(GITHUB_RUNNER_IMAGE_BUILDER),
                "run",
                config.cloud_name,
                IMAGE_NAME_TMPL.format(
                    IMAGE_BASE=config.base.value,
                    APP_NAME=config.app_name,
                    ARCH=config.arch.value,
                ),
                "--base-image",
                config.base.value,
                "--keep-revisions",
                str(config.num_revisions),
                "--callback-script",
                str(config.callback_script),
                ">>",
                str(OUTPUT_LOG_PATH),
                "2>&1",
            ]
        ),
        # run as shell for log redirection, the command is trusted
        shell=True,  # nosec: B602
        user=UBUNTU_USER,
        cwd=UBUNTU_HOME,
    )


def get_latest_image(base: BaseImage, app_name: str, arch: Arch, cloud_name: str) -> str:
    """Fetch the latest image build ID.

    Args:
        app_name: The current charm application name.
        arch: The machine architecture the image was built with.
        base: Ubuntu OS image to build from.
        cloud_name: The Openstack cloud name to connect to from clouds.yaml.

    Raises:
        GetLatestImageError: If there was an error fetching the latest image.

    Returns:
        The latest successful image build ID.
    """
    try:
        proc = subprocess.run(
            [
                "/usr/bin/sudo",
                "--preserve-env",
                str(GITHUB_RUNNER_IMAGE_BUILDER),
                "get",
                "--cloud-name",
                cloud_name,
                "--output-image-name",
                IMAGE_NAME_TMPL.format(IMAGE_BASE=base.value, APP_NAME=app_name, ARCH=arch.value),
            ],
            check=True,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
        )  # nosec: B603
        return str(proc.stdout)
    except subprocess.SubprocessError as exc:
        raise GetLatestImageError from exc
