# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module containing configurations."""

import dataclasses
import itertools
import logging
import urllib.parse
from enum import Enum
from pathlib import Path
from typing import Literal


class Arch(str, Enum):
    """Supported system architectures.

    Attributes:
        ARM64: Represents an ARM64 system architecture.
        X64: Represents an X64/AMD64 system architecture.
        S390X: Represents an S390X system architecture.
        PPC64LE: Represents a PPC64LE system architecture.
        ARM: Represents an ARM (32-bit armhf) system architecture.
    """

    ARM64 = "arm64"
    X64 = "x64"
    S390X = "s390x"
    PPC64LE = "ppc64le"
    ARM = "arm"

    def to_openstack(self) -> str:
        """Convert the architecture to OpenStack compatible arch string.

        Returns:
            The architecture string.
        """  # noqa: DCO050 the ValueError is an unreachable code.
        match self:
            case Arch.ARM64:
                return "aarch64"
            case Arch.X64:
                return "x86_64"
            case Arch.S390X:
                return "s390x"
            case Arch.PPC64LE:
                return "ppc64le"
            case Arch.ARM:
                # Nova/libvirt use the canonical "armv7l" for 32-bit ARM as the image
                # architecture property; "armhf" (the Ubuntu userland ABI name) is rejected by
                # Nova. The cloud-image download filename still uses "armhf" (see cloud_image.py).
                return "armv7l"
        raise ValueError  # pragma: nocover


class BaseImage(str, Enum):
    """The ubuntu OS base image to build and deploy runners on.

    Attributes:
        FOCAL: The focal ubuntu LTS image.
        JAMMY: The jammy ubuntu LTS image.
        NOBLE: The noble ubuntu LTS image.
        RESOLUTE: The resolute ubuntu LTS image.
    """

    FOCAL = "focal"
    JAMMY = "jammy"
    NOBLE = "noble"
    RESOLUTE = "resolute"

    @classmethod
    def get_version(cls, base: "BaseImage") -> Literal["20.04", "22.04", "24.04", "26.04"]:
        """Change the codename to version tag.

        Args:
            base: The base image to get the version number for.

        Return:
            The release version of the current base image.
        """
        match base:
            case BaseImage.FOCAL:
                return "20.04"
            case BaseImage.JAMMY:
                return "22.04"
            case BaseImage.NOBLE:
                return "24.04"
            case BaseImage.RESOLUTE:
                return "26.04"

    @classmethod
    def from_str(cls, tag_or_name: str) -> "BaseImage":
        """Retrieve the base image tag from input.

        Args:
            tag_or_name: The base image string option.

        Returns:
            The base image configuration of the app.
        """
        if tag_or_name in LTS_IMAGE_VERSION_TAG_MAP:
            return cls(LTS_IMAGE_VERSION_TAG_MAP[tag_or_name])
        return cls(tag_or_name)


LTS_IMAGE_VERSION_TAG_MAP = {
    "20.04": BaseImage.FOCAL.value,
    "22.04": BaseImage.JAMMY.value,
    "24.04": BaseImage.NOBLE.value,
    "26.04": BaseImage.RESOLUTE.value,
}
BASE_CHOICES = tuple(
    itertools.chain.from_iterable((tag, name) for (tag, name) in LTS_IMAGE_VERSION_TAG_MAP.items())
)
IMAGE_OUTPUT_PATH = Path("compressed.img")

IMAGE_DEFAULT_APT_PACKAGES = [
    "build-essential",
    "cargo",
    "docker.io",
    "gh",
    "jq",
    "npm",
    "pkg-config",
    "python-is-python3",
    "python3-dev",
    "python3-pip",
    "rustc",
    "shellcheck",
    # socat is used for proxying between the runner and the tmate-ssh-server.
    "socat",
    "tar",
    "time",
    "unzip",
    "wget",
]
S390X_PPC64LE_ADDITIONAL_APT_PACKAGES = ["dotnet-runtime-8.0"]
# The linux-arm runner tarball is self-contained but its bundled .NET runtime needs libicu and
# libatomic present on the system at runtime. rustup and docker-buildx are additionally
# pre-installed on armhf images for arm32 build workloads.
ARM_ADDITIONAL_APT_PACKAGES = ["libicu74", "libatomic1", "rustup", "docker-buildx"]

_LOG_LEVELS = (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR)
LOG_LEVELS = tuple(
    str(level)
    for level in itertools.chain(
        _LOG_LEVELS,
        (logging.getLevelName(level) for level in _LOG_LEVELS),
        (logging.getLevelName(level).lower() for level in _LOG_LEVELS),
    )
)

FORK_RUNNER_BINARY_REPO = "canonical/github-actions-runner"


@dataclasses.dataclass
class ScriptConfig:
    """The custom setup script configurations.

    Attributes:
        script_url: The external setup bash script URL.
        script_secrets: The space separated external secrets to load before running external \
            script_url. e.g. "SECRET_ONE=HELLO SECRET_TWO=WORLD"
    """

    script_url: urllib.parse.ParseResult | None
    script_secrets: dict[str, str]


@dataclasses.dataclass
class ImageConfig:
    """The build image configuration values.

    Attributes:
        arch: The architecture of the target image.
        base: The ubuntu base OS of the image.
        runner_version: The GitHub runner version to install on the VM. Defaults to latest.
        script_config: The custom setup script configurations.
        name: The image name to upload on OpenStack.
    """

    arch: Arch
    base: BaseImage
    runner_version: str
    script_config: ScriptConfig
    name: str
