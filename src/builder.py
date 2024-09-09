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
    UpgradeApplicationError,
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
IMAGE_NAME_TMPL = "{IMAGE_BASE}-{ARCH}"


def initialize(init_config: state.BuilderInitConfig) -> None:
    """Configure the host machine to build images.

    Args:
        init_config: Configuration values required to initialize the builder.

    Raises:
        BuilderSetupError: If there was an error setting up the host device for building images.
    """
    try:
        _install_dependencies(channel=init_config.channel)
        _initialize_image_builder(init_config=init_config)
        install_clouds_yaml(cloud_config=init_config.run_config.cloud_config)
        configure_cron(unit_name=init_config.unit_name, interval=init_config.interval)
    except (DependencyInstallError, ImageBuilderInitializeError) as exc:
        raise BuilderSetupError from exc


def _install_dependencies(channel: state.BuilderAppChannel) -> None:
    """Install required dependencies to run qemu image build.

    Args:
        channel: The application channel to install.

    Raises:
        DependencyInstallError: If there was an error installing apt packages.
    """
    try:
        apt.add_package(APT_DEPENDENCIES, update_cache=True)
        subprocess.run(  # nosec: B603
            [
                "/usr/bin/pipx",
                "install",
                f"git+https://github.com/canonical/github-runner-image-builder@{channel.value}",
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except (apt.PackageNotFoundError, subprocess.SubprocessError) as exc:
        raise DependencyInstallError from exc


def _initialize_image_builder(init_config: state.BuilderInitConfig) -> None:
    """Initialize github-runner-image-builder app.

    Args:
        init_config: Imagebuilder initialization configuration parameters.

    Raises:
        ImageBuilderInitializeError: If there was an error Initialize the app.
    """
    init_cmd = ["/usr/bin/sudo", str(GITHUB_RUNNER_IMAGE_BUILDER_PATH), "init"]
    if init_config.external_build:
        init_cmd += "--experimental-external"
        init_cmd += "True"
        init_cmd += "--cloud-name"
        init_cmd += init_config.run_config.cloud_name
    try:
        subprocess.run(
            init_cmd,
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


def configure_cron(unit_name: str, interval: int) -> bool:
    """Configure cron to run builder.

    Args:
        unit_name: The charm unit name to run cronjob dispatch hook.
        interval: Number of hours in between image build runs.

    Returns:
        True if cron is reconfigured. False otherwise.
    """
    commands = [
        "/usr/bin/run-one",
        "/usr/bin/bash",
        "-c",
        f'/usr/bin/juju-exec "{unit_name}" "JUJU_DISPATCH_PATH=run HOME={UBUNTU_HOME} ./dispatch"',
    ]

    builder_exec_command: str = " ".join(commands)
    cron_text = f"0 */{interval} * * * {UBUNTU_USER} {builder_exec_command}"

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


def run(config: state.BuilderRunConfig) -> str:
    """Run a build immediately.

    Args:
        config: The configuration values for running image builder.

    Raises:
        BuilderRunError: if there was an error while launching the subprocess.

    Returns:
        The built image id.
    """
    try:
        commands = [
            "/usr/bin/run-one",
            "/usr/bin/sudo",
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
        ]
        if config.runner_version:
            commands += ["--runner-version", config.runner_version]
        if config.external_build_config:
            commands += [
                "--experimental-external",
                "True",
                "--flavor",
                config.external_build_config.flavor,
                "--network",
                config.external_build_config.network,
                "--upload-cloud",
                state.UPLOAD_CLOUD_NAME,
            ]
        # The arg "user" exists but pylint disagrees.
        stdout = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg # nosec:B603
            args=commands,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            encoding="utf-8",
            env={"HOME": str(UBUNTU_HOME)},
        )
        if config.external_build_config and "Image build success" not in stdout:
            raise BuilderRunError(f"Unexpected output: {stdout}")
        # The return value of the CLI is "Image build success:\n<image-id>"
        return stdout.split()[-1]
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
        # the user keyword argument exists but pylint doesn't think so.
        image_id = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg
            [
                "/usr/bin/sudo",
                "--preserve-env",
                str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
                "latest-build-id",
                cloud_name,
                IMAGE_NAME_TMPL.format(IMAGE_BASE=base.value, ARCH=arch.value),
            ],
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
            encoding="utf-8",
        )  # nosec: B603
        return image_id
    except subprocess.SubprocessError as exc:
        raise GetLatestImageError from exc


def upgrade_app() -> None:
    """Upgrade the application if newer version is available.

    Raises:
        UpgradeApplicationError: If there was an error upgrading the application.
    """
    try:
        subprocess.run(  # nosec: B603
            [
                "/usr/bin/pipx",
                "upgrade",
                "github-runner-image-builder",
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except subprocess.SubprocessError as exc:
        raise UpgradeApplicationError from exc
