# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import logging
import os

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
# nosec: B603 is applied across subprocess.run calls since we are calling with predefined
# inputs.
import subprocess  # nosec
from pathlib import Path

import yaml
from charms.operator_libs_linux.v0 import apt
from charms.operator_libs_linux.v1 import systemd

import state
from exceptions import (
    BuilderRunError,
    BuilderSetupError,
    DependencyInstallError,
    GetLatestImageError,
    ImageBuilderInitializeError,
)

logger = logging.getLogger(__name__)


UBUNTU_USER = "ubuntu"
UBUNTU_HOME = Path(f"/home/{UBUNTU_USER}")

APT_DEPENDENCIES = [
    "pipx",
    # Required to build github-runner-image-builder using pipx
    "python3-dev",
    "gcc",
]
CRON_PATH = Path("/etc/cron.d")
CRON_BUILD_SCHEDULE_PATH = CRON_PATH / "build-runner-image"
GITHUB_RUNNER_IMAGE_BUILDER_PATH = UBUNTU_HOME / ".local/bin/github-runner-image-builder"
OPENSTACK_CLOUDS_YAML_PATH = UBUNTU_HOME / "clouds.yaml"
OUTPUT_LOG_PATH = UBUNTU_HOME / "github-runner-image-builder.log"
IMAGE_NAME_TMPL = "{IMAGE_BASE}-{ARCH}"


def initialize(init_config: state.BuilderInitConfig) -> None:
    """Configure the host machine to build images.

    Args:
        init_config: Configuration values required to initialize the builder.

    Raises:
        BuilderSetupError: If there was an error setting up the host device for building images.
    """
    try:
        _install_dependencies()
        _initialize_image_builder()
        install_clouds_yaml(cloud_config=init_config.run_config.cloud_config)
        configure_cron(run_config=init_config.run_config, interval=init_config.interval)
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
    except (apt.PackageNotFoundError, subprocess.SubprocessError) as exc:
        raise DependencyInstallError from exc


def _initialize_image_builder() -> None:
    """Initialize github-runner-image-builder app.

    Raises:
        ImageBuilderInitializeError: If there was an error Initialize the app.
    """
    try:
        subprocess.run(
            ["/usr/bin/sudo", str(GITHUB_RUNNER_IMAGE_BUILDER_PATH), "init"],
            check=True,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
        )  # nosec: B603
    except subprocess.SubprocessError as exc:
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


def configure_cron(run_config: state.BuilderRunConfig, interval: int) -> bool:
    """Configure cron to run builder.

    Args:
        run_config: The configuration required to run builder.
        interval: Number of hours in between image build runs.

    Returns:
        True if cron is reconfigured. False otherwise.
    """
    builder_exec_command: str = " ".join(
        [
            # HOME path is required for GO modules.
            f"HOME={UBUNTU_HOME}",
            "/usr/bin/run-one",
            "/usr/bin/sudo",
            "--preserve-env",
            str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
            "run",
            run_config.cloud_name,
            IMAGE_NAME_TMPL.format(
                IMAGE_BASE=run_config.base.value,
                ARCH=run_config.arch.value,
            ),
            "--base-image",
            run_config.base.value,
            "--keep-revisions",
            str(run_config.num_revisions),
            "--callback-script",
            str(run_config.callback_script),
        ]
    )
    cron_text = (
        f"0 */{interval} * * * {UBUNTU_USER} {builder_exec_command} "
        f">> {OUTPUT_LOG_PATH} 2>&1\n"
    )

    if not _should_configure_cron(cron_contents=cron_text):
        return False

    CRON_BUILD_SCHEDULE_PATH.write_text(cron_text, encoding="utf-8")
    systemd.service_restart("cron")
    return True


def _should_configure_cron(cron_contents: str) -> bool:
    """Determine whether changes to cron should be applied.

    Args:
        cron_contents: Latest cronfile contents to be applied.

    Returns:
        True if interval has changed. False otherwise.
    """
    if not CRON_BUILD_SCHEDULE_PATH.exists():
        return True

    return cron_contents != CRON_BUILD_SCHEDULE_PATH.read_text(encoding="utf-8")


def run(config: state.BuilderRunConfig) -> None:
    """Run a build immediately.

    Args:
        config: The configuration values for running image builder.

    Raises:
        BuilderRunError: if there was an error while launching the subprocess.
    """
    try:
        # The callback invotes another hook - which cannot be run when another hook is already
        # running. Call the process as a background and exit immediately.
        subprocess.Popen(  # pylint: disable=consider-using-with
            " ".join(
                [
                    # HOME path is required for GO modules.
                    f"HOME={UBUNTU_HOME}",
                    "/usr/bin/run-one",
                    "/usr/bin/sudo",
                    "--preserve-env",
                    str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
                    "run",
                    config.cloud_name,
                    IMAGE_NAME_TMPL.format(
                        IMAGE_BASE=config.base.value,
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
                    "||",
                    # Run the callback script without Openstack ID argument to let the charm know
                    # about the error.
                    str(config.callback_script),
                    "&",
                ]
            ),
            # run as shell for log redirection, the command is trusted
            shell=True,  # nosec: B602
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            env={},
        )
    except subprocess.SubprocessError as exc:
        raise BuilderRunError from exc


def get_latest_image(arch: state.Arch, base: state.BaseImage, cloud_name: str) -> str:
    """Fetch the latest image build ID.

    Args:
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
                str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
                "latest-build-id",
                cloud_name,
                IMAGE_NAME_TMPL.format(IMAGE_BASE=base.value, ARCH=arch.value),
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
