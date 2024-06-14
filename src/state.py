# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with charm state and configurations."""

import dataclasses
import logging
import os
import pathlib
import platform
import typing
from enum import Enum

import ops

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}
ARCHITECTURES_X86 = {"x86_64"}
CLOUD_NAME = "builder"
LTS_IMAGE_VERSION_TAG_MAP = {"22.04": "jammy", "24.04": "noble"}

APP_CHANNEL_CONFIG_NAME = "app-channel"
BASE_IMAGE_CONFIG_NAME = "base-image"
BUILD_INTERVAL_CONFIG_NAME = "build-interval"
OPENSTACK_AUTH_URL_CONFIG_NAME = "openstack-auth-url"
# Bandit thinks this is a hardcoded password
OPENSTACK_PASSWORD_CONFIG_NAME = "openstack-password"  # nosec: B105
OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME = "openstack-project-domain-name"
OPENSTACK_PROJECT_CONFIG_NAME = "openstack-project-name"
OPENSTACK_USER_DOMAIN_CONFIG_NAME = "openstack-user-domain-name"
OPENSTACK_USER_CONFIG_NAME = "openstack-user-name"
REVISION_HISTORY_LIMIT_CONFIG_NAME = "revision-history-limit"

SUCCESS_CALLBACK_SCRIPT_PATH = pathlib.Path("/home/ubuntu/on_build_success_callback.sh")
FAILED_CALLBACK_SCRIPT_PATH = pathlib.Path("/home/ubuntu/on_build_failed_callback.sh")


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
    def from_charm(cls, charm: ops.CharmBase) -> "BaseImage":
        """Retrieve the base image tag from charm.

        Args:
            charm: The charm instance.

        Returns:
            The base image configuration of the charm.
        """
        image_name = (
            typing.cast(str, charm.config.get(BASE_IMAGE_CONFIG_NAME, "jammy")).lower().strip()
        )
        if image_name in LTS_IMAGE_VERSION_TAG_MAP:
            return cls(LTS_IMAGE_VERSION_TAG_MAP[image_name])
        return cls(image_name)


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


class BuildConfigInvalidError(CharmConfigInvalidError):
    """Raised when charm config related to image build config is invalid."""


@dataclasses.dataclass
class BuilderRunConfig:
    """Configurations for running builder periodically.

    Attributes:
        arch: The machine architecture of the image to build with.
        base: Ubuntu OS image to build from.
        cloud_config: The Openstack clouds.yaml passed as charm config.
        cloud_name: The Openstack cloud name to connect to from clouds.yaml.
        num_revisions: Number of images to keep before deletion.
        callback_script: Path to callback script.
    """

    arch: Arch
    base: BaseImage
    cloud_config: dict[str, typing.Any]
    num_revisions: int
    callback_script: pathlib.Path = SUCCESS_CALLBACK_SCRIPT_PATH

    @property
    def cloud_name(self) -> str:
        """The cloud name from cloud_config."""
        return list(self.cloud_config["clouds"].keys())[0]

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "BuilderRunConfig":
        """Initialize build state from current charm instance.

        Args:
            charm: The running charm instance.

        Raises:
            BuildConfigInvalidError: If there was an invalid configuration on the charm.

        Returns:
            Current charm state.
        """
        try:
            arch = _get_supported_arch()
        except UnsupportedArchitectureError as exc:
            raise BuildConfigInvalidError("Unsupported architecture") from exc

        try:
            base_image = BaseImage.from_charm(charm)
        except ValueError as exc:
            raise BuildConfigInvalidError(
                (
                    "Unsupported input option for base-image, please re-configure the base-image "
                    "option."
                )
            ) from exc

        try:
            cloud_config = _parse_openstack_clouds_config(charm)
        except InvalidCloudConfigError as exc:
            raise BuildConfigInvalidError(msg=str(exc)) from exc

        try:
            revision_history_limit = _parse_revision_history_limit(charm)
        except ValueError as exc:
            raise BuildConfigInvalidError(msg=str(exc)) from exc

        return cls(
            arch=arch,
            base=base_image,
            cloud_config=cloud_config,
            num_revisions=revision_history_limit,
        )


def _parse_build_interval(charm: ops.CharmBase) -> int:
    """Parse build-interval charm configuration option.

    Args:
        charm: The charm instance.

    Raises:
        ValueError: If an invalid build interval is configured.

    Returns:
        Build interval in hours.
    """
    try:
        build_interval = int(charm.config.get(BUILD_INTERVAL_CONFIG_NAME, 6))
    except ValueError as exc:
        raise ValueError("An integer value for build-interval is expected.") from exc
    if build_interval < 1 or build_interval > 24:
        raise ValueError("Build interval must not be smaller than 1 or greater than 24")
    return build_interval


def _parse_revision_history_limit(charm: ops.CharmBase) -> int:
    """Parse revision-history-limit char configuration option.

    Args:
        charm: The charm instance.

    Raises:
        ValueError: If an invalid revision-history-limit is configured.

    Returns:
        Number of revisions to keep before deletion.
    """
    try:
        revision_history = int(charm.config.get(REVISION_HISTORY_LIMIT_CONFIG_NAME, 5))
    except ValueError as exc:
        raise ValueError("An integer value for revision history is expected.") from exc
    if revision_history < 2 or revision_history > 99:
        raise ValueError("Revision history must be greater than 1 and less than 100")
    return revision_history


class InvalidCloudConfigError(Exception):
    """Represents an error with openstack cloud config."""


def _parse_openstack_clouds_config(charm: ops.CharmBase) -> dict[str, dict]:
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

    return {
        "clouds": {
            CLOUD_NAME: {
                "auth": {
                    "auth_url": auth_url,
                    "password": password,
                    "project_domain_name": project_domain,
                    "project_name": project,
                    "user_domain_name": user_domain,
                    "username": user,
                }
            }
        }
    }


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
        channel: The application installation channel.
        run_config: The configuration required to build the image.
        interval: The interval in hours between each scheduled image builds.
    """

    channel: BuilderAppChannel
    run_config: BuilderRunConfig
    interval: int

    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "BuilderInitConfig":
        """Initialize charm state from current charm instance.

        Args:
            charm: The running charm instance.

        Raises:
            BuilderSetupConfigInvalidError: If there was an invalid configuration on the charm.

        Returns:
            Current charm state.
        """
        channel = BuilderAppChannel.from_charm(charm=charm)
        run_config = BuilderRunConfig.from_charm(charm=charm)

        try:
            build_interval = _parse_build_interval(charm)
        except ValueError as exc:
            raise BuilderSetupConfigInvalidError(msg=str(exc)) from exc

        return cls(
            channel=channel,
            run_config=run_config,
            interval=build_interval,
        )
