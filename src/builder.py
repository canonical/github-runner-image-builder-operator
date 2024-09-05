# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import dataclasses
import logging
import multiprocessing
import os

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
# nosec: B603 is applied across subprocess.run calls since we are calling with predefined
# inputs.
import subprocess  # nosec
import typing
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
    init_cmd = [
        "/usr/bin/sudo",
        str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
        "init",
        "--experimental-external",
        "--cloud-name",
        init_config.run_config.cloud_name,
    ]
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


@dataclasses.dataclass
class _CloudConfig:
    """The cloud configuration values for image building.

    Attributes:
        build_cloud: The name of the cloud to build the image on.
        upload_cloud: The name of the cloud to upload thee image to.
        flavor: The name of the flavor to launch to VM with.
        network: The name of the network to launch the builder VMs on.
    """

    build_cloud: str
    upload_cloud: str
    flavor: str
    network: str


@dataclasses.dataclass
class BuildConfig:
    """The image build configuration.

    Attributes:
        arch: The architecture to build the image for.
        base: The ubuntu OS base to build.
        cloud_config: Cloud configuration values for launching a builder VM.
        num_revisions: The number or revisions to keep before deleting old images.
        runner_version: The GitHub actions-runner version.
    """

    arch: state.Arch
    base: state.BaseImage
    cloud_config: _CloudConfig
    num_revisions: int
    runner_version: str | None


@dataclasses.dataclass
class BuildResult:
    """Build result wrapper.

    Attributes:
        config: The configuration values used to run build.
        id: The output image id.
    """

    config: BuildConfig
    id: str


def run(config: state.BuilderRunConfig) -> list[BuildResult]:
    """Run a build immediately.

    Args:
        config: The configuration values for running image builder.

    Returns:
        The built image results.
    """
    build_configs = _parametrize_build(
        arch=config.arch,
        bases=config.bases,
        cloud_config=_CloudConfig(
            build_cloud=config.cloud_name,
            upload_cloud=config.upload_cloud_name,
            flavor=config.external_build_config.flavor,
            network=config.external_build_config.network,
        ),
        num_revisions=config.num_revisions,
        runner_version=config.runner_version,
    )
    with multiprocessing.Pool(processes=len(build_configs)) as pool:
        results = pool.map(_run_build, build_configs)
    return results


def _parametrize_build(
    arch: state.Arch,
    bases: typing.Iterable[state.BaseImage],
    cloud_config: _CloudConfig,
    num_revisions: int,
    runner_version: str | None,
) -> tuple[BuildConfig, ...]:
    """Get parametrized build configurations.

    Args:
        arch: The target image architecture to build for.
        bases: The ubuntu OS bases to build for.
        cloud_config: The cloud configuration for building and uploading images.
        num_revisions: The number or revisions to keep before deleting old images.
        runner_version: The GitHub actions-runner version.

    Returns:
        Per image build configuration values.
    """
    return tuple(
        BuildConfig(
            arch=arch,
            base=base,
            cloud_config=cloud_config,
            num_revisions=num_revisions,
            runner_version=runner_version,
        )
        for base in bases
    )


def _run_build(config: BuildConfig) -> BuildResult:
    """Spawn a single build process.

    Args:
        config: The build configuration parameters.

    Raises:
        BuilderRunError: if there was an error while running the build subprocess.

    Returns:
        The build result with build configuration data and output image ID.
    """
    try:
        commands = [
            "/usr/bin/run-one",
            "/usr/bin/sudo",
            str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
            "run",
            config.cloud_config.build_cloud,
            _format_image_name(arch=config.arch, base=config.base),
            "--base-image",
            config.base.value,
            "--keep-revisions",
            str(config.num_revisions),
        ]
        if config.runner_version:
            commands += ["--runner-version", config.runner_version]
        commands += [
            "--experimental-external",
            "True",
            "--flavor",
            config.cloud_config.flavor,
            "--network",
            config.cloud_config.network,
            "--upload-cloud",
            config.cloud_config.upload_cloud,
        ]
        # The arg "user" exists but pylint disagrees.
        return BuildResult(
            config=config,
            id=subprocess.check_output(  # pylint: disable=unexpected-keyword-arg # nosec:B603
                args=commands,
                user=UBUNTU_USER,
                cwd=UBUNTU_HOME,
                encoding="utf-8",
                env={"HOME": str(UBUNTU_HOME)},
            ),
        )
    except subprocess.SubprocessError as exc:
        raise BuilderRunError from exc


def _format_image_name(arch: state.Arch, base: state.BaseImage) -> str:
    """Create image name based on build configuration parameters.

    Args:
        arch: The architecture to build for.
        base: The Ubuntu OS base image.

    Returns:
        The formatted image name.
    """
    return f"{base.value}-{arch.value}"


@dataclasses.dataclass
class GetLatestImageConfig:
    """Configurations for fetching latest built images.

    Attributes:
        arch: The architecture of the image to fetch.
        base: The Ubuntu OS base image.
        cloud_name: The cloud to fetch the image from.
    """

    arch: state.Arch
    base: state.BaseImage
    cloud_name: str


@dataclasses.dataclass
class GetLatestImageResult:
    """Get latest image wrapper.

    Attributes:
        id: The image ID.
        config: Configuration used to fetch the image.
    """

    id: str
    config: GetLatestImageConfig


def get_latest_image(
    arch: state.Arch, bases: typing.Iterable[state.BaseImage], cloud_name: str
) -> list[GetLatestImageResult]:
    """Fetch the latest image build ID.

    Args:
        arch: The machine architecture the image was built with.
        bases: Ubuntu OS images the image was built on.
        cloud_name: The Openstack cloud name to connect to from clouds.yaml.

    Returns:
        List of get latest image results.
    """
    get_image_configs = _parametrize_get_latest_image(
        arch=arch, bases=bases, cloud_name=cloud_name
    )
    with multiprocessing.Pool(processes=len(get_image_configs)) as pool:
        results = pool.map(_run_get_latest_image, get_image_configs)
    return results


def _run_get_latest_image(get_config: GetLatestImageConfig) -> GetLatestImageResult:
    """Get the latest image.

    Args:
        get_config: Get the latest image.

    Raises:
        GetLatestImageError: If there was an error fetching the latest image.

    Returns:
        The latest successful image build ID with get image configuration values.
    """
    try:
        # the user keyword argument exists but pylint doesn't think so.
        image_id = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg
            [
                "/usr/bin/sudo",
                "--preserve-env",
                str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
                "latest-build-id",
                get_config.cloud_name,
                IMAGE_NAME_TMPL.format(
                    IMAGE_BASE=get_config.base.value, ARCH=get_config.arch.value
                ),
            ],
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
            encoding="utf-8",
        )  # nosec: B603
        return GetLatestImageResult(id=image_id, config=get_config)
    except subprocess.SubprocessError as exc:
        raise GetLatestImageError from exc


def _parametrize_get_latest_image(
    arch: state.Arch, bases: typing.Iterable[state.BaseImage], cloud_name: str
) -> tuple[GetLatestImageConfig, ...]:
    """Get parametrized configurations for getting latest image.

    Args:
        arch: The machine architecture the image was built with.
        bases: Ubuntu OS image to build from.
        cloud_name: The Openstack cloud name to connect to from clouds.yaml.

    Returns:
        The parametrized GetLatestImage configuration values.
    """
    return tuple(
        GetLatestImageConfig(arch=arch, base=base, cloud_name=cloud_name) for base in bases
    )


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
