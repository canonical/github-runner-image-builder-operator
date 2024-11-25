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
    BuilderInitError,
    BuilderRunError,
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

# Bandit thinks this is a hardcoded secret
IMAGE_BUILDER_SECRET_PREFIX = "IMAGE_BUILDER_SECRET_"  # nosec: B105


@dataclasses.dataclass
class ApplicationInitializationConfig:
    """Required application initialization configurations.

    Attributes:
        cloud_config: The OpenStack cloud config the application should interact with.
        channel: The application channel.
        cron_interval: The number of hours to retrigger build.
        image_arch: The image architecture to initialize build resources for.
        resource_prefix: The prefix of application resources.
        unit_name: The Juju unit name to trigger the CRON with.
    """

    cloud_config: state.CloudConfig
    channel: state.BuilderAppChannel
    cron_interval: int
    image_arch: state.Arch
    resource_prefix: str
    unit_name: str


def initialize(app_init_config: ApplicationInitializationConfig) -> None:
    """Configure the host machine to build images.

    The application pre-populate OpenStack resources required to build the image.

    Args:
        app_init_config: Configuration required to initialize the app.

    Raises:
        BuilderInitError: If there was an error initializing the image builder application.
    """
    try:
        install_clouds_yaml(cloud_config=app_init_config.cloud_config.openstack_clouds_config)
        # The following lines should be covered by integration tests.
        _install_dependencies(channel=app_init_config.channel)
        _initialize_image_builder(  # pragma: no cover
            cloud_name=app_init_config.cloud_config.cloud_name,
            image_arch=app_init_config.image_arch,
            resource_prefix=app_init_config.resource_prefix,
        )
        configure_cron(
            unit_name=app_init_config.unit_name, interval=app_init_config.cron_interval
        )  # pragma: no cover
    except (DependencyInstallError, ImageBuilderInitializeError) as exc:
        raise BuilderInitError from exc


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


def _initialize_image_builder(
    cloud_name: str, image_arch: state.Arch, resource_prefix: str
) -> None:
    """Initialize github-runner-image-builder app.

    Args:
        cloud_name: The OpenStack cloud to pre-populate OpenStack image builder resources.
        image_arch: The architecture of the image to build.
        resource_prefix: The resource prefix for artefacts saved in the image repository.

    Raises:
        ImageBuilderInitializeError: If there was an error Initialize the app.
    """
    init_cmd = _build_init_command(
        cloud_name=cloud_name, image_arch=image_arch, resource_prefix=resource_prefix
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


def _build_init_command(
    cloud_name: str, image_arch: state.Arch, resource_prefix: str | None
) -> list[str]:
    """Build the application init command.

    Args:
        cloud_name: The OpenStack cloud to pre-populate OpenStack image builder resources.
        image_arch: The architecture of the image to build.
        resource_prefix: The resource prefix for artefacts saved in the image repository.

    Returns:
        The GitHub runner application init command.
    """
    cmd = [
        "/usr/bin/sudo",
        str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
        "init",
        "--experimental-external",
        "True",
        "--cloud-name",
        cloud_name,
        "--arch",
        image_arch.value,
    ]
    if resource_prefix:
        cmd.extend(["--prefix", resource_prefix])
    return cmd


def install_clouds_yaml(cloud_config: state.OpenstackCloudsConfig) -> None:
    """Install clouds.yaml for Openstack used by the image builder.

    The application interfaces OpenStack credentials with the charm via the clouds.yaml since each
    of the parameters being passed on (i.e. --openstack-username --openstack-password \
    --upload-openstack-username --upload-openstack-password ...) is too verbose.

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
    cron_text = f"0 */{interval} * * * {UBUNTU_USER} {builder_exec_command}\n"

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


@dataclasses.dataclass
class ScriptConfig:
    """User custom script related configurations.

    Attributes:
        script_url: The external script to run during cloud-init process.
        script_secrets: The script secrets to load as environment variables before executing the \
            script.
    """

    script_url: str | None
    script_secrets: dict[str, str] | None


@dataclasses.dataclass
class ImageConfig:
    """Builder run image related configuration parameters.

    Attributes:
        arch: The architecture to build the image for.
        base: The Ubuntu base OS image to build the image on.
        juju: The Juju channel to install and bootstrap on the image.
        microk8s: The Microk8s channel to install and bootstrap on the image.
        prefix: The image prefix.
        runner_version: The GitHub runner version to pin, defaults to latest.
        script_config: User script related configurations.
        image_name: The image name derived from image configuration attributes.
    """

    arch: state.Arch
    base: state.BaseImage
    juju: str
    microk8s: str
    prefix: str
    script_config: ScriptConfig
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
class CloudConfig:
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
class ExternalServiceConfig:
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

    image: ImageConfig
    cloud: CloudConfig
    external_service: ExternalServiceConfig


@dataclasses.dataclass
class ConfigMatrix:
    """Configurable image parameters matrix.

    This is just a wrapper DTO on parameterizable variables.

    Attributes:
        bases: The ubuntu OS bases.
        juju_channels: The juju snap channels to iterate during parametrization. e.g. \
            {"3.1/stable", "2.9/stable"}
        microk8s_channels: The microk8s snap channels to iterate during parametrization. e.g. \
            {"1.28-strict/stable", "1.29-strict/edge"}
    """

    bases: tuple[state.BaseImage, ...]
    juju_channels: set[str]
    microk8s_channels: set[str]


@dataclasses.dataclass
class StaticImageConfig:
    """Static image configuration values.

    Attributes:
        arch: The architecture to build the image for.
        script_url: The external script to run at the end of the cloud-init.
        script_secrets: The script secrets to load as environment variables before executing the \
            script.
        runner_version: The GitHub runner version.
    """

    arch: state.Arch
    script_url: str | None
    script_secrets: dict[str, str] | None
    runner_version: str | None


@dataclasses.dataclass
class StaticConfigs:
    """Static configurations that are used to interact with the image repository.

    Attributes:
        cloud_config: The OpenStack cloud configuration.
        image_config: The output image configuration.
        service_config: The helper services to build the image.
    """

    cloud_config: CloudConfig
    image_config: StaticImageConfig
    service_config: ExternalServiceConfig


def run(config_matrix: ConfigMatrix, static_config: StaticConfigs) -> list[list[CloudImage]]:
    """Run a build immediately.

    Args:
        config_matrix: The configurable values matrix for running image builder.
        static_config: The static configurations values to run the image builder.

    Raises:
        BuilderRunError: if there was an error while launching the subprocess.

    Returns:
        The built image metadata.
    """
    build_configs = _parametrize_build(config_matrix=config_matrix, static_config=static_config)
    try:
        num_cores = multiprocessing.cpu_count() - 1
        with multiprocessing.Pool(min(len(build_configs), num_cores)) as pool:
            build_results = pool.map(_run, build_configs)
    except multiprocessing.ProcessError as exc:
        raise BuilderRunError("Failed to run parallel build") from exc
    return build_results


def _parametrize_build(
    config_matrix: ConfigMatrix, static_config: StaticConfigs
) -> tuple[RunConfig, ...]:
    """Get parametrized build configurations.

    Args:
        config_matrix: The configuration values for running image builder.
        static_config: The static configurations values to run the image builder.

    Returns:
        Per image build configuration values.
    """
    configs: list[RunConfig] = []
    for base in config_matrix.bases:
        for juju in config_matrix.juju_channels:
            for microk8s in config_matrix.microk8s_channels:
                configs.append(
                    RunConfig(
                        image=ImageConfig(
                            arch=static_config.image_config.arch,
                            base=base,
                            juju=juju,
                            microk8s=microk8s,
                            prefix=static_config.cloud_config.resource_prefix,
                            runner_version=static_config.image_config.runner_version,
                            script_config=ScriptConfig(
                                script_url=static_config.image_config.script_url,
                                script_secrets=static_config.image_config.script_secrets,
                            ),
                        ),
                        cloud=CloudConfig(
                            build_cloud=static_config.cloud_config.build_cloud,
                            build_flavor=static_config.cloud_config.build_flavor,
                            build_network=static_config.cloud_config.build_network,
                            resource_prefix=static_config.cloud_config.resource_prefix,
                            num_revisions=static_config.cloud_config.num_revisions,
                            upload_clouds=static_config.cloud_config.upload_clouds,
                        ),
                        external_service=ExternalServiceConfig(
                            dockerhub_cache=static_config.service_config.dockerhub_cache,
                            proxy=(
                                static_config.service_config.proxy
                                if static_config.service_config.proxy
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
        run_command = _build_run_command(
            run_args=_RunArgs(
                cloud_name=config.cloud.build_cloud, image_name=config.image.image_name
            ),
            cloud_options=_CloudOptions(
                flavor=config.cloud.build_flavor,
                keep_revisions=config.cloud.num_revisions,
                network=config.cloud.build_network,
                prefix=config.cloud.resource_prefix,
                upload_clouds=config.cloud.upload_clouds,
            ),
            image_options=_ImageOptions(
                arch=config.image.arch,
                image_base=config.image.base,
                juju=config.image.juju,
                microk8s=config.image.microk8s,
                runner_version=config.image.runner_version,
                script_url=config.image.script_config.script_url,
                script_secrets=config.image.script_config.script_secrets,
            ),
            service_options=_ServiceOptions(
                dockerhub_cache=config.external_service.dockerhub_cache,
                proxy=config.external_service.proxy,
            ),
        )
        logger.info("Run build command: %s", run_command)
        # The arg "user" exists but pylint disagrees.
        stdout = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg # nosec:B603
            args=run_command,
            user=UBUNTU_USER,
            cwd=UBUNTU_HOME,
            encoding="utf-8",
            env={
                "HOME": str(UBUNTU_HOME),
                **_transform_secrets(secrets=config.image.script_config.script_secrets),
            },
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


def _transform_secrets(secrets: dict[str, str] | None) -> dict[str, str]:
    """Transform secrets to be prefixed with IMAGE_BUILDER_SECRET_.

    Args:
        secrets: The secrets to load as environment variables.

    Returns:
        Secrets to load as environment variables for image builder application.
    """
    return (
        {f"{IMAGE_BUILDER_SECRET_PREFIX}{key}": value for (key, value) in secrets.items()}
        if secrets
        else {}
    )


@dataclasses.dataclass
class _RunArgs:
    """Builder application run arguments.

    Attributes:
        cloud_name: The cloud to run the builder VMs on.
        image_name: The output image name.
    """

    cloud_name: str
    image_name: str


@dataclasses.dataclass
class _CloudOptions:
    """Builder application run optional arguments related to OpenStack cloud.

    Attributes:
        flavor: The OpenStack flavor to launch the VM with.
        keep_revisions: The number of image revisions to keep before deletion from the image \
            repository.
        network: The OpenStack network to launch the builder VMs in.
        prefix: The OpenStack artefacts resource prefix.
        upload_clouds: The name of clouds in clouds.yaml to upload the final images to.
    """

    flavor: str | None
    keep_revisions: int | None
    network: str | None
    prefix: str | None
    upload_clouds: typing.Iterable[str] | None


@dataclasses.dataclass
class _ImageOptions:
    """Builder application run optional arguments related to image.

    Attributes:
        arch: The architecture of the final image build.
        image_base: The Ubuntu OS base.
        juju: The Juju snap channel, e.g. 3.1/stable.
        microk8s: The Microk8s snap channel, e.g. 1.29-strict/stable.
        runner_version: The GitHub runner version, e.g. 1.2.3.
        script_url: The URL of the script to run at the end of cloud-init.
        script_secrets: The script secrets to load as environment variables before executing the \
            script.
    """

    arch: state.Arch | None
    image_base: state.BaseImage | None
    juju: str | None
    microk8s: str | None
    runner_version: str | None
    script_url: str | None
    script_secrets: dict[str, str] | None


@dataclasses.dataclass
class _ServiceOptions:
    """Builder application run optional arguments related to external helper services.

    Attributes:
        dockerhub_cache: The DockerHub cache to use when initializing microk8s.
        proxy: The proxy to use when building the image.
    """

    dockerhub_cache: str | None
    proxy: str | None


def _build_run_command(
    run_args: _RunArgs,
    cloud_options: _CloudOptions,
    image_options: _ImageOptions,
    service_options: _ServiceOptions,
) -> list[str]:
    """Build the application run command.

    Args:
        run_args: Image builder application runner required arguments.
        cloud_options: Optional arguments related to OpenStack cloud.
        image_options: Optional arguments related to image.
        service_options: Optional arguments related to external helper services.

    Returns:
        The application run command.
    """
    cmd = [
        "/usr/bin/run-one",
        "/usr/bin/sudo",
        str(GITHUB_RUNNER_IMAGE_BUILDER_PATH),
        "run",
        run_args.cloud_name,
        run_args.image_name,
        # This option is to be deprecated when the application only supports external build mode.
        "--experimental-external",
        "True",
    ]
    cmd.extend(_build_run_cloud_options(cloud_options=cloud_options))
    cmd.extend(_build_run_image_options(image_options=image_options))
    cmd.extend(_build_run_service_options(service_options=service_options))
    return cmd


def _build_run_cloud_options(cloud_options: _CloudOptions) -> list[str]:
    """Build the application run command cloud options.

    Args:
        cloud_options: Optional arguments related to OpenStack cloud.

    Returns:
        The application run options related to OpenStack cloud.
    """
    cmd: list[str] = []
    if cloud_options.flavor:
        cmd.extend(["--flavor", cloud_options.flavor])
    if cloud_options.keep_revisions:
        cmd.extend(["--keep-revisions", str(cloud_options.keep_revisions)])
    if cloud_options.network:
        cmd.extend(["--network", cloud_options.network])
    if cloud_options.prefix:
        cmd.extend(["--prefix", cloud_options.prefix])
    if cloud_options.upload_clouds:
        cmd.extend(["--upload-clouds", ",".join(cloud_options.upload_clouds)])
    return cmd


def _build_run_image_options(image_options: _ImageOptions) -> list[str]:
    """Build the application run command image options.

    Args:
        image_options: Optional arguments related to output image.

    Returns:
        The application run options related to output image.
    """
    cmd: list[str] = []
    if image_options.arch:
        cmd.extend(["--arch", image_options.arch.value])
    if image_options.image_base:
        cmd.extend(["--base-image", image_options.image_base.value])
    if image_options.juju:
        cmd.extend(["--juju", image_options.juju])
    if image_options.microk8s:
        cmd.extend(["--microk8s", image_options.microk8s])
    if image_options.runner_version:
        cmd.extend(["--runner-version", image_options.runner_version])
    if image_options.script_url:
        cmd.extend(["--script-url", image_options.script_url])
    return cmd


def _build_run_service_options(service_options: _ServiceOptions) -> list[str]:
    """Build the application run command service options.

    Args:
        service_options: Optional arguments related to image building helper services.

    Returns:
        The application run options related to helper services.
    """
    cmd: list[str] = []
    if service_options.dockerhub_cache:
        cmd.extend(["--dockerhub-cache", service_options.dockerhub_cache])
    if service_options.proxy:
        cmd.extend(
            [
                "--proxy",
                service_options.proxy.removeprefix("http://").removeprefix("https://"),
            ]
        )
    return cmd


def get_latest_images(
    config_matrix: ConfigMatrix, static_config: StaticConfigs
) -> list[CloudImage]:
    """Fetch the latest image build ID.

    Args:
        config_matrix: Matricized values of configurable image parameters.
        static_config: Static configurations that are used to interact with the image repository.

    Raises:
        GetLatestImageError: If there was an error fetching the latest image.

    Returns:
        The latest successful image build information.
    """
    fetch_configs = _parametrize_fetch(config_matrix=config_matrix, static_config=static_config)
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


def _parametrize_fetch(
    config_matrix: ConfigMatrix, static_config: StaticConfigs
) -> tuple[FetchConfig, ...]:
    """Get parametrized fetch configurations.

    Args:
        config_matrix: Parametrizable configuration values matrix.
        static_config: Static configurations that are used to interact with the image repository.

    Returns:
        Per image fetch configuration values.
    """
    configs = []
    for base in config_matrix.bases:
        for juju in config_matrix.juju_channels:
            for microk8s in config_matrix.microk8s_channels:
                configs.append(
                    FetchConfig(
                        arch=static_config.image_config.arch,
                        base=base,
                        cloud_id=static_config.cloud_config.build_cloud,
                        prefix=static_config.cloud_config.resource_prefix,
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
