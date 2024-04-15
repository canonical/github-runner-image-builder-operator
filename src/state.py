# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with charm state and configurations."""

import dataclasses
import platform
from enum import Enum

from ops import CharmBase

BASE_IMAGE_CONFIG_NAME = "base-image"
BUILD_INTERVAL_CONFIG_NAME = "build-interval"
REVISION_HISTORY_LIMIT_CONFIG_NAME = "revision-history-limit"



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

    def __init__(self, arch: str) -> None:
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            arch: The current machine architecture.
        """
        self.arch = arch



ARCHITECTURES_ARM64 = {"aarch64", "arm64"}
ARCHITECTURES_X86 = {"x86_64"}

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


LTS_IMAGE_VERSION_TAG_MAP = {"22.04": "jammy", "24.04": "noble"}

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
        image_name = charm.config.get(BASE_IMAGE_CONFIG_NAME, "jammy").lower().strip()
        if image_name in LTS_IMAGE_VERSION_TAG_MAP:
            return cls(LTS_IMAGE_VERSION_TAG_MAP[image_name])
        return cls(image_name)

def _parse_build_interval(charm: CharmBase) -> int:
    """Parses build-interval charm configuration option.

    Args:
        charm: The charm instance.

    Raises:
        ValueError: If an invalid build interval is configured.

    Returns:
        Build interval in hours.
    """
    try:
        build_interval = int(charm.config.get(BUILD_INTERVAL_CONFIG_NAME, "0").strip())
    except ValueError as exc:
        raise ValueError("An integer value for build-interval is expected.") from exc
    if build_interval < 0 or build_interval > 24:
        raise ValueError("Build interval must not be negative or greater than 24")
    return build_interval


def _parse_revision_history_limit(charm: CharmBase) -> int:
    """Parses revision-history-limit char configuration option.
    
    Args:
        charm: The charm instance.

    Raises:
        ValueError: If an invalid revision-history-limit is configured.

    Returns:
        Number of revisions to keep before deletion.
    """
    try:
        revision_history = int(charm.config.get(REVISION_HISTORY_LIMIT_CONFIG_NAME, "0").strip())
    except ValueError as exc:
        raise ValueError("An integer value for revision history is expected.") from exc
    if revision_history < 0 or revision_history > 99:
        raise ValueError("Revision history must be greater than 0 and less than 100")
    return revision_history


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

@dataclasses.dataclass(frozen=True)
class CharmState:
    """The charm state.

    Attributes:
        arch: The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64.
        base_image: The ubuntu base image to run the runner virtual machines on.
        build_interval: The interval in hours between each scheduled image builds.
        revision_history_limit: The number of image revisions to keep.
    """
    arch: Arch
    base_image: BaseImage
    build_interval: int
    revision_history_limit: int

    @classmethod
    def from_charm(cls, charm: CharmBase):
        """Initialize charm state from current charm instance.
        
        Args:
            charm: The running charm instance.

        Raises:
            CharmConfigInvalidError: If there was an invalid configuration on the charm.
        
        Returns:
            Current charm state.
        """
        try:
            arch = _get_supported_arch()
        except UnsupportedArchitectureError as exc:
            raise CharmConfigInvalidError(msg=f"Unsupported architecture {arch}, please deploy on a supported architecture.") from exc
    
        try:
            base_image = BaseImage.from_charm(charm)
        except ValueError as exc:
            raise CharmConfigInvalidError(msg="Unsupported input option for base-image, please re-configure the base-image option.") from exc
        
        try:
            build_interval = _parse_build_interval(charm)
        except ValueError as exc:
            raise CharmConfigInvalidError(msg=str(exc))

        try:
            revision_history_limit = _parse_revision_history_limit(charm)
        except ValueError as exc:
            raise CharmConfigInvalidError(msg=str(exc))
        
        return cls(arch=arch, base_image=base_image, build_interval=build_interval, revision_history_limit=revision_history_limit)
