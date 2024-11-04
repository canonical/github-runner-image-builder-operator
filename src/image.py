# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Github-runner-image-builder-operator image relation observer."""

import json
import logging
from collections import defaultdict
from typing import TypedDict

import ops

import builder
import charm_utils
import state

logger = logging.getLogger(__name__)


class ImageRelationData(TypedDict, total=False):
    """Relation data for providing image ID.

    Attributes:
        id: The latest image ID to provide.
        tags: The comma separated tags of the image, e.g. x64, jammy.
        images: JSON formatted list of image dictionary {id: str, tags: str}.
    """

    id: str
    tags: str
    images: str | None


class Observer(ops.Object):
    """The image relation observer."""

    def __init__(self, charm: ops.CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "image-observer")
        self.charm = charm

        charm.framework.observe(
            charm.on[state.IMAGE_RELATION].relation_joined, self._on_image_relation_joined
        )

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_image_relation_joined(self, event: ops.RelationJoinedEvent) -> None:
        """Handle the image relation joined event.

        Args:
            event: The event emitted when a relation is joined.
        """
        build_config = state.BuilderRunConfig.from_charm(charm=self.charm)
        if not build_config.cloud_config.upload_cloud_ids:
            self.model.unit.status = ops.BlockedStatus(
                f"{state.IMAGE_RELATION} integration required."
            )
            return
        unit_cloud_auth_config = state.CloudsAuthConfig.from_unit_relation_data(
            data=event.relation.data[event.unit]
        )
        if not unit_cloud_auth_config:
            logger.warning("Unit relation data not yet ready.")
            return
        builder.install_clouds_yaml(build_config.cloud_config.openstack_clouds_config)
        cloud_images = builder.get_latest_images(
            config=build_config, cloud_id=unit_cloud_auth_config.get_id()
        )
        if not cloud_images:
            logger.info("Image not yet ready for %s.", event.unit.name)
            return
        self.update_image_data(cloud_images=[cloud_images])

    def update_image_data(
        self,
        cloud_images: list[list[builder.CloudImage]],
    ) -> None:
        """Update relation data for each cloud coming from image requires side of relation.

        Args:
            cloud_images: The cloud id and image ids to propagate via relation data.
        """
        cloud_id_to_image_ids = _build_cloud_to_images_map(cloud_images=cloud_images)
        for relation in self.model.relations[state.IMAGE_RELATION]:
            # There is no need to test for case with no units
            for unit in relation.units:  # pragma: no branch
                unit_auth_data = state.CloudsAuthConfig.from_unit_relation_data(
                    data=relation.data[unit]
                )
                if (
                    not unit_auth_data
                    or (cloud_id := unit_auth_data.get_id()) not in cloud_id_to_image_ids
                ):
                    logger.warning("Cloud auth data not found in relation with %s", unit.name)
                    continue
                relation.data[self.model.unit].update(
                    _cloud_images_to_relation_data(cloud_images=cloud_id_to_image_ids[cloud_id])
                )
                # the relation data update is required only once per relation since every units in
                # the relation share the same OpenStack cloud credentials.
                break


def _build_cloud_to_images_map(
    cloud_images: list[list[builder.CloudImage]],
) -> dict[str, list[builder.CloudImage]]:
    """Build a map of cloud id to cloud_images.

    Args:
        cloud_images: The cloud id and image ids to propagate via relation data.

    Returns:
        The map of cloud_id to cloud images.
    """
    cloud_id_to_image_ids: dict[str, list[builder.CloudImage]] = defaultdict(list)
    for images in cloud_images:
        for image in images:
            cloud_id_to_image_ids[image.cloud_id].append(image)
    return cloud_id_to_image_ids


def _cloud_images_to_relation_data(cloud_images: list[builder.CloudImage]) -> ImageRelationData:
    """Transform cloud images data to relation data.

    Args:
        cloud_images: The images built for a cloud.

    Raises:
        ValueError: if no images were available for parsing.

    Returns:
        The image relation data for a unit.
    """
    if not cloud_images:
        raise ValueError("No images to parse to relation data.")
    primary = cloud_images[0]
    return ImageRelationData(
        id=primary.image_id,
        tags=_format_tags(image=primary),
        images=json.dumps(
            list(
                ImageRelationData(id=image.image_id, tags=_format_tags(image=image))
                for image in cloud_images
            )
        ),
    )


def _format_tags(image: builder.CloudImage) -> str:
    """Generate image tags.

    Args:
        image: The cloud image.

    Returns:
        The CSV formatted tags.
    """
    tag_str = ",".join(tag for tag in (image.arch.value, image.base.value) if tag)
    if image.juju:
        tag_str += f",juju={image.juju}"
    if image.microk8s:
        tag_str += f",microk8s={image.microk8s}"
    return tag_str
