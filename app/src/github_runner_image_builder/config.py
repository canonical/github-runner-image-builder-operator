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
                # The armhf runner image is an arm64 boot image (64-bit kernel) that carries a
                # 32-bit linux-arm runner payload. Native armhf images (32-bit kernel) do not boot
                # on the aarch64 "virt" machine, so the glance architecture is aarch64 so the base
                # image and snapshot schedule and boot on arm64 hosts. The 32-bit runner is
                # installed via multiarch (see cloud-init.sh.j2 and ARM_ADDITIONAL_APT_PACKAGES).
                return "aarch64"
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
# The 32-bit linux-arm runner agent runs via the host's native AArch32 support on the arm64
# image. It needs the armhf loader (ld-linux-armhf.so.3 from libc6:armhf) and the armhf build of
# libatomic (a .NET runtime dependency). rustup provides the armhf/armv7 Rust toolchain and
# docker-buildx enables arm32 container builds. libicu (the other .NET runtime dependency) is
# release-specific and handled by ARM_LIBICU_APT_PACKAGE_BY_BASE below.
ARM_ADDITIONAL_APT_PACKAGES = [
    "libc6:armhf",
    "libatomic1:armhf",
    "rustup",
    "docker-buildx",
]
# rustup (installed on armhf images) conflicts with the distro cargo and rustc packages, so these
# are dropped from the default apt package set on armhf; rustup provides cargo and rustc instead.
ARM_EXCLUDED_DEFAULT_APT_PACKAGES = ("cargo", "rustc")
# The linux-arm runner's bundled .NET runtime dlopens libicu, whose soname is release-specific
# (noble ships libicu74, resolute ships libicu78). Install the armhf build matching the base image.
ARM_LIBICU_APT_PACKAGE_BY_BASE = {
    BaseImage.NOBLE: "libicu74:armhf",
    BaseImage.RESOLUTE: "libicu78:armhf",
}

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
