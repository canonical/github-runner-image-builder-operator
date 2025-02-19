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
    """

    ARM64 = "arm64"
    X64 = "x64"
    S390X = "s390x"

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
        raise ValueError  # pragma: nocover


class BaseImage(str, Enum):
    """The ubuntu OS base image to build and deploy runners on.

    Attributes:
        JAMMY: The jammy ubuntu LTS image.
        NOBLE: The noble ubuntu LTS image.
    """

    JAMMY = "jammy"
    NOBLE = "noble"

    @classmethod
    def get_version(cls, base: "BaseImage") -> Literal["22.04", "24.04"]:
        """Change the codename to version tag.

        Args:
            base: The base image to get the version number for.

        Return:
            The release version of the current base image.
        """
        match base:
            case BaseImage.JAMMY:
                return "22.04"
            case BaseImage.NOBLE:
                return "24.04"

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


LTS_IMAGE_VERSION_TAG_MAP = {"22.04": BaseImage.JAMMY.value, "24.04": BaseImage.NOBLE.value}
BASE_CHOICES = tuple(
    itertools.chain.from_iterable((tag, name) for (tag, name) in LTS_IMAGE_VERSION_TAG_MAP.items())
)
IMAGE_OUTPUT_PATH = Path("compressed.img")

IMAGE_DEFAULT_APT_PACKAGES = [
    "build-essential",
    "docker.io",
    "gh",
    "jq",
    "npm",
    "python3-dev",
    "python3-pip",
    "python-is-python3",
    "shellcheck",
    "tar",
    "time",
    "unzip",
    "wget",
]
S390x_ADDITIONAL_APT_PACKAGES = ["dotnet-runtime-8.0"]

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
UPSTREAM_RUNNER_BINARY_REPO = "actions/runner"


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
