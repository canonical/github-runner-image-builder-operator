# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import logging
import os

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
import subprocess  # nosec
from dataclasses import dataclass
from pathlib import Path

import yaml
from charms.operator_libs_linux.v0 import apt
from charms.operator_libs_linux.v1.systemd import service_restart

from exceptions import (
    BuilderSetupError,
    DependencyInstallError,
    GetLatestImageError,
    ImageBuilderInstallError,
)
from state import Arch, BaseImage

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
CALLBACK_SCRIPT_PATH = Path("propagate_image_id")
CRON_PATH = Path("/etc/cron.d")
CRON_BUILD_SCHEDULE_PATH = CRON_PATH / "build-runner-image"
GITHUB_RUNNER_IMAGE_BUILDER = Path(
    Path(f"/home/{UBUNTU_USER}") / ".local/bin/github-runner-image-builder"
)
OPENSTACK_CLOUDS_YAML_PATH = Path("clouds.yaml")
OPENSTACK_IMAGE_ID_ENV = "OPENSTACK_IMAGE_ID"
IMAGE_NAME_TMPL = "{IMAGE_BASE}-{APP_NAME}-{ARCH}"


@dataclass
class CallbackConfig:
    """Configuration for callback scripts.

    Attributes:
        model_name: Juju model name.
        unit_name: Current juju application unit name.
        charm_dir: Charm directory to trigger the juju hooks.
        hook_name: The Juju hook to call after building image.
    """

    model_name: str
    unit_name: str
    charm_dir: str
    hook_name: str


@dataclass
class CharmMeta:
    """Charm metadata used to create callback script to Juju custom event hook.

    Attributes:
        app_name: The charm application name, used to name Openstack image.
        model_name: The Juju model name, used to trigger juju image build success event.
        unit_name: The juju unit name, used to trigger juju image build success event.
    """

    app_name: str
    model_name: str
    unit_name: str


@dataclass
class RunCronConfig:
    """Configurations for running builder peridocally.

    Attributes:
        arch: The machine architecture of the image to build with.
        base: Ubuntu OS image to build from.
        charm_meta: The charm metadata used to call callback hook.
        cloud_name: The Openstack cloud name to connect to from clouds.yaml.
        interval: The frequency in which the image builder should be triggered.
        num_revisions: Number of images to keep before deletion.
    """

    arch: Arch
    base: BaseImage
    charm_meta: CharmMeta
    cloud_name: str
    interval: int
    num_revisions: int


def setup_builder(
    callback_config: CallbackConfig, cron_config: RunCronConfig, cloud_config: dict
) -> None:
    """Configure the host machine to build images.

    Args:
        callback_config: Configuration values to create callbacks script.
        cron_config: Configuration values to register cron to build images periodically.
        cloud_config: The openstack clouds.yaml contents

    Raises:
        BuilderSetupError: If there was an error setting up the host device for building images.
    """
    try:
        _install_dependencies()
        _create_callback_script(config=callback_config)
        _install_image_builder()
        install_clouds_yaml(cloud_config=cloud_config)
        install_cron(config=cron_config)
    except (DependencyInstallError, ImageBuilderInstallError) as exc:
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
                "git+https://github.com/canonical/github-runner-image-builder@feat/app_openstack",
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except (apt.PackageNotFoundError, subprocess.CalledProcessError) as exc:
        raise DependencyInstallError from exc


def _create_callback_script(config: CallbackConfig) -> None:
    """Create callback script to propagate images.

    Args:
        config: The callback script configuration values.
    """
    cur_env = {
        "JUJU_DISPATCH_PATH": f"hooks/{config.hook_name}",
        "JUJU_MODEL_NAME": config.model_name,
        "JUJU_UNIT_NAME": config.unit_name,
        OPENSTACK_IMAGE_ID_ENV: "$OPENSTACK_IMAGE_ID",
    }
    env = " ".join(f'{key}="{val}"' for (key, val) in cur_env.items())
    script_contents = f"""#! /bin/bash
OPENSTACK_IMAGE_ID="$1"

/usr/bin/juju-exec {config.unit_name} {env} {config.charm_dir}/dispatch
"""
    CALLBACK_SCRIPT_PATH.write_text(script_contents, encoding="utf-8")


def _install_image_builder() -> None:
    """Install github-runner-image-builder app.

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


def install_clouds_yaml(cloud_config: dict) -> None:
    """Install clouds.yaml for Openstack used by the image builder.

    Args:
        cloud_config: The contents of clouds.yaml parsed as dict.
    """
    if not OPENSTACK_CLOUDS_YAML_PATH.exists():
        OPENSTACK_CLOUDS_YAML_PATH.write_text(cloud_config, encoding="utf-8")
        return
    if yaml.safe_load(OPENSTACK_CLOUDS_YAML_PATH.read_text(encoding="utf-8")) != cloud_config:
        OPENSTACK_CLOUDS_YAML_PATH.write_text(cloud_config, encoding="utf-8")


def install_cron(config: RunCronConfig) -> None:
    """Configure cron to run builder.

    Args:
        config: The configuration required to setup cron job to run builder periodically.
    """
    if not _should_configure_cron(
        interval=config.interval,
        image_base=config.base,
        cloud_name=config.cloud_name,
        num_revisions=config.num_revisions,
    ):
        return

    builder_exec_command: str = " ".join(
        [
            # HOME path is required for GO modules.
            f"HOME=/home/{UBUNTU_USER}",
            "/usr/bin/sudo",
            "--preserve-env",
            str(GITHUB_RUNNER_IMAGE_BUILDER),
            "build",
            "--image-base",
            config.base.value,
            "--cloud-name",
            config.cloud_name,
            "--num-revisions",
            str(config.num_revisions),
            "--callback-script-path",
            str(CALLBACK_SCRIPT_PATH),
            "--output-image-name",
            IMAGE_NAME_TMPL.format(
                IMAGE_BASE=config.base.value,
                APP_NAME=config.charm_meta.app_name,
                ARCH=config.arch.value,
            ),
        ]
    )
    cron_text = f"0 */{config.interval} * * * {UBUNTU_USER} {builder_exec_command}\n"
    CRON_BUILD_SCHEDULE_PATH.write_text(cron_text, encoding="utf-8")
    service_restart("cron")


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
    installed_image_base = cron_args[12]
    installed_cloud_name = cron_args[14]
    installed_num_revisions = int(cron_args[16])
    return (
        installed_interval != interval
        or installed_image_base != image_base.value
        or installed_cloud_name != cloud_name
        or num_revisions != installed_num_revisions
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
            timeout=10 * 60,
            env=os.environ,
        )  # nosec: B603
        return str(proc.stdout)
    except subprocess.SubprocessError as exc:
        raise GetLatestImageError from exc
