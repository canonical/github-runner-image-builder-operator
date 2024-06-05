# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with charm state and configurations."""

import dataclasses
import logging
import os
import pathlib
import platform
from enum import Enum
from typing import Any, Optional, cast

import yaml
from ops import CharmBase

import builder

logger = logging.getLogger(__name__)

ARCHITECTURES_ARM64 = {"aarch64", "arm64"}
ARCHITECTURES_X86 = {"x86_64"}
LTS_IMAGE_VERSION_TAG_MAP = {"22.04": "jammy", "24.04": "noble"}

BASE_IMAGE_CONFIG_NAME = "base-image"
BUILD_INTERVAL_CONFIG_NAME = "build-interval"
OPENSTACK_CLOUDS_YAML_CONFIG_NAME = "openstack-clouds-yaml"
REVISION_HISTORY_LIMIT_CONFIG_NAME = "revision-history-limit"


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


class UnsupportedArchitectureError(Exception):
    """Raised when given machine charm architecture is unsupported.

    Attributes:
        arch: The current machine architecture.
    """

    def __str__(self) -> str:
        """Represent the error in string format.

        Returns:
            The error in string format.
        """
        return f"UnsupportedArchitectureError: {self.arch}"

    def __init__(self, arch: str) -> None:
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            arch: The current machine architecture.
        """
        self.arch = arch


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
            raise UnsupportedArchitectureError(arch=arch)


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
    def from_charm(cls, charm: CharmBase) -> "BaseImage":
        """Retrieve the base image tag from charm.

        Args:
            charm: The charm instance.

        Returns:
            The base image configuration of the charm.
        """
        image_name = cast(str, charm.config.get(BASE_IMAGE_CONFIG_NAME, "jammy")).lower().strip()
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
    # Use optional instead of | operator due to unsupported str | None operand.
    def from_env(cls) -> Optional["ProxyConfig"]:
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


class CharmConfigInvalidError(Exception):
    """Raised when charm config is invalid.

    Attributes:
        msg: Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg: Explanation of the error.
        """
        self.msg = msg


class BuildConfigInvalidError(CharmConfigInvalidError):
    """Raised when charm config related to image build config is invalid."""


@dataclasses.dataclass
class RunConfig:
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
    cloud_config: dict[str, Any]
    num_revisions: int
    callback_script: pathlib.Path = builder.CALLBACK_SCRIPT_PATH

    @property
    def cloud_name(self) -> str:
        """The cloud name from cloud_config."""
        return list(self.cloud_config["clouds"].keys())[0]

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "RunConfig":
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


def _parse_build_interval(charm: CharmBase) -> int:
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


def _parse_revision_history_limit(charm: CharmBase) -> int:
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


def _parse_openstack_clouds_config(charm: CharmBase) -> dict[str, Any]:
    """Parse and validate openstack clouds yaml config value.

    Args:
        charm: The charm instance.

    Raises:
        InvalidCloudConfigError: if an invalid Openstack config value was set.

    Returns:
        The openstack clouds yaml.
    """
    openstack_clouds_yaml_str = charm.config.get(OPENSTACK_CLOUDS_YAML_CONFIG_NAME)
    if not openstack_clouds_yaml_str:
        raise InvalidCloudConfigError("No cloud config set")

    try:
        openstack_clouds_yaml = yaml.safe_load(cast(str, openstack_clouds_yaml_str))
    except yaml.YAMLError as exc:
        raise InvalidCloudConfigError(
            f"Invalid {OPENSTACK_CLOUDS_YAML_CONFIG_NAME} config. Invalid yaml."
        ) from exc
    if (config_type := type(openstack_clouds_yaml)) is not dict:
        raise InvalidCloudConfigError(
            f"Invalid openstack config format, expected dict, got {config_type}"
        )
    try:
        clouds = list(openstack_clouds_yaml["clouds"].keys())
    except KeyError as exc:
        raise InvalidCloudConfigError(
            "Invalid openstack config. Not able to initialize openstack integration."
        ) from exc
    if not clouds:
        raise InvalidCloudConfigError("No clouds found.")

    return openstack_clouds_yaml


class BuilderSetupConfigInvalidError(CharmConfigInvalidError):
    """Raised when charm config related to image build setup config is invalid."""


@dataclasses.dataclass(frozen=True)
class BuilderInitConfig:
    """The image builder setup config.

    Attributes:
        run_config: The configuration required to build the image.
        interval: The interval in hours between each scheduled image builds.
    """

    run_config: RunConfig
    interval: int

    @classmethod
    def from_charm(cls, charm: CharmBase) -> "BuilderInitConfig":
        """Initialize charm state from current charm instance.

        Args:
            charm: The running charm instance.

        Raises:
            BuilderSetupConfigInvalidError: If there was an invalid configuration on the charm.

        Returns:
            Current charm state.
        """
        try:
            run_config = RunConfig.from_charm(charm=charm)
        except BuildConfigInvalidError as exc:
            raise BuilderSetupConfigInvalidError(msg="Invalid run config.") from exc

        try:
            build_interval = _parse_build_interval(charm)
        except ValueError as exc:
            raise BuilderSetupConfigInvalidError(msg=str(exc)) from exc

        return cls(
            run_config=run_config,
            interval=build_interval,
        )
