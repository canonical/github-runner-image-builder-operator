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

import tenacity
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
        install_clouds_yaml(
            cloud_config=init_config.run_config.cloud_config.openstack_clouds_config
        )
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
            [
                "--experimental-external",
                "True",
                "--cloud-name",
                init_config.run_config.cloud_config.cloud_name,
                "--arch",
                init_config.run_config.image_config.arch.value,
                "--prefix",
                init_config.app_name,
            ]
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
        juju: The juju snap channel.
        microk8s: The microk8s snap channel.
    """

    arch: state.Arch
    base: state.BaseImage
    cloud_id: str
    image_id: str
    juju: str
    microk8s: str


def run(config: state.BuilderRunConfig) -> list[list[CloudImage]]:
    """Run a build immediately.

    Args:
        config: The configuration values for running image builder.

    Raises:
        BuilderRunError: if there was an error while launching the subprocess.

    Returns:
        The built image id.
    """
    build_configs = _parametrize_build(config=config)
    try:
        num_cores = multiprocessing.cpu_count() - 1
        with multiprocessing.Pool(min(len(build_configs), num_cores)) as pool:
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
        juju: The Juju channel to install and bootstrap on the image.
        microk8s: The Microk8s channel to install and bootstrap on the image.
        prefix: The image prefix.
        runner_version: The GitHub runner version to pin, defaults to latest.
        script_url: The external script to run during cloud-init process.
        image_name: The image name derived from image configuration attributes.
    """

    arch: state.Arch
    base: state.BaseImage
    juju: str
    microk8s: str
    prefix: str
    script_url: str | None
    runner_version: str | None

    @property
    def image_name(self) -> str:
        """The image name derived from the image configuration attributes.

        Returns:
            The image name.
        """
        image_name = f"{self.prefix}-{self.base.value}-{self.arch.value}"
        if self.juju:
            image_name += f"-juju-{self.juju.replace('/','-')}"
        if self.microk8s:
            image_name += f"-mk8s-{self.microk8s.replace('/', '-')}"
        return image_name


@dataclasses.dataclass
class _RunCloudConfig:
    """Builder run cloud related configuration parameters.

    Attributes:
        build_cloud: The cloud to build the images on.
        build_flavor: The OpenStack builder flavor to use.
        build_network: The OpenStack builder network to use.
        resource_prefix: The OpenStack resources prefix to indicate the ownership.
        upload_clouds: The clouds to upload the final image to.
        num_revisions: The number of revisions to keep before deleting the image.
    """

    build_cloud: str
    build_flavor: str
    build_network: str
    resource_prefix: str
    num_revisions: int
    upload_clouds: typing.Iterable[str]


@dataclasses.dataclass
class _ExternalServiceConfig:
    """Builder run external service dependencies.

    Attributes:
        dockerhub_cache: The DockerHub cache URL to use to apply to image building.
        proxy: The proxy to use to build the image.
    """

    dockerhub_cache: str | None
    proxy: str | None


@dataclasses.dataclass
class RunConfig:
    """Builder run configuration parameters.

    Attributes:
        image: The image configuration parameters.
        cloud: The cloud configuration parameters.
        external_service: The external service dependencies for building the image.
    """

    image: _RunImageConfig
    cloud: _RunCloudConfig
    external_service: _ExternalServiceConfig


def _parametrize_build(config: state.BuilderRunConfig) -> tuple[RunConfig, ...]:
    """Get parametrized build configurations.

    Args:
        config: The configuration values for running image builder.

    Returns:
        Per image build configuration values.
    """
    configs = []
    for base in config.image_config.bases:
        for juju in config.image_config.juju_channels:
            for microk8s in config.image_config.microk8s_channels:
                configs.append(
                    RunConfig(
                        image=_RunImageConfig(
                            arch=config.image_config.arch,
                            base=base,
                            juju=juju,
                            microk8s=microk8s,
                            prefix=config.image_config.prefix,
                            runner_version=config.image_config.runner_version,
                            script_url=config.image_config.script_url,
                        ),
                        cloud=_RunCloudConfig(
                            build_cloud=config.cloud_config.cloud_name,
                            build_flavor=config.cloud_config.external_build_config.flavor,
                            build_network=config.cloud_config.external_build_config.network,
                            resource_prefix=config.image_config.prefix,
                            num_revisions=config.cloud_config.num_revisions,
                            upload_clouds=config.cloud_config.upload_cloud_ids,
                        ),
                        external_service=_ExternalServiceConfig(
                            dockerhub_cache=config.service_config.dockerhub_cache,
                            proxy=(
                                config.service_config.proxy.http
                                if config.service_config.proxy
                                else None
                            ),
                        ),
                    )
                )
    return tuple(configs)


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=2, min=5, max=60),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
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
            config.image.image_name,
            "--base-image",
            config.image.base.value,
            "--keep-revisions",
            str(config.cloud.num_revisions),
        ]
        if config.image.runner_version:
            commands.extend(["--runner-version", config.image.runner_version])
        if config.image.juju:
            commands.extend(["--juju", config.image.juju])
        if config.image.microk8s:
            commands.extend(["--microk8s", config.image.microk8s])
        if config.external_service.dockerhub_cache:
            commands.extend(["--dockerhub-cache", config.external_service.dockerhub_cache])
        if config.image.script_url:
            commands.extend(["--script-url", config.image.script_url])
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
                "--prefix",
                config.image.prefix,
            ]
        )
        if config.external_service.proxy:
            commands.extend(
                [
                    "--proxy",
                    config.external_service.proxy.removeprefix("http://").removeprefix("https://"),
                ]
            )
        logger.info("Run build command: %s", commands)
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
                juju=config.image.juju,
                microk8s=config.image.microk8s,
            )
            for (cloud_id, image_id) in zip(
                config.cloud.upload_clouds, stdout.split()[-1].split(",")
            )
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "Image build failed, code: %s, out: %s, err: %s, stdout: %s",
            exc.returncode,
            exc.output,
            exc.stderr,
            exc.stdout,
        )
        raise BuilderRunError from exc
    except subprocess.SubprocessError as exc:
        raise BuilderRunError from exc


def get_latest_images(config: state.BuilderRunConfig, cloud_id: str) -> list[CloudImage]:
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
        num_cores = multiprocessing.cpu_count() - 1
        with multiprocessing.Pool(min(len(fetch_configs), num_cores)) as pool:
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
        juju: The Juju channel to fetch the image for.
        microk8s: The Microk8s channel to fetch the image for.
        prefix: The image name prefix.
        image_name: The image name derived from image configuration attributes.
    """

    arch: state.Arch
    base: state.BaseImage
    cloud_id: str
    juju: str
    microk8s: str
    prefix: str

    @property
    def image_name(self) -> str:
        """The image name derived from the image configuration attributes.

        Returns:
            The image name.
        """
        image_name = f"{self.prefix}-{self.base.value}-{self.arch.value}"
        if self.juju:
            image_name += f"-juju-{self.juju.replace('/', '-')}"
        if self.microk8s:
            image_name += f"-mk8s-{self.microk8s.replace('/', '-')}"
        return image_name


def _parametrize_fetch(config: state.BuilderRunConfig, cloud_id: str) -> tuple[FetchConfig, ...]:
    """Get parametrized fetch configurations.

    Args:
        config: The configuration values for running image builder.
        cloud_id: The cloud ID to fetch image for.

    Returns:
        Per image fetch configuration values.
    """
    configs = []
    for base in config.image_config.bases:
        for juju in config.image_config.juju_channels:
            for microk8s in config.image_config.microk8s_channels:
                configs.append(
                    FetchConfig(
                        arch=config.image_config.arch,
                        base=base,
                        cloud_id=cloud_id,
                        prefix=config.image_config.prefix,
                        juju=juju,
                        microk8s=microk8s,
                    )
                )
    return tuple(configs)


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
                config.image_name,
            ],
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            timeout=10 * 60,
            env=os.environ,
            encoding="utf-8",
        )  # nosec: B603
        return CloudImage(
            arch=config.arch,
            base=config.base,
            cloud_id=config.cloud_id,
            image_id=image_id,
            juju=config.juju,
            microk8s=config.microk8s,
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
