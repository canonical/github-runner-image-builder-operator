# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for downloading images from cloud-images.ubuntu.com."""

# gzip needs to be preloaded to extract github runner tar.gz. This is because within the chroot
# env, tarfile module tries to import gzip dynamically and fails.
import gzip  # noqa: F401 # pylint: disable=unused-import
import hashlib
import logging
import typing
from datetime import date
from pathlib import Path

import requests

from github_runner_image_builder.config import Arch, BaseImage
from github_runner_image_builder.errors import BaseImageDownloadError, UnsupportedArchitectureError
from github_runner_image_builder.utils import retry

logger = logging.getLogger(__name__)

SupportedBaseImageArch = typing.Literal["amd64", "arm64", "s390x", "ppc64el"]

CHECKSUM_BUF_SIZE = 65536  # 65kb


def download_and_validate_image(
    arch: Arch, base_image: BaseImage, release_date: date | None = None
) -> Path:
    """Download and verify the base image from cloud-images.ubuntu.com.

    Args:
        arch: The base image architecture to download.
        base_image: The ubuntu base image OS to download.
        release_date: the release date of the base image. If None, latest is picked.

    Returns:
        The downloaded image path.

    Raises:
        BaseImageDownloadError: If there was an error with downloading/verifying the image.
    """
    try:
        bin_arch = _get_supported_runner_arch(arch)
    except UnsupportedArchitectureError as exc:
        logger.exception("Unsupported runner architecture")
        raise BaseImageDownloadError from exc

    image_path_str = f"{base_image.value}-server-cloudimg-{bin_arch}.img"
    image_path = _download_base_image(
        base_image=base_image,
        bin_arch=bin_arch,
        output_filename=image_path_str,
        release_date=release_date,
    )
    shasums = _fetch_shasums(base_image=base_image)
    if image_path_str not in shasums:
        logger.exception("Failed to validate SHASUM for cloud image (checksum not found).")
        raise BaseImageDownloadError("Corresponding checksum not found.")
    if not _validate_checksum(image_path, shasums[image_path_str]):
        logger.exception("Failed to validate SHASUM for cloud image (invalid checksum).")
        raise BaseImageDownloadError("Invalid checksum.")
    return image_path


def _get_supported_runner_arch(arch: Arch) -> SupportedBaseImageArch:
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
        case Arch.S390X:
            return "s390x"
        case Arch.PPC64LE:
            return "ppc64el"  # cloud-images.ubuntu.com uses ppc64el instead of ppc64le
        case _:
            raise UnsupportedArchitectureError(f"Detected system arch: {arch} is unsupported.")


@retry(tries=3, delay=5, max_delay=30, backoff=2, local_logger=logger)
def _download_base_image(
    base_image: BaseImage, bin_arch: str, output_filename: str, release_date: date | None = None
) -> Path:
    """Download the base image.

    Args:
        bin_arch: The ubuntu cloud-image supported arch.
        base_image: The ubuntu base image OS to download.
        output_filename: The output filename of the downloaded image.
        release_date: The release date of the base image. If None, latest is picked.

    Raises:
        BaseImageDownloadError: If there was an error downloaded from cloud-images.ubuntu.com

    Returns:
        The downloaded image path.
    """
    release_dir = release_date.strftime("%Y%m%d") if release_date else "current"
    # The ubuntu-cloud-images is a trusted source
    # Bandit thinks there is no timeout provided for the code below.
    try:
        request = requests.get(
            f"https://cloud-images.ubuntu.com/{base_image.value}/{release_dir}/{base_image.value}"
            f"-server-cloudimg-{bin_arch}.img",
            timeout=60 * 20,
            stream=True,
        )  # nosec: B310, B113
    except requests.exceptions.HTTPError as exc:
        logger.exception("Failed to download base cloud image.")
        raise BaseImageDownloadError from exc
    with open(output_filename, "wb") as file:
        for chunk in request.iter_content(1024 * 1024):  # 1 MB chunks
            file.write(chunk)
    return Path(output_filename)


@retry(tries=3, delay=5, max_delay=30, backoff=2, local_logger=logger)
def _fetch_shasums(base_image: BaseImage, release_date: date | None = None) -> dict[str, str]:
    """Fetch SHA256SUM for given base image.

    Args:
        base_image: The ubuntu base image OS to fetch SHA256SUMs for.
        release_date: The release date of the base image. If None, latest is picked.

    Raises:
        BaseImageDownloadError: If there was an error downloading SHA256SUMS file from \
            cloud-images.ubuntu.com

    Returns:
        A map of image file name to SHA256SUM.
    """
    release_dir = release_date.strftime("%Y%m%d") if release_date else "current"
    try:
        # bandit does not detect that the timeout parameter exists.
        response = requests.get(  # nosec: request_without_timeout
            f"https://cloud-images.ubuntu.com/{base_image.value}/{release_dir}/SHA256SUMS",
            timeout=60 * 5,
        )
    except requests.RequestException as exc:
        logger.exception("Failed to download base cloud image SHA256SUMS file.")
        raise BaseImageDownloadError from exc
    # file consisting of lines <SHA256SUM> *<filename>
    shasum_contents = str(response.content, encoding="utf-8")
    imagefile_to_shasum = {
        sha256_and_file[1].strip("*"): sha256_and_file[0]
        for shasum_line in shasum_contents.strip().splitlines()
        if (sha256_and_file := shasum_line.split())
    }
    return imagefile_to_shasum


def _validate_checksum(file: Path, expected_checksum: str) -> bool:
    """Validate the checksum of a given file.

    Args:
        file: The file to calculate checksum for.
        expected_checksum: The expected file checksum.

    Returns:
        True if the checksums match. False otherwise.
    """
    sha256 = hashlib.sha256()
    with open(file=file, mode="rb") as target_file:
        while data := target_file.read(CHECKSUM_BUF_SIZE):
            sha256.update(data)
    return sha256.hexdigest() == expected_checksum
