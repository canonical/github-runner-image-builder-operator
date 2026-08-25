# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for uploading images to shareable storage."""

import logging
from pathlib import Path
from typing import cast

import openstack
import openstack.connection
import openstack.exceptions
from openstack.compute.v2.server import Server
from openstack.image.v2.image import Image

from github_runner_image_builder.config import Arch
from github_runner_image_builder.errors import OpenstackError, UploadImageError

logger = logging.getLogger(__name__)

# Timeout constants (in seconds)
SNAPSHOT_CREATION_TIMEOUT = 60 * 30  # 30 minutes
TMP_IMAGE_NAME_SUFFIX = "-tmp"
FILE_MD5_PROPERTY = "owner_specified.openstack.md5"
FILE_SHA256_PROPERTY = "owner_specified.openstack.sha256"
ACTIVE_IMAGE_STATUS = "active"
SHA256_ALGORITHM = "sha256"


def create_snapshot(
    cloud_name: str, image_name: str, server: Server, keep_revisions: int
) -> Image:
    """Upload image to openstack glance.

    Args:
        cloud_name: The Openstack cloud to use from clouds.yaml.
        image_name: The image name to upload as.
        server: The running OpenStack server to snapshot.
        keep_revisions: The number of revisions to keep for an image.

    Raises:
        UploadImageError: If there was an error uploading the image to Openstack Glance.

    Returns:
        The created image.
    """
    with openstack.connect(cloud=cloud_name) as connection:
        try:
            logger.info("Creating image snapshot, %s %s", image_name, server.name)
            image: Image = connection.create_image_snapshot(
                name=image_name, server=server.id, wait=True, timeout=SNAPSHOT_CREATION_TIMEOUT
            )
            logger.info("Pruning older snapshots, %s keeping %s.", image_name, keep_revisions)
            _prune_old_images(
                connection=connection, image_name=image_name, num_revisions=keep_revisions
            )
            logger.info("Snapshot created successfully, %s %s.", image_name, image.id)
            return image
        except openstack.exceptions.SDKException as exc:
            logger.exception("Error while creating snapshot (Base).")
            raise UploadImageError from exc


def upload_image(
    arch: Arch, cloud_name: str, image_name: str, image_path: Path, keep_revisions: int
) -> Image:
    """Upload image to openstack glance.

    Args:
        arch: The image architecture.
        cloud_name: The Openstack cloud to use from clouds.yaml.
        image_name: The image name to upload as.
        image_path: The path to image to upload.
        keep_revisions: The number of revisions to keep for an image.

    Raises:
        UploadImageError: If there was an error uploading the image to Openstack Glance.

    Returns:
        The created image.
    """
    tmp_image_name = f"{image_name}{TMP_IMAGE_NAME_SUFFIX}"
    with openstack.connect(cloud=cloud_name) as connection:
        try:
            _delete_images_by_name(connection=connection, image_name=tmp_image_name)

            logger.info("Uploading image %s.", tmp_image_name)
            image_properties = {"architecture": arch.to_openstack()}
            # ignore type since the library does not provide correct type hinting but the docstring
            # does define the return type.
            image: Image = connection.create_image(
                name=tmp_image_name,
                filename=str(image_path),
                properties=image_properties,
                allow_duplicates=True,
                wait=True,
                # Required for the locally computed hashes to be recorded on the image.
                validate_checksum=True,
            )  # type: ignore
            _validate_image_checksums(image=image)
            logger.info("Renaming image %s to %s.", tmp_image_name, image_name)
            image = cast(Image, connection.image.update_image(image, name=image_name))
            logger.info("Pruning older images %s, keeping %s.", image_name, keep_revisions)
            _prune_old_images(
                connection=connection, image_name=image_name, num_revisions=keep_revisions
            )
            logger.info("Image created successfully, %s %s.", image_name, image.id)
            return image
        except openstack.exceptions.OpenStackCloudException as exc:
            logger.exception("Error while uploading image.")
            raise UploadImageError from exc
        finally:
            # The temporary image is renamed on success, meaning this only has an effect if the
            # upload did not complete.
            _delete_images_by_name_quietly(connection=connection, image_name=tmp_image_name)


def _delete_images_by_name(connection: openstack.connection.Connection, image_name: str) -> None:
    """Delete every image matching the given name.

    Args:
        connection: The connected openstack cloud instance.
        image_name: The exact image name to delete.
    """
    for image in connection.image.images(name=image_name):
        logger.info("Deleting image %s %s.", image_name, image.id)
        connection.delete_image(image.id, wait=True)


def _delete_images_by_name_quietly(
    connection: openstack.connection.Connection, image_name: str
) -> None:
    """Delete every image matching the given name, logging instead of raising on failure.

    Args:
        connection: The connected openstack cloud instance.
        image_name: The exact image name to delete.
    """
    try:
        _delete_images_by_name(connection=connection, image_name=image_name)
    except openstack.exceptions.OpenStackCloudException:
        # Raising here would mask the original error, the leftover image is deleted on the next
        # upload instead.
        logger.exception("Failed to clean up image %s.", image_name)


def _validate_image_checksums(image: Image) -> None:
    """Compare the hashes Glance computed against the hashes computed locally during upload.

    Args:
        image: The uploaded image.

    Raises:
        UploadImageError: If the hashes are missing or do not match.
    """
    properties = image.properties or {}
    local_md5 = properties.get(FILE_MD5_PROPERTY)
    local_sha256 = properties.get(FILE_SHA256_PROPERTY)
    if not local_md5 or not local_sha256:
        raise UploadImageError(f"Image {image.name} is missing the locally computed hashes.")
    if image.checksum != local_md5:
        raise UploadImageError(
            f"Checksum mismatch for image {image.name}, md5: {image.checksum} != {local_md5}."
        )
    # Glance computes the multihash with the algorithm it is configured with, which is not
    # necessarily the sha256 that openstacksdk computes locally.
    if image.hash_algo == SHA256_ALGORITHM and image.hash_value != local_sha256:
        raise UploadImageError(
            f"Checksum mismatch for image {image.name}, "
            f"sha256: {image.hash_value} != {local_sha256}."
        )


def _prune_old_images(
    connection: openstack.connection.Connection, image_name: str, num_revisions: int
) -> None:
    """Remove old images outside of number of revisions to keep.

    Args:
        connection: The connected openstack cloud instance.
        image_name: The image name to search for.
        num_revisions: The number of revisions to keep.

    Raises:
        OpenstackError: if there was an error deleting the images.
    """
    # Images left behind in a non-active status by a failed upload have to be pruned as well,
    # otherwise they accumulate forever.
    images = _get_sorted_images_by_created_at(
        connection=connection, image_name=image_name, active_only=False
    )
    if not images:
        return
    images_to_prune = images[num_revisions:]
    for image in images_to_prune:
        try:
            if not connection.delete_image(image.id, wait=True):
                logger.exception("Failed to delete image %s:%s.", image.name, image.id)
                raise OpenstackError(f"Failed to delete image: {image.id}")
        except openstack.exceptions.OpenStackCloudException as exc:
            raise OpenstackError from exc


def get_latest_build_id(cloud_name: str, image_name: str, active_only: bool = True) -> str:
    """Fetch the latest image id.

    Args:
        cloud_name: The Openstack cloud to use from clouds.yaml.
        image_name: The image name to search for.
        active_only: If True (default), only return active images. If False, return the
            latest image in any upload status (including saving/queued).

    Returns:
        The image ID if exists, empty string otherwise.
    """
    with openstack.connect(cloud=cloud_name) as connection:
        images = _get_sorted_images_by_created_at(
            connection=connection, image_name=image_name, active_only=active_only
        )
        if not active_only:
            # An upload in progress is still under its temporary name.
            images = _sort_images_by_created_at(
                images
                + _get_sorted_images_by_created_at(
                    connection=connection,
                    image_name=f"{image_name}{TMP_IMAGE_NAME_SUFFIX}",
                    active_only=False,
                )
            )
        if not images:
            return ""
        # The type of ID is in string but the library does not provide correct type hints for it.
        return images[0].id  # type: ignore


def _get_sorted_images_by_created_at(
    connection: openstack.connection.Connection,
    image_name: str,
    active_only: bool = True,
) -> list[Image]:
    """Fetch the images sorted by created_at date.

    Args:
        connection: The connected openstack cloud instance.
        image_name: The exact image name to search for.
        active_only: If True (default), only images that finished uploading are returned.

    Raises:
        OpenstackError: if there was an error fetching the images.

    Returns:
        The images sorted by created_at date with latest first.
    """
    try:
        images = list(connection.image.images(name=image_name))
    except openstack.exceptions.OpenStackCloudException as exc:
        logger.exception("Failed to search images with name %s.", image_name)
        raise OpenstackError from exc
    if active_only:
        images = [image for image in images if image.status == ACTIVE_IMAGE_STATUS]
    return _sort_images_by_created_at(images)


def _sort_images_by_created_at(images: list[Image]) -> list[Image]:
    """Sort images by their creation date, latest first.

    Args:
        images: The images to sort.

    Returns:
        The images sorted by created_at date with latest first.
    """
    # The type of images are list[Image] but the library does not provide correct type hints for
    # it.
    return sorted(images, key=lambda image: image.created_at, reverse=True)  # type: ignore
