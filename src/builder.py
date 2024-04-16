# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""

import dataclasses
import hashlib
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Literal

from charms.operator_libs_linux.v0 import apt, passwd

from chroot import ChrootBaseError, ChrootContextManager
from state import Arch, BaseImage

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
        subprocess.run(["sudo", "modprobe", "nbd"], check=True, timeout=10)
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
        ["qemu-nbd", "--disconnect", str(NETWORK_BLOCK_DEVICE_PATH)], timeout=30, check=False
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
        subprocess.run(
            ["qemu-img", "resize", str(cloud_image_path), "+1.5G"], check=True, timeout=60
        )
    except subprocess.CalledProcessError as exc:
        raise ImageResizeError from exc


class ImageMountError(Exception):
    """Represents an error while mounting the image to network block device."""


def _mount_image_to_network_block_device(cloud_image_path: Path) -> None:
    """Mount the image to network block device in preparation for chroot.

    Args:
        cloud_image_path: The target cloud image file to mount.

    Raises:
        ImageMountError: If there was an error mounting the image to network block device.
    """
    try:
        subprocess.run(
            ["qemu-nbd", f"--connect={NETWORK_BLOCK_DEVICE_PATH}", str(cloud_image_path)],
            check=True,
            timeout=60,
        )
        subprocess.run(
            ["mount", "-o", "rw", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH), str(IMAGE_MOUNT_DIR)],
            check=True,
            timeout=60,
        )
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
        subprocess.run(
            ["growpart", str(NETWORK_BLOCK_DEVICE_PATH), "1"],
            check=True,
            timeout=60,
        )
        subprocess.run(
            ["resize2fs", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)],
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
        subprocess.run(["/usr/bin/systemctl", "stop", APT_TIMER], check=True, timeout=30)
        subprocess.run(["/usr/bin/systemctl", "disable", APT_TIMER], check=True, timeout=30)
        subprocess.run(["/usr/bin/systemctl", "mask", APT_SVC], check=True, timeout=30)
        subprocess.run(["/usr/bin/systemctl", "stop", APT_UPGRADE_TIMER], check=True, timeout=30)
        subprocess.run(
            ["/usr/bin/systemctl", "disable", APT_UPGRADE_TIMER], check=True, timeout=30
        )
        subprocess.run(["/usr/bin/systemctl", "mask", APT_UPGRAD_SVC], check=True, timeout=30)
        subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True, timeout=30)
        apt.remove_package("unattended-upgrades")
    except (subprocess.SubprocessError, apt.PackageNotFoundError) as exc:
        raise UnattendedUpgradeDisableError from exc


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


def _install_external_packages(arch: Arch) -> None:
    """Install packages outside of apt.

    Installs yarn, yq.

    Args:
        arch: The architecture to download binaries for. #TODO check bin arch

    Raises:
        ExternalPackageInstallError: If there was an error installing external package.
    """
    try:
        subprocess.run(["/usr/bin/npm", "install", "--global", "yarn"], check=True, timeout=60)
        subprocess.run(["/usr/bin/npm", "cache", "clean", "--force"], check=True, timeout=60)
        urllib.request.urlretrieve(YQ_DOWNLOAD_URL_TMPL.format(BIN_ARCH=arch.value), "yq")
        urllib.request.urlretrieve(YQ_BINARY_CHECKSUM_URL, "checksums")
        urllib.request.urlretrieve(YQ_CHECKSUM_HASHES_ORDER_URL, "checksums_hashes_order")
        urllib.request.urlretrieve(YQ_EXTRACT_CHECKSUM_SCRIPT_URL, "extract-checksum.sh")
        # The output is <BIN_NAME> <CHECKSUM>
        checksum = subprocess.check_output(
            ["/usr/bin/bash", "extract-checksum.sh", "SHA-256", "yq"], encoding="utf-8", timeout=60
        ).split()[1]
        yq = Path("yq")
        yq.chmod(755)
        yq.rename("/usr/bin/yq")
        if not _validate_checksum(yq, checksum):
            raise ExternalPackageInstallError("Invalid checksum")
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
        subprocess.run(
            ["virt-sparsify", "--compress", str(image), "compressed.img"], check=True, timeout=60
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

UBUNTU_USER = "ubuntu"
DOCKER_GROUP = "docker"
MICROK8S_GROUP = "microk8s"


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
        _resize_mount_partitions()
    except (CloudImageDownloadError, ResizePartitionError, ImageMountError) as exc:
        raise BuildImageError from exc

    try:
        with ChrootContextManager(IMAGE_MOUNT_DIR):
            _replace_mounted_resolv_conf()
            apt.add_package(IMAGE_DEFAULT_APT_PACKAGES, update_cache=True)
            _create_python_symlinks()
            _disable_unattended_upgrades()
            passwd.add_user(UBUNTU_USER)
            passwd.add_group(MICROK8S_GROUP)
            passwd.add_user_to_group(UBUNTU_USER, MICROK8S_GROUP)
            passwd.add_user_to_group(UBUNTU_USER, DOCKER_GROUP)
            _install_external_packages(arch=config.arch)
    except ChrootBaseError as exc:
        raise BuildImageError from exc

    try:
        return _compress_image(cloud_image_path)
    except ImageCompressError as exc:
        raise BuildImageError from exc
