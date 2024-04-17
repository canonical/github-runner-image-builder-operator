# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import dataclasses
import hashlib
import logging
import os
import shutil

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
import subprocess  # nosec
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

from charms.operator_libs_linux.v0 import apt

from chroot import ChrootBaseError, ChrootContextManager
from state import Arch, BaseImage
from utils import retry

logger = logging.getLogger(__name__)

APT_DEPENDENCIES = [
    "qemu-utils",  # used for qemu utilities tools to build and resize image
    "libguestfs-tools",  # used to modify VM images.
]


class DependencyInstallError(Exception):
    """Represents an error while installing required dependencies."""


def _install_dependencies() -> None:
    """Install required dependencies to run qemu image build.

    Raises:
        DependencyInstallError: If there was an error installing apt packages.
    """
    try:
        apt.add_package(APT_DEPENDENCIES, update_cache=True)
    except apt.PackageNotFoundError as exc:
        raise DependencyInstallError from exc


class NetworkBlockDeviceError(Exception):
    """Represents an error while enabling network block device."""


def _enable_nbd() -> None:
    """Enable network block device module to mount and build chrooted image.

    Raises:
        NetworkBlockDeviceError: If there was an error enable nbd kernel.
    """
    try:
        subprocess.run(["/usr/bin/modprobe", "nbd"], check=True, timeout=10)  # nosec: B603
    except subprocess.CalledProcessError as exc:
        raise NetworkBlockDeviceError from exc


class BuilderSetupError(Exception):
    """Represents an error while setting up host machine as builder."""


def setup_builder() -> None:
    """Configure the host machine to build images.

    Raises:
        BuilderSetupError: If there was an error setting up the host device for building images.
    """
    try:
        _install_dependencies()
        _enable_nbd()
    except (DependencyInstallError, NetworkBlockDeviceError) as exc:
        raise BuilderSetupError from exc


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


SupportedCloudImageArch = Literal["amd64", "arm64"]


def _get_supported_runner_arch(arch: Arch) -> SupportedCloudImageArch:
    """Validate and return supported runner architecture.

    The supported runner architecture takes in arch value from Github supported
    architecture and outputs architectures supported by ubuntu cloud images.
    See: https://docs.github.com/en/actions/hosting-your-own-runners/managing-\
        self-hosted-runners/about-self-hosted-runners#architectures
    and https://cloud-images.ubuntu.com/jammy/current/

    Args:
        arch: The compute architecture to check support for.

    Raises:
        UnsupportedArchitectureError: If an unsupported architecture was passed.

    Returns:
        The supported architecture.
    """
    match arch:
        case Arch.X64:
            return "amd64"
        case Arch.ARM64:
            return "arm64"
        case _:
            raise UnsupportedArchitectureError(arch)


IMAGE_MOUNT_DIR = Path("/mnt/ubuntu-image/")
NETWORK_BLOCK_DEVICE_PATH = Path("/dev/nbd0")
NETWORK_BLOCK_DEVICE_PARTITION_PATH = Path("/dev/nbd0p1")


def _clean_build_state() -> None:
    """Remove any artefacts left by previous build."""
    # The commands will fail if artefacts do not exist and hence there is no need to check the
    # output of subprocess runs.
    IMAGE_MOUNT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["/usr/bin/umount", str(IMAGE_MOUNT_DIR / "dev")], timeout=30, check=False
    )  # nosec: B603
    subprocess.run(
        ["/usr/bin/umount", str(IMAGE_MOUNT_DIR / "proc")], timeout=30, check=False
    )  # nosec: B603
    subprocess.run(
        ["/usr/bin/umount", str(IMAGE_MOUNT_DIR / "sys")], timeout=30, check=False
    )  # nosec: B603
    subprocess.run(
        ["/usr/bin/umount", str(IMAGE_MOUNT_DIR)], timeout=30, check=False
    )  # nosec: B603
    subprocess.run(
        ["/usr/bin/umount", str(NETWORK_BLOCK_DEVICE_PATH)], timeout=30, check=False
    )  # nosec: B603
    subprocess.run(  # nosec: B603
        ["/usr/bin/umount", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)], timeout=30, check=False
    )
    subprocess.run(  # nosec: B603
        ["/usr/bin/qemu-nbd", "--disconnect", str(NETWORK_BLOCK_DEVICE_PATH)],
        timeout=30,
        check=False,
    )
    subprocess.run(  # nosec: B603
        ["/usr/bin/qemu-nbd", "--disconnect", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)],
        timeout=30,
        check=False,
    )


CLOUD_IMAGE_URL_TMPL = (
    "https://cloud-images.ubuntu.com/{BASE_IMAGE}/current/"
    "{BASE_IMAGE}-server-cloudimg-{BIN_ARCH}.img"
)
CLOUD_IMAGE_FILE_NAME = "{BASE_IMAGE}-server-cloudimg-{BIN_ARCH}.img"


class CloudImageDownloadError(Exception):
    """Represents an error downloading cloud image."""


def _download_cloud_image(arch: Arch, base_image: BaseImage) -> Path:
    """Download the cloud image from cloud-images.ubuntu.com.

    Args:
        arch: The cloud image architecture to download.
        base_image: The ubuntu base image OS to download.

    Returns:
        The downloaded cloud image path.

    Raises:
        CloudImageDownloadError: If there was an error downloading the image.
    """
    try:
        bin_arch = _get_supported_runner_arch(arch)
    except UnsupportedArchitectureError as exc:
        raise CloudImageDownloadError from exc

    try:
        image_path, _ = urllib.request.urlretrieve(
            CLOUD_IMAGE_URL_TMPL.format(BASE_IMAGE=base_image.value, BIN_ARCH=bin_arch),
            CLOUD_IMAGE_FILE_NAME.format(BASE_IMAGE=base_image.value, BIN_ARCH=bin_arch),
        )
        return Path(image_path)
    except urllib.error.ContentTooShortError as exc:
        raise CloudImageDownloadError from exc


class ImageResizeError(Exception):
    """Represents an error while resizing the image."""


def _resize_cloud_img(cloud_image_path: Path) -> None:
    """Resize cloud image to allow space for dependency installations.

    Args:
        cloud_image_path: The target cloud image file to resize.

    Raises:
        ImageResizeError: If there was an error resizing the image.
    """
    try:
        subprocess.run(  # nosec: B603
            ["/usr/bin/qemu-img", "resize", str(cloud_image_path), "+1.5G"], check=True, timeout=60
        )
    except subprocess.CalledProcessError as exc:
        raise ImageResizeError from exc


class ImageMountError(Exception):
    """Represents an error while mounting the image to network block device."""


@retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
def _mount_nbd_partition() -> None:
    """Mount the network block device partition."""
    subprocess.run(  # nosec: B603
        [
            "/usr/bin/mount",
            "-o",
            "rw",
            str(NETWORK_BLOCK_DEVICE_PARTITION_PATH),
            str(IMAGE_MOUNT_DIR),
        ],
        check=True,
        timeout=60,
    )


def _mount_image_to_network_block_device(cloud_image_path: Path) -> None:
    """Mount the image to network block device in preparation for chroot.

    Args:
        cloud_image_path: The target cloud image file to mount.

    Raises:
        ImageMountError: If there was an error mounting the image to network block device.
    """
    try:
        subprocess.run(  # nosec: B603
            ["/usr/bin/qemu-nbd", f"--connect={NETWORK_BLOCK_DEVICE_PATH}", str(cloud_image_path)],
            check=True,
            timeout=60,
        )
        _mount_nbd_partition()
    except subprocess.CalledProcessError as exc:
        raise ImageMountError from exc


MOUNTED_RESOLV_CONF_PATH = IMAGE_MOUNT_DIR / "etc/resolv.conf"
HOST_RESOLV_CONF_PATH = Path("/etc/resolv.conf")


def _replace_mounted_resolv_conf() -> None:
    """Replace resolv.conf to host resolv.conf to allow networking."""
    MOUNTED_RESOLV_CONF_PATH.unlink(missing_ok=True)
    shutil.copy(str(HOST_RESOLV_CONF_PATH), str(MOUNTED_RESOLV_CONF_PATH))


class ResizePartitionError(Exception):
    """Represents an error while resizing network block device partitions."""


def _resize_mount_partitions() -> None:
    """Resize the block partition to fill available space.

    Raises:
        ResizePartitionError: If there was an error resizing network block device partitions.
    """
    try:
        subprocess.run(  # nosec: B603
            ["/usr/bin/growpart", str(NETWORK_BLOCK_DEVICE_PATH), "1"],
            check=True,
            timeout=60,
        )
        subprocess.run(  # nosec: B603
            ["/usr/bin/resize2fs", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)],
            check=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        raise ResizePartitionError from exc


DEFAULT_PYTHON_PATH = Path("/usr/bin/python3")
SYM_LINK_PYTHON_PATH = Path("/usr/bin/python")


def _create_python_symlinks() -> None:
    """Create python3 symlinks."""
    os.symlink(DEFAULT_PYTHON_PATH, SYM_LINK_PYTHON_PATH)


APT_TIMER = "apt-daily.timer"
APT_SVC = "apt-daily.service"
APT_UPGRADE_TIMER = "apt-daily-upgrade.timer"
APT_UPGRAD_SVC = "apt-daily-upgrade.service"


class UnattendedUpgradeDisableError(Exception):
    """Represents an error while disabling unattended-upgrade related services."""


def _disable_unattended_upgrades() -> None:
    """Disable unatteneded upgrades to prevent apt locks.

    Raises:
        UnattendedUpgradeDisableError: If there was an error disabling unattended upgrade related
            services.
    """
    try:
        # use subprocess run rather than operator-libs-linux's systemd library since the library
        # does not provide full features like mask.
        subprocess.run(
            ["/usr/bin/systemctl", "stop", APT_TIMER], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(
            ["/usr/bin/systemctl", "disable", APT_TIMER], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(
            ["/usr/bin/systemctl", "mask", APT_SVC], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(
            ["/usr/bin/systemctl", "stop", APT_UPGRADE_TIMER], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(  # nosec: B603
            ["/usr/bin/systemctl", "disable", APT_UPGRADE_TIMER], check=True, timeout=30
        )
        subprocess.run(
            ["/usr/bin/systemctl", "mask", APT_UPGRAD_SVC], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(
            ["/usr/bin/systemctl", "daemon-reload"], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(  # nosec: B603
            ["/usr/bin/apt-get", "remove", "-y", "unattended-upgrades"], check=True, timeout=30
        )
    except subprocess.SubprocessError as exc:
        raise UnattendedUpgradeDisableError from exc


class SystemUserConfigurationError(Exception):
    """Represents an error while adding user to chroot env."""


UBUNTU_USER = "ubuntu"
DOCKER_GROUP = "docker"
MICROK8S_GROUP = "microk8s"


def _configure_system_users() -> None:
    """Configure system users.

    Raises:
        SystemUserConfigurationError: If there was an error configuring ubuntu user.
    """
    try:
        subprocess.run(
            ["/usr/bin/useradd", "-m", UBUNTU_USER], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(
            ["/usr/bin/groupadd", MICROK8S_GROUP], check=True, timeout=30
        )  # nosec: B603
        subprocess.run(  # nosec: B603
            ["/usr/bin/usermod", "-aG", DOCKER_GROUP, UBUNTU_USER], check=True, timeout=30
        )
        subprocess.run(  # nosec: B603
            ["/usr/bin/usermod", "-aG", MICROK8S_GROUP, UBUNTU_USER], check=True, timeout=30
        )
    except subprocess.SubprocessError as exc:
        raise SystemUserConfigurationError from exc


YQ_DOWNLOAD_URL_TMPL = (
    "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_{BIN_ARCH}"
)
YQ_BINARY_CHECKSUM_URL = "https://github.com/mikefarah/yq/releases/latest/download/checksums"
YQ_CHECKSUM_HASHES_ORDER_URL = (
    "https://github.com/mikefarah/yq/releases/latest/download/checksums_hashes_order"
)
YQ_EXTRACT_CHECKSUM_SCRIPT_URL = (
    "https://github.com/mikefarah/yq/releases/latest/download/extract-checksum.sh"
)


class ExternalPackageInstallError(Exception):
    """Represents an error installilng external packages."""


def _validate_checksum(file: Path, expected_checksum: str) -> bool:
    """Validate the checksum of a given file.

    Args:
        file: The file to calculate checksum for.
        expected_checksum: The expected file checksum.

    Returns:
        True if the checksums match. False otherwise.
    """
    sha256 = hashlib.sha256()
    sha256.update(file.read_bytes())
    return sha256.hexdigest() == expected_checksum


BIN_ARCH_MAP: dict[Arch, str] = {Arch.ARM64: "arm64", Arch.X64: "amd64"}


def _install_external_packages(arch: Arch) -> None:
    """Install packages outside of apt.

    Installs yarn, yq.

    Args:
        arch: The architecture to download binaries for. #TODO check bin arch

    Raises:
        ExternalPackageInstallError: If there was an error installing external package.
    """
    try:
        subprocess.run(
            ["/usr/bin/npm", "install", "--global", "yarn"], check=True, timeout=60 * 5
        )  # nosec: B603
        subprocess.run(
            ["/usr/bin/npm", "cache", "clean", "--force"], check=True, timeout=60
        )  # nosec: B603
        bin_arch = BIN_ARCH_MAP[arch]
        yq_path_str = f"yq_linux_{bin_arch}"
        # The URLs are trusted
        urllib.request.urlretrieve(
            YQ_DOWNLOAD_URL_TMPL.format(BIN_ARCH=bin_arch), yq_path_str
        )  # nosec: B310
        urllib.request.urlretrieve(YQ_BINARY_CHECKSUM_URL, "checksums")  # nosec: B310
        urllib.request.urlretrieve(
            YQ_CHECKSUM_HASHES_ORDER_URL, "checksums_hashes_order"
        )  # nosec: B310
        urllib.request.urlretrieve(
            YQ_EXTRACT_CHECKSUM_SCRIPT_URL, "extract-checksum.sh"
        )  # nosec: B310
        # The output is <BIN_NAME> <CHECKSUM>
        checksum = subprocess.check_output(  # nosec: B603
            ["/usr/bin/bash", "extract-checksum.sh", "SHA-256", yq_path_str],
            encoding="utf-8",
            timeout=60,
        ).split()[1]
        yq_path = Path(yq_path_str)
        if not _validate_checksum(yq_path, checksum):
            raise ExternalPackageInstallError("Invalid checksum")
        yq_path.chmod(755)
        yq_path.rename("/usr/bin/yq")
    except (subprocess.SubprocessError, urllib.error.ContentTooShortError) as exc:
        raise ExternalPackageInstallError from exc


class ImageCompressError(Exception):
    """Represents an error while compressing cloud-img."""


def _compress_image(image: Path) -> Path:
    """Compress the cloud image.

    Args:
        image: The image to compress.

    Raises:
        ImageCompressError: If there was something wrong compressing the image.

    Returns:
        The compressed image path.
    """
    try:
        subprocess.run(  # nosec: B603
            ["/usr/bin/virt-sparsify", "--compress", str(image), "compressed.img"],
            check=True,
            timeout=60 * 10,
        )
        return Path("compressed.img")
    except subprocess.CalledProcessError as exc:
        raise ImageCompressError from exc


IMAGE_DEFAULT_APT_PACKAGES = [
    "docker.io",
    "npm",
    "python3-pip",
    "shellcheck",
    "jq",
    "wget",
    "unzip",
    "gh",
]


@dataclasses.dataclass
class BuildImageConfig:
    """Configuration for building the image.

    Attributes:
        arch: The CPU architecture to build the image for.
        base_image: The ubuntu image to use as build base.
    """

    arch: Arch
    base_image: BaseImage


class BuildImageError(Exception):
    """Represents an error while building the image."""


def build_image(config: BuildImageConfig) -> Path:
    """Build and save the image locally.

    Args:
        config: The configuration values to build the image with.

    Raises:
        BuildImageError: If there was an error building the image.

    Returns:
        The saved image path.
    """
    _clean_build_state()
    try:
        cloud_image_path = _download_cloud_image(arch=config.arch, base_image=config.base_image)
        _resize_cloud_img(cloud_image_path=cloud_image_path)
        _mount_image_to_network_block_device(cloud_image_path=cloud_image_path)
        _replace_mounted_resolv_conf()
        _resize_mount_partitions()
    except (CloudImageDownloadError, ImageMountError, ResizePartitionError) as exc:
        raise BuildImageError from exc

    try:
        with ChrootContextManager(IMAGE_MOUNT_DIR):
            # operator_libs_linux apt package uses dpkg -l and that does not work well with chroot
            # env, hence use subprocess run.
            subprocess.run(
                ["/usr/bin/apt-get", "update", "-y"], check=True, timeout=60 * 5
            )  # nosec: B603
            subprocess.run(  # nosec: B603
                ["/usr/bin/apt-get", "install", "-y", *IMAGE_DEFAULT_APT_PACKAGES],
                check=True,
                timeout=60 * 10,
            )
            _create_python_symlinks()
            _disable_unattended_upgrades()
            _configure_system_users()
            _install_external_packages(arch=config.arch)
    except (
        ChrootBaseError,
        subprocess.CalledProcessError,
        UnattendedUpgradeDisableError,
        SystemUserConfigurationError,
        ExternalPackageInstallError,
    ) as exc:
        raise BuildImageError from exc

    try:
        _clean_build_state()
        return _compress_image(cloud_image_path)
    except ImageCompressError as exc:
        raise BuildImageError from exc
