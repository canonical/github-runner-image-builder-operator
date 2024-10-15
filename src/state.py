# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with charm state and configurations."""

import dataclasses
import logging
import os
import platform
import typing
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
EXTERNAL_BUILD_CONFIG_NAME = "experimental-external-build"
EXTERNAL_BUILD_FLAVOR_CONFIG_NAME = "experimental-external-build-flavor"
EXTERNAL_BUILD_NETWORK_CONFIG_NAME = "experimental-external-build-network"
JUJU_CHANNELS_CONFIG_NAME = "juju-channels"
OPENSTACK_AUTH_URL_CONFIG_NAME = "openstack-auth-url"
# Bandit thinks this is a hardcoded password
OPENSTACK_PASSWORD_CONFIG_NAME = "openstack-password"  # nosec: B105
OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME = "openstack-project-domain-name"
OPENSTACK_PROJECT_CONFIG_NAME = "openstack-project-name"
OPENSTACK_USER_DOMAIN_CONFIG_NAME = "openstack-user-domain-name"
OPENSTACK_USER_CONFIG_NAME = "openstack-user-name"
REVISION_HISTORY_LIMIT_CONFIG_NAME = "revision-history-limit"
RUNNER_VERSION_CONFIG_NAME = "runner-version"

IMAGE_RELATION = "image"


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
        prefix: The image name prefix (application name).
        runner_version: The GitHub runner version to embed in the image. Latest version if empty.
    """

    arch: Arch
    bases: tuple[BaseImage, ...]
    juju_channels: set[str]
    prefix: str
    runner_version: str

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
        runner_version = _parse_runner_version(charm=charm)

        return cls(
            arch=arch,
            bases=base_images,
            juju_channels=juju_channels,
            prefix=charm.app.name,
            runner_version=runner_version,
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
class BuilderRunConfig:
    """Configurations for running builder periodically.

    Attributes:
        image_config: Image configuration parameters.
        cloud_config: Cloud configuration parameters.
    """

    image_config: ImageConfig
    cloud_config: CloudConfig

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "BuilderRunConfig":
        """Initialize build state from current charm instance.

        Args:
            charm: The running charm instance.

        Returns:
            Current charm state.
        """
        cloud_config = CloudConfig.from_charm(charm=charm)
        image_config = ImageConfig.from_charm(charm=charm)
        return cls(
            cloud_config=cloud_config,
            image_config=image_config,
        )


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


class BuilderSetupConfigInvalidError(CharmConfigInvalidError):
    """Raised when charm config related to image build setup config is invalid."""


@dataclasses.dataclass(frozen=True)
class BuilderInitConfig:
    """The image builder setup config.

    Attributes:
        app_name: The current charm's application name.
        channel: The application installation channel.
        external_build: Whether the image builder should run in external build mode.
        interval: The interval in hours between each scheduled image builds.
        run_config: The configuration required to build the image.
        unit_name: The charm unit name in which the builder is running on.
    """

    app_name: str
    channel: BuilderAppChannel
    external_build: bool
    interval: int
    run_config: BuilderRunConfig
    unit_name: str

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "BuilderInitConfig":
        """Initialize charm state from current charm instance.

        Args:
            charm: The running charm instance.

        Returns:
            Current charm state.
        """
        channel = BuilderAppChannel.from_charm(charm=charm)
        run_config = BuilderRunConfig.from_charm(charm=charm)
        build_interval = _parse_build_interval(charm)

        return cls(
            app_name=charm.app.name,
            channel=channel,
            external_build=typing.cast(bool, charm.config.get(EXTERNAL_BUILD_CONFIG_NAME, False)),
            run_config=run_config,
            interval=build_interval,
            unit_name=charm.unit.name,
        )
