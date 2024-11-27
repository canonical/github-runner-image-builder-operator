# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with charm state and configurations."""

import dataclasses
import logging
import multiprocessing
import os
import platform
import typing
import urllib.parse
from enum import Enum

import ops
import pydantic

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}
ARCHITECTURES_X86 = {"x86_64", "amd64"}
CLOUD_NAME = "builder"
LTS_IMAGE_VERSION_TAG_MAP = {"22.04": "jammy", "24.04": "noble"}

ARCHITECTURE_CONFIG_NAME = "architecture"
APP_CHANNEL_CONFIG_NAME = "app-channel"
BASE_IMAGE_CONFIG_NAME = "base-image"
BUILD_INTERVAL_CONFIG_NAME = "build-interval"
DOCKERHUB_CACHE_CONFIG_NAME = "dockerhub-cache"
EXTERNAL_BUILD_CONFIG_NAME = "experimental-external-build"
EXTERNAL_BUILD_FLAVOR_CONFIG_NAME = "experimental-external-build-flavor"
EXTERNAL_BUILD_NETWORK_CONFIG_NAME = "experimental-external-build-network"
JUJU_CHANNELS_CONFIG_NAME = "juju-channels"
MICROK8S_CHANNELS_CONFIG_NAME = "microk8s-channels"
OPENSTACK_AUTH_URL_CONFIG_NAME = "openstack-auth-url"
# Bandit thinks this is a hardcoded password
OPENSTACK_PASSWORD_CONFIG_NAME = "openstack-password"  # nosec: B105
OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME = "openstack-project-domain-name"
OPENSTACK_PROJECT_CONFIG_NAME = "openstack-project-name"
OPENSTACK_USER_DOMAIN_CONFIG_NAME = "openstack-user-domain-name"
OPENSTACK_USER_CONFIG_NAME = "openstack-user-name"
REVISION_HISTORY_LIMIT_CONFIG_NAME = "revision-history-limit"
RUNNER_VERSION_CONFIG_NAME = "runner-version"
SCRIPT_URL_CONFIG_NAME = "script-url"
# Bandit thinks this is a hardcoded password
SCRIPT_SECRET_ID_CONFIG_NAME = "script-secret-id"  # nosec: B105
SCRIPT_SECRET_CONFIG_NAME = "script-secret"  # nosec: B105

IMAGE_RELATION = "image"

MIN_JUJU_VERSION_WITH_SECRET_SUPPORT = ops.JujuVersion("3.3")


class CharmConfigInvalidError(Exception):
    """Raised when charm config is invalid.

    Attributes:
        msg: Explanation of the error.
    """

    def __init__(self, msg: str | None = None):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


# Step down formatting is not applied here since classes need to be predefined to be used as class
# definitions of the CharmState class.
class Arch(str, Enum):
    """Supported system architectures.

    Attributes:
        ARM64: Represents an ARM64 system architecture.
        X64: Represents an X64/AMD64 system architecture.
    """

    def __str__(self) -> str:
        """Interpolate to string value.

        Returns:
            The enum string value.
        """
        return self.value

    ARM64 = "arm64"
    X64 = "x64"

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "Arch":
        """Get architecture to build for from charm config.

        Args:
            charm: The charm instance.

        Returns:
            The architecture to build for.
        """
        architecture = (
            typing.cast(str, charm.config.get(ARCHITECTURE_CONFIG_NAME, "")).lower().strip()
        )
        match architecture:
            case arch if arch in ARCHITECTURES_ARM64:
                return Arch.ARM64
            case arch if arch in ARCHITECTURES_X86:
                return Arch.X64
            case _:
                return _get_supported_arch()


class UnsupportedArchitectureError(CharmConfigInvalidError):
    """Raised when given machine charm architecture is unsupported."""


def _get_supported_arch() -> Arch:
    """Get current machine architecture.

    Raises:
        UnsupportedArchitectureError: if the current architecture is unsupported.

    Returns:
        Arch: Current machine architecture.
    """
    arch = platform.machine()
    match arch:
        case arch if arch in ARCHITECTURES_ARM64:
            return Arch.ARM64
        case arch if arch in ARCHITECTURES_X86:
            return Arch.X64
        case _:
            raise UnsupportedArchitectureError(msg=f"Unsupported {arch=}")


class InvalidBaseImageError(CharmConfigInvalidError):
    """Represents an error with invalid charm base image configuration."""


class BaseImage(str, Enum):
    """The ubuntu OS base image to build and deploy runners on.

    Attributes:
        JAMMY: The jammy ubuntu LTS image.
        NOBLE: The noble ubuntu LTS image.
    """

    JAMMY = "jammy"
    NOBLE = "noble"

    def __str__(self) -> str:
        """Interpolate to string value.

        Returns:
            The enum string value.
        """
        return self.value

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> tuple["BaseImage", ...]:
        """Retrieve the base image tag from charm.

        Args:
            charm: The charm instance.

        Raises:
            InvalidBaseImageError: If there was an invalid BaseImage configuration value.

        Returns:
            The base image configuration of the charm.
        """
        image_names = tuple(
            image_name.lower().strip()
            for image_name in typing.cast(
                str, charm.config.get(BASE_IMAGE_CONFIG_NAME, "jammy")
            ).split(",")
        )
        try:
            return tuple(
                (
                    cls(LTS_IMAGE_VERSION_TAG_MAP[image_name])
                    if image_name in LTS_IMAGE_VERSION_TAG_MAP
                    else cls(image_name)
                )
                for image_name in image_names
            )
        except ValueError as exc:
            raise InvalidBaseImageError(f"Invalid bases: {image_names}") from exc


@dataclasses.dataclass
class ProxyConfig:
    """Proxy configuration.

    Attributes:
        http: HTTP proxy address.
        https: HTTPS proxy address.
        no_proxy: Comma-separated list of hosts that should not be proxied.
    """

    http: str
    https: str
    no_proxy: str

    @classmethod
    def from_env(cls) -> "ProxyConfig | None":
        """Initialize the proxy config from charm.

        Returns:
            Current proxy config of the charm.
        """
        http_proxy = os.getenv("JUJU_CHARM_HTTP_PROXY", "")
        https_proxy = os.getenv("JUJU_CHARM_HTTPS_PROXY", "")
        no_proxy = os.getenv("JUJU_CHARM_NO_PROXY", "")

        if not (https_proxy and http_proxy):
            return None

        return cls(http=http_proxy, https=https_proxy, no_proxy=no_proxy)


@dataclasses.dataclass
class ExternalBuildConfig:
    """Configurations for external builder VMs.

    Attributes:
        flavor: The OpenStack flavor to use for external builder VM.
        network: The OpenStack network to launch the builder VM.
    """

    flavor: str
    network: str

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "ExternalBuildConfig":
        """Initialize build configuration from current charm instance.

        Args:
            charm: The running charm instance.

        Returns:
            The external build configuration of the charm.
        """
        flavor_name = (
            typing.cast(str, charm.config.get(EXTERNAL_BUILD_FLAVOR_CONFIG_NAME, ""))
            .lower()
            .strip()
        )
        network_name = (
            typing.cast(str, charm.config.get(EXTERNAL_BUILD_NETWORK_CONFIG_NAME, ""))
            .lower()
            .strip()
        )
        return cls(flavor=flavor_name, network=network_name)


class CloudsAuthConfig(pydantic.BaseModel):
    """Clouds.yaml authentication parameters.

    Attributes:
        auth_url: OpenStack authentication URL (keystone).
        password: OpenStack project user password.
        project_domain_name: OpenStack project domain name.
        project_name: OpenStack project name.
        user_domain_name: OpenStack user domain name.
        username: The OpenStack user name for given project.
    """

    # This is a configuration class and does not have methods.
    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic configuration options.

        Attributes:
            frozen: Define whether the object should be mutable.
        """

        frozen = True

    auth_url: str
    password: str
    project_domain_name: str
    project_name: str
    user_domain_name: str
    username: str

    def get_id(self) -> str:
        """Get unique cloud configuration ID.

        Returns:
            The unique cloud configuration ID.
        """
        return f"{self.project_name}_{self.username}"

    @classmethod
    def from_unit_relation_data(cls, data: ops.RelationDataContent) -> "CloudsAuthConfig | None":
        """Get auth data from unit relation data.

        Args:
            data: The unit relation data.

        Returns:
            CloudsAuthConfig if all required relation data are available, None otherwise.
        """
        if any(
            required_field not in data
            for required_field in (
                "auth_url",
                "password",
                "project_domain_name",
                "project_name",
                "user_domain_name",
                "username",
            )
        ):
            logger.info("Required relation data not yet set.")
            return None
        return cls(
            auth_url=data["auth_url"],
            password=data["password"],
            project_domain_name=data["project_domain_name"],
            project_name=data["project_name"],
            user_domain_name=data["user_domain_name"],
            username=data["username"],
        )


class _CloudsConfig(pydantic.BaseModel):
    """Clouds.yaml configuration.

    Attributes:
        auth: The authentication parameters.
    """

    auth: CloudsAuthConfig | None


class OpenstackCloudsConfig(pydantic.BaseModel):
    """The Openstack clouds.yaml configuration mapping.

    Attributes:
        clouds: The mapping of cloud to cloud configuration values.
    """

    clouds: typing.MutableMapping[str, _CloudsConfig]


class BuildConfigInvalidError(CharmConfigInvalidError):
    """Raised when charm config related to image build config is invalid."""


@dataclasses.dataclass
class ImageConfig:
    """Image configuration parameters.

    Attributes:
        arch: The machine architecture of the image to build with.
        bases: Ubuntu OS images to build from.
        juju_channels: The Juju channels to install on the images.
        microk8s_channels: The Microk8s channels to install on the images.
        runner_version: The GitHub runner version to embed in the image. Latest version if empty.
        script_url: The external script to run during cloud-init process.
        script_secrets: The script secrets to load as environment variables before executing the \
            script.
    """

    arch: Arch
    bases: tuple[BaseImage, ...]
    juju_channels: set[str]
    microk8s_channels: set[str]
    runner_version: str
    script_url: str | None
    script_secrets: dict[str, str] | None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "ImageConfig":
        """Initialize image config state from current charm instance.

        Args:
            charm: The running charm instance.

        Returns:
            Image configuration state.
        """
        arch = Arch.from_charm(charm=charm)
        base_images = BaseImage.from_charm(charm)
        juju_channels = _parse_juju_channels(charm=charm)
        microk8s_channels = _parse_microk8s_channels(charm=charm)
        runner_version = _parse_runner_version(charm=charm)
        script_url = _parse_script_url(charm=charm)
        script_secrets = _parse_script_secrets(charm=charm)

        return cls(
            arch=arch,
            bases=base_images,
            juju_channels=juju_channels,
            microk8s_channels=microk8s_channels,
            runner_version=runner_version,
            script_url=script_url,
            script_secrets=script_secrets,
        )


@dataclasses.dataclass
class CloudConfig:
    """Cloud configuration parameters.

    Attributes:
        cloud_name: The OpenStack cloud name to connect to from clouds.yaml.
        external_build_config: The external builder configuration values.
        num_revisions: Number of images to keep before deletion.
        openstack_clouds_config: The OpenStack clouds.yaml passed as charm config.
        upload_cloud_ids: The OpenStack cloud ids to connect to, where the image should be \
            made available.
    """

    openstack_clouds_config: OpenstackCloudsConfig
    external_build_config: ExternalBuildConfig | None
    num_revisions: int

    @property
    def cloud_name(self) -> str:
        """The cloud name from cloud_config."""
        return CLOUD_NAME

    @property
    def upload_cloud_ids(self) -> list[str]:
        """The cloud name from cloud_config."""
        return list(
            cloud_id
            for cloud_id in self.openstack_clouds_config.clouds.keys()
            if cloud_id != CLOUD_NAME
        )

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "CloudConfig":
        """Initialize cloud config state from current charm instance.

        Args:
            charm: The running charm instance.

        Returns:
            Cloud configuration state.
        """
        cloud_config = _parse_openstack_clouds_config(charm)
        external_build_enabled = typing.cast(
            bool, charm.config.get(EXTERNAL_BUILD_CONFIG_NAME, False)
        )
        external_build_config = (
            ExternalBuildConfig.from_charm(charm=charm) if external_build_enabled else None
        )
        revision_history_limit = _parse_revision_history_limit(charm)

        return cls(
            openstack_clouds_config=cloud_config,
            external_build_config=external_build_config,
            num_revisions=revision_history_limit,
        )


@dataclasses.dataclass
class ServiceConfig:
    """External service configuration values.

    Attributes:
        dockerhub_cache: The DockerHub cache to use for microk8s installation.
        proxy: The Juju proxy in which the charm should use to build the image.
    """

    dockerhub_cache: str | None
    proxy: ProxyConfig | None

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "ServiceConfig":
        """Initialize the external service configurations from charm.

        Args:
            charm: The running charm instance.

        Returns:
            The external service configurations used to build images.
        """
        dockerhub_cache = _parse_dockerhub_cache_config(charm=charm)
        proxy = ProxyConfig.from_env()
        return cls(dockerhub_cache=dockerhub_cache, proxy=proxy)


class InvalidDockerHubCacheURLError(CharmConfigInvalidError):
    """Represents an error with DockerHub cache URL."""


def _parse_dockerhub_cache_config(charm: ops.CharmBase) -> str | None:
    """Parse the dockerhub cache URL config from charm.

    Args:
        charm: The charm instance.

    Raises:
        InvalidDockerHubCacheURLError: If an invalid URL string was passed to the charm.

    Returns:
        The valid DockerHub cache URL string.
    """
    dockerhub_cache_url_str = typing.cast(str, charm.config.get(DOCKERHUB_CACHE_CONFIG_NAME))
    if not dockerhub_cache_url_str:
        return None
    parsed_result = urllib.parse.urlparse(dockerhub_cache_url_str)
    if not all((parsed_result.scheme, parsed_result.hostname)):
        raise InvalidDockerHubCacheURLError("DockerHub scheme or hostname not provided.")
    return parsed_result.geturl()


class BuilderAppChannelInvalidError(CharmConfigInvalidError):
    """Represents invalid builder app channel configuration."""


class BuilderAppChannel(str, Enum):
    """Image builder application channel.

    This is managed by the application's git tag and versioning tag in pyproject.toml.

    Attributes:
        EDGE: Edge application channel.
        STABLE: Stable application channel.
    """

    EDGE = "edge"
    STABLE = "stable"

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "BuilderAppChannel":
        """Retrieve the app channel from charm.

        Args:
            charm: The charm instance.

        Raises:
            BuilderAppChannelInvalidError: If an invalid application channel was selected.

        Returns:
            The application channel to deploy.
        """
        try:
            return cls(typing.cast(str, charm.config.get(APP_CHANNEL_CONFIG_NAME)))
        except ValueError as exc:
            raise BuilderAppChannelInvalidError from exc


@dataclasses.dataclass
class ApplicationConfig:
    """Image builder application related configuration values.

    Attributes:
        build_interval: Hours between regular build jobs.
        channel: The application channel to install.
        parallel_build: Number of parallel number of applications to spawn.
        resource_prefix: The prefix of the resource saved on the repository for this application \
            manager.
    """

    build_interval: int
    channel: BuilderAppChannel
    parallel_build: int
    resource_prefix: str


@dataclasses.dataclass
class BuilderConfig:
    """Configurations for running builder periodically.

    Attributes:
        app_config: Application configuration parameters.
        image_config: Image configuration parameters.
        cloud_config: Cloud configuration parameters.
        service_config: The external dependent service configurations to build the image.
    """

    app_config: ApplicationConfig
    image_config: ImageConfig
    cloud_config: CloudConfig
    service_config: ServiceConfig

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "BuilderConfig":
        """Initialize build state from current charm instance.

        Args:
            charm: The running charm instance.

        Returns:
            Current charm state.
        """
        cloud_config = CloudConfig.from_charm(charm=charm)
        image_config = ImageConfig.from_charm(charm=charm)
        service_config = ServiceConfig.from_charm(charm=charm)
        return cls(
            app_config=ApplicationConfig(
                build_interval=_parse_build_interval(charm=charm),
                channel=BuilderAppChannel.from_charm(charm=charm),
                parallel_build=_get_num_parallel_build(charm=charm),
                resource_prefix=charm.app.name,
            ),
            cloud_config=cloud_config,
            image_config=image_config,
            service_config=service_config,
        )


class InsufficientCoresError(CharmConfigInvalidError):
    """Represents an error with invalid charm resource configuration."""


def _get_num_parallel_build(charm: ops.CharmBase) -> int:
    """Determine the number of parallel build that the charm can run.

    Args:
        charm: The charm instance.

    Raises:
        InsufficientCoresError: If not sufficient number of cores were allocated to the charm.

    Returns:
        The number of cores to use for parallel building of images.
    """
    num_cores = multiprocessing.cpu_count() - 1
    if num_cores < 1:
        raise InsufficientCoresError(
            "Please allocate more cores "
            f"`juju set-constraints {charm.app.name} cores=<more than 2 cores>`"
        )
    return num_cores


class BuildIntervalConfigError(CharmConfigInvalidError):
    """Represents an error with invalid interval configuration."""


def _parse_build_interval(charm: ops.CharmBase) -> int:
    """Parse build-interval charm configuration option.

    Args:
        charm: The charm instance.

    Raises:
        BuildIntervalConfigError: If an invalid build interval is configured.

    Returns:
        Build interval in hours.
    """
    try:
        build_interval = int(charm.config.get(BUILD_INTERVAL_CONFIG_NAME, 6))
    except ValueError as exc:
        raise BuildIntervalConfigError("An integer value for build-interval is expected.") from exc
    if build_interval < 1 or build_interval > 24:
        raise BuildIntervalConfigError(
            "Build interval must not be smaller than 1 or greater than 24"
        )
    return build_interval


class InvalidRevisionHistoryLimitError(CharmConfigInvalidError):
    """Represents an error with invalid revision history limit configuration value."""


def _parse_revision_history_limit(charm: ops.CharmBase) -> int:
    """Parse revision-history-limit char configuration option.

    Args:
        charm: The charm instance.

    Raises:
        InvalidRevisionHistoryLimitError: If an invalid revision-history-limit is configured.

    Returns:
        Number of revisions to keep before deletion.
    """
    try:
        revision_history = int(charm.config.get(REVISION_HISTORY_LIMIT_CONFIG_NAME, 5))
    except ValueError as exc:
        raise InvalidRevisionHistoryLimitError(
            "An integer value for revision history is expected."
        ) from exc
    if revision_history < 2 or revision_history > 99:
        raise InvalidRevisionHistoryLimitError(
            "Revision history must be greater than 1 and less than 100"
        )
    return revision_history


def _parse_runner_version(charm: ops.CharmBase) -> str:
    """Parse the runner version configuration value.

    Args:
        charm: The charm instance.

    Raises:
        ValueError: If an invalid version number is provided.

    Returns:
        The semantic version number of the GitHub runner.
    """
    version_str = typing.cast(str, charm.config.get(RUNNER_VERSION_CONFIG_NAME, ""))
    if not version_str:
        return ""

    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError("The runner version must be in semantic version format.")
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
    except ValueError as exc:
        raise ValueError("The runner version numbers must be an integer.") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ValueError("The runner version numbers cannot be negative.")

    return version_str


class InvalidCloudConfigError(CharmConfigInvalidError):
    """Represents an error with openstack cloud config."""


def _parse_openstack_clouds_config(charm: ops.CharmBase) -> OpenstackCloudsConfig:
    """Parse and validate openstack clouds yaml config value.

    Args:
        charm: The charm instance.

    Raises:
        InvalidCloudConfigError: if an invalid Openstack config value was set.

    Returns:
        The openstack clouds yaml.
    """
    auth_url = typing.cast(str, charm.config.get(OPENSTACK_AUTH_URL_CONFIG_NAME))
    password = typing.cast(str, charm.config.get(OPENSTACK_PASSWORD_CONFIG_NAME))
    project_domain = typing.cast(str, charm.config.get(OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME))
    project = typing.cast(str, charm.config.get(OPENSTACK_PROJECT_CONFIG_NAME))
    user_domain = typing.cast(str, charm.config.get(OPENSTACK_USER_DOMAIN_CONFIG_NAME))
    user = typing.cast(str, charm.config.get(OPENSTACK_USER_CONFIG_NAME))
    if not all((auth_url, password, project_domain, project, user_domain, user)):
        raise InvalidCloudConfigError("Please supply all OpenStack configurations.")

    clouds_config = OpenstackCloudsConfig(
        clouds={
            CLOUD_NAME: _CloudsConfig(
                auth=CloudsAuthConfig(
                    auth_url=auth_url,
                    password=password,
                    project_domain_name=project_domain,
                    project_name=project,
                    user_domain_name=user_domain,
                    username=user,
                ),
            )
        }
    )

    upload_cloud_auths = _parse_openstack_clouds_auth_configs_from_relation(charm=charm)
    for cloud_auth_config in upload_cloud_auths:
        clouds_config.clouds[cloud_auth_config.get_id()] = _CloudsConfig(auth=cloud_auth_config)

    return clouds_config


def _parse_openstack_clouds_auth_configs_from_relation(
    charm: ops.CharmBase,
) -> set[CloudsAuthConfig]:
    """Parse OpenStack clouds auth configuration from charm relation data.

    Args:
        charm: The charm instance.

    Returns:
        The OpenStack clouds yaml.
    """
    clouds_config: set[CloudsAuthConfig] = set()
    for relation in charm.model.relations.get(IMAGE_RELATION, []):
        if not relation.units:
            logger.warning("Units not yet joined %s relation.", IMAGE_RELATION)
            continue
        for unit in relation.units:
            if not relation.data[unit] or not (
                unit_auth_data := CloudsAuthConfig.from_unit_relation_data(relation.data[unit])
            ):
                logger.warning("Required field not yet set on %s.", unit.name)
                continue
            clouds_config.add(unit_auth_data)
    return clouds_config


class JujuChannelInvalidError(CharmConfigInvalidError):
    """Represents invalid Juju channels configuration."""


def _parse_juju_channels(charm: ops.CharmBase) -> set[str]:
    """Parse Juju channels from charm config.

    Args:
        charm: The charm instance.

    Raises:
        JujuChannelInvalidError: If there was an error parsing Juju channels config.

    Returns:
        Juju channels to install on the image.
    """
    juju_channels_str = typing.cast(str, charm.config.get(JUJU_CHANNELS_CONFIG_NAME, ""))
    try:
        # Add an empty value for image without juju (default).
        return set(("",)).union(_parse_snap_channels(csv_str=juju_channels_str))
    except ValueError as exc:
        raise JujuChannelInvalidError from exc


class Microk8sChannelInvalidError(CharmConfigInvalidError):
    """Represents invalid Microk8s channels configuration."""


def _parse_microk8s_channels(charm: ops.CharmBase) -> set[str]:
    """Parse Microk8s channels from charm config.

    Args:
        charm: The charm instance.

    Raises:
        Microk8sChannelInvalidError: If there was an error parsing Microk8s channels config.

    Returns:
        Microk8s channels to install on the image.
    """
    microk8s_channels_str = typing.cast(str, charm.config.get(MICROK8S_CHANNELS_CONFIG_NAME, ""))
    try:
        # Add an empty value for image without Microk8s (default).
        return set(("",)).union(_parse_snap_channels(csv_str=microk8s_channels_str))
    except ValueError as exc:
        raise Microk8sChannelInvalidError from exc


def _parse_snap_channels(csv_str: str) -> set[str]:
    """Parse snap channels from comma separated string value.

    The snap channel should be in <track>/<risk> format.

    Args:
        csv_str: The comma separated snap channel values.

    Raises:
        ValueError: If an invalid snap channel string was provided.

    Returns:
        Valid snap channel strings.
    """
    channels = set(channel.strip().lower() for channel in csv_str.split(",") if channel)
    for channel in channels:
        risk_track = channel.split("/")
        if len(risk_track) != 2 or any(not value for value in risk_track):
            raise ValueError(f"Invalid snap channel: {channel}")
    return channels


class InvalidScriptURLError(CharmConfigInvalidError):
    """Represents script URL configuration."""


def _parse_script_url(charm: ops.CharmBase) -> str | None:
    """Parse script url from charm configuration.

    Args:
        charm: The running charm instance.

    Raises:
        InvalidScriptURLError: If an invalid URL has been provided.

    Returns:
        Valid external script URL.
    """
    script_url_str = typing.cast(str, charm.config.get(SCRIPT_URL_CONFIG_NAME, ""))
    if not script_url_str:
        return None
    parsed_url = urllib.parse.urlparse(script_url_str)
    if not parsed_url.scheme or not parsed_url.hostname:
        raise InvalidScriptURLError("Invalid script URL, must contain scheme and hostname.")
    return script_url_str


class InvalidSecretError(CharmConfigInvalidError):
    """Represents an error when fetching secrets."""


def _parse_script_secrets(charm: ops.CharmBase) -> dict[str, str] | None:
    """Parse secrets to load as environment variables for the external script.

    Args:
        charm: The running charm instance.

    Raises:
        InvalidSecretError: If a secret of invalid format (secrets separated by space)
    """
    script_secret_id = typing.cast(str, charm.config.get(SCRIPT_SECRET_ID_CONFIG_NAME, ""))
    script_secret = typing.cast(str, charm.config.get(SCRIPT_SECRET_CONFIG_NAME, ""))
    if not script_secret_id and not script_secret:
        return None
    _validate_juju_secrets_config_support(
        is_secret_used=bool(script_secret_id), is_config_used=bool(script_secret)
    )
    if script_secret_id:
        try:
            secret = charm.model.get_secret(id=script_secret_id)
        except ops.SecretNotFoundError as exc:
            raise InvalidSecretError(f"Secret label not found: {script_secret_id}.") from exc
        except ops.ModelError as exc:
            raise InvalidSecretError(
                "Charm does not have access to read secrets. "
                "Please grant the charm read access to the secret."
            ) from exc
        return secret.get_content(refresh=True)
    secret_map = {}
    for key_value_pair in script_secret.split(" "):
        key_value = key_value_pair.split("=")
        if len(key_value) != 2 or not all(value for value in key_value):
            raise InvalidSecretError(f"Invalid secret <Key>=<Value> pair {key_value}")
        secret_map[key_value[0]] = key_value[1]
    return secret_map


def _validate_juju_secrets_config_support(is_secret_used: bool, is_config_used: bool) -> None:
    """Validate secrets support by Juju.

    If secrets are supported and secret config option is unused, raise an error.
    If secrets are not supported and secret config option is used, raise an error.
    If secrets are supported and config option is used, raised an error.
    If secrets are not supported and config option is used, pass.

    Args:
        is_secret_used: Whether the secret configuration option is used.
        is_config_used: Whether the configuration option is used.

    Raises:
        InvalidSecretError: If the usage of configuration option involving secrets are not valid.
    """
    if is_secret_used and is_config_used:
        raise InvalidSecretError(
            f"Both {SCRIPT_SECRET_CONFIG_NAME} "
            f"and {SCRIPT_SECRET_ID_CONFIG_NAME} configuration option set. "
            "Please remove one."
        )
    juju_version = ops.JujuVersion.from_environ()
    if is_secret_used and juju_version < MIN_JUJU_VERSION_WITH_SECRET_SUPPORT:
        raise InvalidSecretError(
            f"Secrets are not supported in Juju version {juju_version}. "
            "Please consider upgrading the Juju controller to versions "
            f">= 3.3 or use the {SCRIPT_SECRET_CONFIG_NAME} configuration "
            "option."
        )
    if not is_secret_used and juju_version >= MIN_JUJU_VERSION_WITH_SECRET_SUPPORT:
        raise InvalidSecretError(
            f"Please use Juju secrets via {SCRIPT_SECRET_ID_CONFIG_NAME} and unset the "
            f"{SCRIPT_SECRET_CONFIG_NAME} configuration option."
        )
