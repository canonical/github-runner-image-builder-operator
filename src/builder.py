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
    init_cmd = ["/usr/bin/sudo", str(GITHUB_RUNNER_IMAGE_BUILDER_PATH), "init"]
    if init_config.external_build:
        init_cmd.extend(
            ["--experimental-external", "True", "--cloud-name", init_config.run_config.cloud_name]
        )
    try:
        subprocess.run(
            init_cmd,
            check=True,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
        )  # nosec: B603
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Failed to initialize builder, code: %s, out: %s, err: %s",
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise ImageBuilderInitializeError from exc
    except subprocess.SubprocessError as exc:
        raise ImageBuilderInitializeError from exc


def install_clouds_yaml(cloud_config: state.OpenstackCloudsConfig) -> None:
    """Install clouds.yaml for Openstack used by the image builder.

    Args:
        cloud_config: The contents of clouds.yaml parsed as dict.
    """
    cloud_config_dict = cloud_config.model_dump()
    if not OPENSTACK_CLOUDS_YAML_PATH.exists():
        OPENSTACK_CLOUDS_YAML_PATH.write_text(yaml.safe_dump(cloud_config_dict), encoding="utf-8")
        return
    if yaml.safe_load(OPENSTACK_CLOUDS_YAML_PATH.read_text(encoding="utf-8")) != cloud_config_dict:
        OPENSTACK_CLOUDS_YAML_PATH.write_text(yaml.safe_dump(cloud_config_dict), encoding="utf-8")


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
class CloudImage:
    """The cloud ID to uploaded image ID pair.

    Attributes:
        arch: The image architecture.
        base: The ubuntu base image of the build.
        cloud_id: The cloud ID that the image was uploaded to.
        image_id: The uploaded image ID.
    """

    arch: state.Arch
    base: state.BaseImage
    cloud_id: str
    image_id: str


def run(config: state.BuilderRunConfig, proxy: state.ProxyConfig | None) -> list[list[CloudImage]]:
    """Run a build immediately.

    Args:
        config: The configuration values for running image builder.
        proxy: The proxy configuration to apply on the builder.

    Raises:
        BuilderRunError: if there was an error while launching the subprocess.

    Returns:
        The built image id.
    """
    build_configs = _parametrize_build(config=config, proxy=proxy)
    try:
        with multiprocessing.Pool(len(build_configs)) as pool:
            build_results = pool.map(_run, build_configs)
    except multiprocessing.ProcessError as exc:
        raise BuilderRunError("Failed to run parallel build") from exc
    return build_results


@dataclasses.dataclass
class _RunImageConfig:
    """Builder run image related configuration parameters.

    Attributes:
        arch: The architecture to build the image for.
        base: The Ubuntu base OS image to build the image on.
        runner_version: The GitHub runner version to pin, defaults to latest.
    """

    arch: state.Arch
    base: state.BaseImage
    runner_version: str | None


@dataclasses.dataclass
class _RunCloudConfig:
    """Builder run cloud related configuration parameters.

    Attributes:
        build_cloud: The cloud to build the images on.
        build_flavor: The OpenStack builder flavor to use.
        build_network: The OpenStack builder network to use.
        upload_clouds: The clouds to upload the final image to.
        num_revisions: The number of revisions to keep before deleting the image.
        proxy: The proxy to use to build the image.
    """

    build_cloud: str
    build_flavor: str
    build_network: str
    upload_clouds: typing.Iterable[str]
    num_revisions: int
    proxy: str | None


@dataclasses.dataclass
class RunConfig:
    """Builder run configuration parameters.

    Attributes:
        image: The image configuration parameters.
        cloud: The cloud configuration parameters.
    """

    image: _RunImageConfig
    cloud: _RunCloudConfig


def _parametrize_build(
    config: state.BuilderRunConfig, proxy: state.ProxyConfig | None
) -> tuple[RunConfig, ...]:
    """Get parametrized build configurations.

    Args:
        config: The configuration values for running image builder.
        proxy: The proxy configuration to apply on the builder.

    Returns:
        Per image build configuration values.
    """
    return tuple(
        RunConfig(
            image=_RunImageConfig(
                arch=config.arch, base=base, runner_version=config.runner_version
            ),
            cloud=_RunCloudConfig(
                build_cloud=config.cloud_name,
                build_flavor=config.external_build_config.flavor,
                build_network=config.external_build_config.network,
                upload_clouds=config.upload_cloud_ids,
                num_revisions=config.num_revisions,
                proxy=proxy.http if proxy else None,
            ),
        )
        for base in config.bases
    )


def _run(config: RunConfig) -> list[CloudImage]:
    """Run a single build process.

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
            config.cloud.build_cloud,
            IMAGE_NAME_TMPL.format(
                IMAGE_BASE=config.image.base.value,
                ARCH=config.image.arch.value,
            ),
            "--base-image",
            config.image.base.value,
            "--keep-revisions",
            str(config.cloud.num_revisions),
        ]
        if config.image.runner_version:
            commands.extend(["--runner-version", config.image.runner_version])
        commands.extend(
            [
                "--experimental-external",
                "True",
                "--arch",
                config.image.arch.value,
                "--flavor",
                config.cloud.build_flavor,
                "--network",
                config.cloud.build_network,
                "--upload-clouds",
                ",".join(config.cloud.upload_clouds),
            ]
        )
        if config.cloud.proxy:
            commands.extend(
                [
                    "--proxy",
                    config.cloud.proxy.removeprefix("http://").removeprefix("https://"),
                ]
            )
        # The arg "user" exists but pylint disagrees.
        stdout = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg # nosec:B603
            args=commands,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            encoding="utf-8",
            env={"HOME": str(UBUNTU_HOME)},
        )
        # The return value of the CLI is "Image build success:\n<comma-separated-image-ids>"
        return list(
            CloudImage(
                arch=config.image.arch,
                base=config.image.base,
                cloud_id=cloud_id,
                image_id=image_id,
            )
            for (cloud_id, image_id) in zip(
                config.cloud.upload_clouds, stdout.split()[-1].split(",")
            )
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Image build failed, code: %s, out: %s, err: %s", exc.stderr, exc.stdout, exc.stderr
        )
        raise BuilderRunError from exc
    except subprocess.SubprocessError as exc:
        raise BuilderRunError from exc


def get_latest_image(config: state.BuilderRunConfig, cloud_id: str) -> list[CloudImage]:
    """Fetch the latest image build ID.

    Args:
        config: The configuration values for fetching latest image id.
        cloud_id: The cloud the fetch the images for.

    Raises:
        GetLatestImageError: If there was an error fetching the latest image.

    Returns:
        The latest successful image build information.
    """
    fetch_configs = _parametrize_fetch(config=config, cloud_id=cloud_id)
    try:
        with multiprocessing.Pool(len(fetch_configs)) as pool:
            get_results = pool.map(_get_latest_image, fetch_configs)
    except multiprocessing.ProcessError as exc:
        raise GetLatestImageError("Failed to run parallel fetch") from exc
    return get_results


@dataclasses.dataclass
class FetchConfig:
    """Fetch image configuration parameters.

    Attributes:
        arch: The architecture to build the image for.
        base: The Ubuntu base OS image to build the image on.
        cloud_id: The cloud ID to fetch the image from.
    """

    arch: state.Arch
    base: state.BaseImage
    cloud_id: str


def _parametrize_fetch(config: state.BuilderRunConfig, cloud_id: str) -> tuple[FetchConfig, ...]:
    """Get parametrized fetch configurations.

    Args:
        config: The configuration values for running image builder.
        cloud_id: The cloud ID to fetch image for.

    Returns:
        Per image fetch configuration values.
    """
    return tuple(
        FetchConfig(arch=config.arch, base=base, cloud_id=cloud_id) for base in config.bases
    )


def _get_latest_image(config: FetchConfig) -> CloudImage:
    """Fetch the latest image.

    Args:
        config: The fetch image configuration parameters.

    Raises:
        GetLatestImageError: If there was something wrong calling the image builder CLI.

    Returns:
        The built cloud image.
    """
    try:
        # the user keyword argument exists but pylint doesn't think so.
        image_id = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg
            [
                "/usr/bin/sudo",
                "--preserve-env",
                str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
                "latest-build-id",
                config.cloud_id,
                IMAGE_NAME_TMPL.format(IMAGE_BASE=config.base.value, ARCH=config.arch.value),
            ],
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
            encoding="utf-8",
        )  # nosec: B603
        return CloudImage(
            arch=config.arch, base=config.base, cloud_id=config.cloud_id, image_id=image_id
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Get latest id failed, code: %s, out: %s, err: %s",
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise GetLatestImageError from exc
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
                "/usr/bin/run-one",
                "/usr/bin/pipx",
                "upgrade",
                "github-runner-image-builder",
            ],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Pipx upgrade failed, code: %s, out: %s, err: %s",
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise UpgradeApplicationError from exc
    except subprocess.SubprocessError as exc:
        raise UpgradeApplicationError from exc
