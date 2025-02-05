# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with qemu image builder."""
# nosec: B603 is added throughout subprocess calls, make sure that they are running trusted user
# inputs.

import contextlib
import http
import http.client
import logging
import pwd
import shutil

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
import subprocess  # nosec
import tarfile
import urllib.error
import urllib.request
import urllib.response
from io import BytesIO
from pathlib import Path

import requests

from github_runner_image_builder import cloud_image, config, store
from github_runner_image_builder.chroot import ChrootBaseError, ChrootContextManager
from github_runner_image_builder.errors import (
    BuildImageError,
    DependencyInstallError,
    HomeDirectoryChangeOwnershipError,
    ImageCompressError,
    ImageConnectError,
    ImageResizeError,
    NetworkBlockDeviceError,
    PermissionConfigurationError,
    ResizePartitionError,
    RunnerDownloadError,
    SystemUserConfigurationError,
    UnattendedUpgradeDisableError,
    UnmountBuildPathError,
    YarnInstallError,
    YQBuildError,
)
from github_runner_image_builder.utils import retry

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


APT_DEPENDENCIES = [
    "qemu-utils",  # used for qemu utilities tools to build and resize image
    "cloud-utils",  # used for growpart.
    "golang-go",  # used to build yq from source.
]
APT_NONINTERACTIVE_ENV = {"DEBIAN_FRONTEND": "noninteractive"}
SNAP_GO = "go"

# Constants for mounting images
IMAGE_MOUNT_DIR = Path("/mnt/ubuntu-image/")
NETWORK_BLOCK_DEVICE_PATH = Path("/dev/nbd0")
NETWORK_BLOCK_DEVICE_PARTITION_PATH = Path(f"{NETWORK_BLOCK_DEVICE_PATH}p1")

# Constants for building image
# This amount is the smallest increase that caters for the installations within this image.
RESIZE_AMOUNT = "+4G"
MOUNTED_RESOLV_CONF_PATH = IMAGE_MOUNT_DIR / "etc/resolv.conf"
HOST_RESOLV_CONF_PATH = Path("/etc/resolv.conf")

# Constants for disabling automatic apt updates
APT_TIMER = "apt-daily.timer"
APT_SVC = "apt-daily.service"
APT_UPGRADE_TIMER = "apt-daily-upgrade.timer"
APT_UPGRAD_SVC = "apt-daily-upgrade.service"

# Constants for managing users and groups
UBUNTU_USER = "ubuntu"
DOCKER_GROUP = "docker"
MICROK8S_GROUP = "microk8s"
LXD_GROUP = "lxd"
SUDOERS_GROUP = "sudo"
UBUNTU_HOME = Path("/home/ubuntu")
ACTIONS_RUNNER_PATH = UBUNTU_HOME / "actions-runner"

# Constants for packages in the image
YQ_REPOSITORY_URL = "https://github.com/mikefarah/yq.git"
YQ_REPOSITORY_PATH = Path("yq_source")
HOST_YQ_BIN_PATH = Path("/usr/bin/yq")
MOUNTED_YQ_BIN_PATH = IMAGE_MOUNT_DIR / "usr/bin/yq"
IMAGE_HWE_PKG_FORMAT = "linux-generic-hwe-{VERSION}"
SYSCTL_CONF_PATH = Path("/etc/sysctl.conf")


def initialize() -> None:
    """Configure the host machine to build images."""
    logger.info("Installing dependencies.")
    _install_dependencies()
    logger.info("Enabling network block device.")
    _enable_network_block_device()


def _install_dependencies() -> None:
    """Install required dependencies to run qemu image build.

    Raises:
        DependencyInstallError: If there was an error installing apt packages.
    """
    try:
        output = subprocess.check_output(
            ["/usr/bin/apt-get", "update", "-y"],
            encoding="utf-8",
            env=APT_NONINTERACTIVE_ENV,
            timeout=30 * 60,
        )  # nosec: B603
        logger.info("apt-get update out: %s", output)
        output = subprocess.check_output(
            ["/usr/bin/apt-get", "install", "-y", "--no-install-recommends", *APT_DEPENDENCIES],
            encoding="utf-8",
            env=APT_NONINTERACTIVE_ENV,
            timeout=30 * 60,
        )  # nosec: B603
        logger.info("apt-get install out: %s", output)
        output = subprocess.check_output(
            ["/usr/bin/snap", "install", SNAP_GO, "--classic"],
            encoding="utf-8",
            timeout=30 * 60,
        )  # nosec: B603
        logger.info("snap install go out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error installing dependencies, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise DependencyInstallError from exc


def _enable_network_block_device() -> None:
    """Enable network block device module to mount and build chrooted image.

    Raises:
        NetworkBlockDeviceError: If there was an error enable nbd kernel.
    """
    try:
        output = subprocess.check_output(["/usr/sbin/modprobe", "nbd"], timeout=10)  # nosec: B603
        logger.info("modprobe nbd out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error enabling network block device, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise NetworkBlockDeviceError from exc


def run(
    cloud_name: str,
    image_config: config.ImageConfig,
    keep_revisions: int,
) -> str:
    """Build and save the image locally.

    Args:
        cloud_name: The OpenStack cloud to use from clouds.yaml.
        image_config: The target image configuration values.
        keep_revisions: The number of image to keep for snapshot before deletion.

    Raises:
        BuildImageError: If there was an error building the image.

    Returns:
        The built image ID.
    """
    # ensure clean state - if there were errors within the chroot environment (e.g. network error)
    # this guarantees retry-ability
    _unmount_build_path()
    _disconnect_image_to_network_block_device(check=False)

    IMAGE_MOUNT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading base image.")
    base_image_path = cloud_image.download_and_validate_image(
        arch=image_config.arch, base_image=image_config.base
    )
    logger.info("Resizing base image.")
    _resize_image(image_path=base_image_path)
    logger.info("Connecting image to network block device.")
    _connect_image_to_network_block_device(image_path=base_image_path)
    logger.info("Resizing partitions.")
    _resize_mount_partitions()
    logger.info("Installing YQ from source.")
    _install_yq()

    logger.info("Setting up chroot environment.")
    logger.info("Replacing resolv.conf.")
    _replace_mounted_resolv_conf()
    try:
        with ChrootContextManager(IMAGE_MOUNT_DIR):
            _install_apt_packages(base_image=image_config.base)
            logger.info("Disabling unattended upgrades.")
            _disable_unattended_upgrades()
            logger.info("Enabling network optimization policy.")
            _enable_network_fair_queuing_congestion()
            logger.info("Configuring system users.")
            _configure_system_users()
            logger.info("Configuring /usr/local/bin directory.")
            _configure_usr_local_bin()
            logger.info("Installing Yarn.")
            _install_yarn()
            logger.info("Installing GitHub runner.")
            _install_github_runner(arch=image_config.arch, version=image_config.runner_version)
            logger.info("Changing ownership of home directory.")
            _chown_home()
    except ChrootBaseError as exc:
        logger.exception("Error chrooting into %s", IMAGE_MOUNT_DIR)
        raise BuildImageError from exc

    logger.info("Disconnecting image to network block device.")
    _disconnect_image_to_network_block_device(check=True)

    logger.info("Compressing image.")
    _compress_image(base_image_path)

    image = store.upload_image(
        arch=image_config.arch,
        cloud_name=cloud_name,
        image_name=image_config.name,
        image_path=config.IMAGE_OUTPUT_PATH,
        keep_revisions=keep_revisions,
    )
    return image.id


def _disconnect_image_to_network_block_device(check: bool = True) -> None:
    """Disconnect the image to network block device in cleanup for chroot.

    Args:
        check: Whether to raise an error on command failure.

    Raises:
        ImageConnectError: If there was an error disconnecting the image from network block device.
    """
    try:
        result = subprocess.run(  # nosec: B603
            ["/usr/bin/qemu-nbd", "--disconnect", str(NETWORK_BLOCK_DEVICE_PATH)],
            check=check,
            encoding="utf-8",
            timeout=30,
        )
        logger.info(
            "qemu-nbd disconnect nbd code: %s out: %s err: %s",
            result.returncode,
            result.stdout,
            result.stderr,
        )
        result = subprocess.run(  # nosec: B603
            ["/usr/bin/qemu-nbd", "--disconnect", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)],
            check=check,
            encoding="utf-8",
            timeout=30,
        )
        logger.info(
            "qemu-nbd disconnect nbdp1 code: %s out: %s err: %s",
            result.returncode,
            result.stdout,
            result.stderr,
        )
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error disconnecting image to network block device, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise ImageConnectError from exc
    except subprocess.SubprocessError as exc:
        raise ImageConnectError from exc


def _unmount_build_path() -> None:
    """Unmount any mounted paths left by previous build.

    Raises:
        UnmountBuildPathError: if there was an error unmounting previous build state.
    """
    # The commands will fail if artefacts do not exist and hence there is no need to check the
    # output of subprocess runs.
    try:
        output = subprocess.run(
            ["/usr/bin/umount", str(IMAGE_MOUNT_DIR / "dev")],
            timeout=30,
            check=False,
        )  # nosec: B603
        logger.info("umount dev out: %s", output)
        output = subprocess.run(
            ["/usr/bin/umount", str(IMAGE_MOUNT_DIR / "proc")],
            timeout=30,
            check=False,
            capture_output=True,
        )  # nosec: B603
        logger.info("umount proc out: %s", output)
        output = subprocess.run(
            ["/usr/bin/umount", str(IMAGE_MOUNT_DIR / "sys")],
            timeout=30,
            check=False,
            capture_output=True,
        )  # nosec: B603
        logger.info("umount sys out: %s", output)
        output = subprocess.run(
            ["/usr/bin/umount", str(IMAGE_MOUNT_DIR)], timeout=30, check=False, capture_output=True
        )  # nosec: B603
        logger.info("umount ubuntu-image out: %s", output)
        output = subprocess.run(
            ["/usr/bin/umount", str(NETWORK_BLOCK_DEVICE_PATH)],
            timeout=30,
            check=False,
            capture_output=True,
        )  # nosec: B603
        logger.info("umount nbd out: %s", output)
        output = subprocess.run(  # nosec: B603
            ["/usr/bin/umount", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)],
            timeout=30,
            check=False,
            capture_output=True,
        )
        logger.info("umount nbdp1 out: %s", output)
    except subprocess.SubprocessError as exc:
        logger.exception("Unable to unmount build path")
        raise UnmountBuildPathError from exc


def _resize_image(image_path: Path) -> None:
    """Resize image to allow space for dependency installations.

    Args:
        image_path: The target image file to resize.

    Raises:
        ImageResizeError: If there was an error resizing the image.
    """
    try:
        output = subprocess.check_output(  # nosec: B603
            ["/usr/bin/qemu-img", "resize", str(image_path), RESIZE_AMOUNT],
            timeout=60,
        )
        logger.info("qemu-img resize out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error resizing image, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise ImageResizeError from exc
    except subprocess.SubprocessError as exc:
        raise ImageResizeError from exc


def _connect_image_to_network_block_device(image_path: Path) -> None:
    """Connect the image to network block device in preparation for chroot.

    Args:
        image_path: The target image file to connect.

    Raises:
        ImageConnectError: If there was an error connecting the image to network block device.
    """
    try:
        output = subprocess.check_output(  # nosec: B603
            ["/usr/bin/qemu-nbd", f"--connect={NETWORK_BLOCK_DEVICE_PATH}", str(image_path)],
            timeout=60,
        )
        logger.info("qemu-nbd connect out: %s", output)
        _mount_network_block_device_partition()
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error connecting image to network block device, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise ImageConnectError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error connecting to network block device.")
        raise ImageConnectError from exc


# Network block device may fail to mount, retrying will usually fix this.
@retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
def _mount_network_block_device_partition() -> None:
    """Mount the network block device partition."""
    output = subprocess.check_output(  # nosec: B603
        [
            "/usr/bin/mount",
            "-o",
            "rw",
            str(NETWORK_BLOCK_DEVICE_PARTITION_PATH),
            str(IMAGE_MOUNT_DIR),
        ],
        timeout=60,
    )
    logger.info("mount nbd0p1 out: %s", output)


def _resize_mount_partitions() -> None:
    """Resize the block partition to fill available space.

    Raises:
        ResizePartitionError: If there was an error resizing network block device partitions.
    """
    try:
        output = subprocess.check_output(  # nosec: B603
            ["/usr/bin/growpart", str(NETWORK_BLOCK_DEVICE_PATH), "1"], timeout=10 * 60
        )
        logger.info("growpart out: %s", output)
        output = subprocess.check_output(  # nosec: B603
            ["/usr/sbin/resize2fs", str(NETWORK_BLOCK_DEVICE_PARTITION_PATH)],
            timeout=10 * 60,
        )
        logger.info("resize2fs out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error resizing mount partitions, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise ResizePartitionError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running partition resize.")
        raise ResizePartitionError from exc


@retry(tries=3, delay=5, max_delay=30, backoff=2, local_logger=logger)
def _install_yq() -> None:
    """Build and install yq from source.

    Raises:
        YQBuildError: If there was an error building yq from source.
    """
    try:
        if not YQ_REPOSITORY_PATH.exists():
            output = subprocess.check_output(  # nosec: B603
                ["/usr/bin/git", "clone", str(YQ_REPOSITORY_URL), str(YQ_REPOSITORY_PATH)],
                timeout=60 * 10,
            )
            logger.info("git clone out: %s", output)
        else:
            output = subprocess.check_output(  # nosec: B603
                ["/usr/bin/git", "-C", str(YQ_REPOSITORY_PATH), "pull"],
                timeout=60 * 10,
            )
            logger.info("git pull out: %s", output)
        output = subprocess.check_output(  # nosec: B603
            ["/snap/bin/go", "mod", "tidy", "-C", str(YQ_REPOSITORY_PATH)],
            timeout=60 * 10,
        )
        logger.info("go mod tidy out: %s", output)
        output = subprocess.check_output(  # nosec: B603
            ["/snap/bin/go", "build", "-C", str(YQ_REPOSITORY_PATH), "-o", str(HOST_YQ_BIN_PATH)],
            timeout=20 * 60,
        )
        logger.info("go build out: %s", output)
        shutil.copy(HOST_YQ_BIN_PATH, MOUNTED_YQ_BIN_PATH)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error installing yq, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise YQBuildError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running install yq commands.")
        raise YQBuildError from exc


def _replace_mounted_resolv_conf() -> None:
    """Replace resolv.conf to host resolv.conf to allow networking."""
    MOUNTED_RESOLV_CONF_PATH.unlink(missing_ok=True)
    shutil.copy(str(HOST_RESOLV_CONF_PATH), str(MOUNTED_RESOLV_CONF_PATH))


def _install_apt_packages(base_image: config.BaseImage) -> None:
    """Install APT packages on the chroot env.

    Args:
        base_image: The target base image to fetch HWE kernel for.
    """
    # operator_libs_linux apt package uses dpkg -l and that does not work well with
    # chroot env, hence use subprocess run.
    output = subprocess.check_output(
        ["/usr/bin/apt-get", "update", "-y"],
        timeout=60 * 10,
        env=APT_NONINTERACTIVE_ENV,
    )  # nosec: B603
    logger.info("apt-get update out: %s", output)
    output = subprocess.check_output(  # nosec: B603
        [
            "/usr/bin/apt-get",
            "install",
            "-y",
            "--no-install-recommends",
            *config.IMAGE_DEFAULT_APT_PACKAGES,
        ],
        timeout=60 * 20,
        env=APT_NONINTERACTIVE_ENV,
    )
    logger.info("apt-get install out: %s", output)
    # Install HWE kernel to match parity w/ GitHub provided runners.
    output = subprocess.check_output(  # nosec: B603
        [
            "/usr/bin/apt-get",
            "install",
            "-y",
            # https://ubuntu.com/kernel/lifecycle installs recommended packages
            "--install-recommends",
            IMAGE_HWE_PKG_FORMAT.format(VERSION=config.BaseImage.get_version(base_image)),
        ],
        timeout=60 * 20,
        env=APT_NONINTERACTIVE_ENV,
    )
    logger.info("apt-get install HWE kernel out: %s", output)


def _disable_unattended_upgrades() -> None:
    """Disable unatteneded upgrades to prevent apt locks.

    Raises:
        UnattendedUpgradeDisableError: If there was an error disabling unattended upgrade related
            services.
    """
    try:
        # use subprocess run rather than operator-libs-linux's systemd library since the library
        # does not provide full features like mask.
        output = subprocess.check_output(
            ["/usr/bin/systemctl", "disable", APT_TIMER], timeout=30
        )  # nosec: B603
        logger.info("systemctl disable apt timer out: %s", output)
        output = subprocess.check_output(
            ["/usr/bin/systemctl", "mask", APT_SVC], timeout=30
        )  # nosec: B603
        logger.info("systemctl mask apt timer out: %s", output)
        output = subprocess.check_output(  # nosec: B603
            ["/usr/bin/systemctl", "disable", APT_UPGRADE_TIMER], timeout=30
        )
        logger.info("systemctl disable apt upgrade timer out: %s", output)
        output = subprocess.check_output(
            ["/usr/bin/systemctl", "mask", APT_UPGRAD_SVC], timeout=30
        )  # nosec: B603
        logger.info("systemctl mask apt upgrade timer out: %s", output)
        output = subprocess.check_output(  # nosec: B603
            ["/usr/bin/apt-get", "remove", "-y", "unattended-upgrades"],
            env=APT_NONINTERACTIVE_ENV,
            timeout=30,
        )
        logger.info("apt-get remove unattended-upgrades out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error disabling unattended upgrades, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise UnattendedUpgradeDisableError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running unattended upgrades disable commands.")
        raise UnattendedUpgradeDisableError from exc


def _enable_network_fair_queuing_congestion() -> None:
    """Enable bbr traffic congestion algorithm."""
    with open(SYSCTL_CONF_PATH, mode="a", encoding="utf-8") as sysctl_file:
        sysctl_file.write("net.core.default_qdisc=fq\n")
        sysctl_file.write("net.ipv4.tcp_congestion_control=bbr\n")


def _configure_system_users() -> None:
    """Configure system users.

    Raises:
        SystemUserConfigurationError: If there was an error configuring ubuntu user.
    """
    try:
        output = subprocess.check_output(  # nosec: B603
            ["/usr/sbin/useradd", "-m", UBUNTU_USER], timeout=30
        )
        logger.info("useradd ubunutu out: %s", output)
        with (UBUNTU_HOME / ".profile").open("a") as profile_file:
            profile_file.write(f"PATH=$PATH:{UBUNTU_HOME}/.local/bin\n")
        with (UBUNTU_HOME / ".bashrc").open("a") as bashrc_file:
            bashrc_file.write(f"PATH=$PATH:{UBUNTU_HOME}/.local/bin\n")
        output = subprocess.check_output(
            ["/usr/sbin/groupadd", MICROK8S_GROUP], timeout=30
        )  # nosec: B603
        logger.info("groupadd microk8s out: %s", output)
        output = subprocess.check_output(  # nosec: B603
            [
                "/usr/sbin/usermod",
                "-aG",
                f"{DOCKER_GROUP},{MICROK8S_GROUP},{LXD_GROUP},{SUDOERS_GROUP}",
                UBUNTU_USER,
            ],
            timeout=30,
        )
        logger.info("usrmod to ubuntu user out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error disabling unattended upgrades, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise SystemUserConfigurationError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running system user configuration commands.")
        raise SystemUserConfigurationError from exc


def _configure_usr_local_bin() -> None:
    """Change the permissions of /usr/local/bin dir to match GH hosted runners permissions.

    Raises:
        PermissionConfigurationError: if there was an error changing permissions.
    """
    try:
        # The 777 is to match the behavior of GitHub hosted runners
        output = subprocess.check_output(  # nosec: B603
            ["/usr/bin/chmod", "777", "/usr/local/bin"], timeout=30
        )
        logger.info("chmod /usr/local/bin out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error changing /usr/local/bin/ permissions, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise PermissionConfigurationError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running system user bin directory configuration commands.")
        raise PermissionConfigurationError from exc


def _install_yarn() -> None:
    """Install yarn using NPM.

    Raises:
        YarnInstallError: If there was an error installing external package.
    """
    try:
        # 2024/04/26 There's a potential security risk here, npm is subject to toolchain attacks.
        output = subprocess.check_output(
            ["/usr/bin/npm", "install", "--global", "yarn"], timeout=60 * 5
        )  # nosec: B603
        logger.info("npm install yarn out: %s", output)
        output = subprocess.check_output(
            ["/usr/bin/npm", "cache", "clean", "--force"], timeout=60
        )  # nosec: B603
        logger.info("npm cache clean out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error installing Yarn, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise YarnInstallError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running Yarn installation commands.")
        raise YarnInstallError from exc


def _install_github_runner(arch: config.Arch, version: str) -> None:
    """Download and install github runner.

    Args:
        arch: The architecture of the host image.
        version: The runner version to download.

    Raises:
        RunnerDownloadError: If there was an error downloading runner.
    """
    try:
        version = _get_github_runner_version(version)
    except _FetchVersionError as exc:
        logger.exception("Error fetching github runner version.")
        raise RunnerDownloadError("Failed to fetch latest GitHub runner version.") from exc

    try:
        tar_res: http.client.HTTPResponse
        # The github releases URL is safe to open
        with urllib.request.urlopen(  # nosec: B310
            f"https://github.com/actions/runner/releases/download/v{version}/"
            f"actions-runner-linux-{arch.value}-{version}.tar.gz"
        ) as tar_res:
            tar_bytes = tar_res.read()
    except urllib.error.URLError as exc:
        logger.exception("Error downloading GitHub runner tar.gz.")
        raise RunnerDownloadError("Error downloading runner tar archive.") from exc
    ACTIONS_RUNNER_PATH.mkdir(parents=True, exist_ok=True)
    try:
        with contextlib.closing(tarfile.open(name=None, fileobj=BytesIO(tar_bytes))) as tar_file:
            # the tar file provided by GitHub can be trusted
            tar_file.extractall(path=ACTIONS_RUNNER_PATH)  # nosec: B202
    except tarfile.TarError as exc:
        logger.exception("Error extracting GitHub runner tar.gz.")
        raise RunnerDownloadError("Error extracting runner tar archive.") from exc
    ubuntu_user = pwd.getpwnam(UBUNTU_USER)
    try:
        subprocess.check_call(  # nosec: B603
            [
                "/usr/bin/chown",
                "-R",
                f"{ubuntu_user.pw_uid}:{ubuntu_user.pw_gid}",
                str(ACTIONS_RUNNER_PATH),
            ],
            timeout=60,
        )
    except subprocess.SubprocessError as exc:
        logger.exception("Error changing ownership of GitHub runner directory.")
        raise RunnerDownloadError("Error changing GitHub runner directory.") from exc


class _FetchVersionError(Exception):
    """Represents an error fetching latest GitHub runner version."""


def _get_github_runner_version(version: str) -> str:
    """Get GitHub runner's latest version number if version is not specified.

    Args:
        version: The user provided version.

    Returns:
        The latest GitHub runner version number or user provided version.

    Raises:
        _FetchVersionError: if there was an error getting the latest GitHub version.
    """
    if version:
        return version.lstrip("v")
    try:
        # False positive on bandit that thinks this has no timeout.
        redirect_res = requests.get(  # nosec: B113
            "https://github.com/actions/runner/releases/latest",
            timeout=60 * 30,
            allow_redirects=False,
        )
    except requests.exceptions.RequestException as exc:
        raise _FetchVersionError("Unable to fetch the latest release version.") from exc
    if not redirect_res.is_redirect or not (
        latest_version := redirect_res.headers.get("Location", "").split("/")[-1]
    ):
        raise _FetchVersionError("Failed to get latest runner version, invalid redirect.")
    return latest_version.lstrip("v")


def _chown_home() -> None:
    """Change the ownership of Ubuntu home directory.

    Raises:
        HomeDirectoryChangeOwnershipError: If there was an error changing the home directory
        ownership to ubuntu:ubuntu.
    """
    try:
        subprocess.check_call(
            ["/usr/bin/chown", "--recursive", "ubuntu:ubuntu", "/home/ubuntu"],  # nosec
            timeout=60 * 10,
        )
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error changing home directory ownership, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise HomeDirectoryChangeOwnershipError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error changing home directory ownership command.")
        raise HomeDirectoryChangeOwnershipError from exc


# Image compression might fail for arbitrary reasons - retrying usually solves this.
@retry(tries=5, delay=5, max_delay=60, backoff=2, local_logger=logger)
def _compress_image(image: Path) -> None:
    """Compress the image.

    Args:
        image: The image to compress.

    Raises:
        ImageCompressError: If there was something wrong compressing the image.
    """
    try:
        output = subprocess.check_output(  # nosec: B603
            [
                "/usr/bin/sudo",
                "/usr/bin/qemu-img",
                "convert",
                "-c",  # compress
                "-f",  # input format
                "qcow2",
                "-O",  # output format
                "qcow2",
                str(image),
                str(config.IMAGE_OUTPUT_PATH),
            ],
            timeout=60 * 10,
        )
        logger.info("qemu-img convert compress out: %s", output)
    except subprocess.CalledProcessError as exc:
        logger.exception(
            "Error compressing image, cmd: %s, code: %s, err: %s",
            exc.cmd,
            exc.returncode,
            exc.output,
        )
        raise ImageCompressError from exc
    except subprocess.SubprocessError as exc:
        logger.exception("Error running image compression command.")
        raise ImageCompressError from exc
