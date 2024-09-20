# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Github-runner-image-builder-operator image relation observer."""

import logging
from typing import TypedDict

import ops

import builder
import charm_utils
import state

logger = logging.getLogger(__name__)


class ImageRelationData(TypedDict):
    """Relation data for providing image ID.

    Attributes:
        id: The latest image ID to provide.
        tags: The comma separated tags of the image, e.g. x64, jammy.
    """

    id: str
    tags: str


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
        if not build_config.upload_cloud_ids:
            self.model.unit.status = ops.WaitingStatus("Waiting for relation data.")
            return
        unit_cloud_auth_config = state.CloudsAuthConfig.from_unit_relation_data(
            data=event.relation.data[event.unit]
        )
        if not unit_cloud_auth_config:
            logger.warning("Unit relation data not yet ready.")
            return
        image_id = builder.get_latest_image(
            arch=build_config.arch,
            base=build_config.base,
            cloud_name=(cloud_id := unit_cloud_auth_config.get_id()),
        )
        if not image_id:
            logger.warning("Image not yet ready.")
            return
        self.update_image_data(
            cloud_image_ids=[builder.CloudImage(cloud_id=cloud_id, image_id=image_id)],
            arch=build_config.arch,
            base=build_config.base,
        )

    def update_image_data(
        self,
        cloud_image_ids: list[builder.CloudImage],
        arch: state.Arch,
        base: state.BaseImage,
    ) -> None:
        """Update the relation data if image exists for according cloud supplied by the relation \
        data.

        Args:
            cloud_image_ids: The cloud id and image id pairs to propagate via relation data.
            arch: The architecture in which the image was built for.
            base: The OS base image.
        """
        cloud_id_to_image_id = {
            cloud_image.cloud_id: cloud_image.image_id for cloud_image in cloud_image_ids
        }
        for relation in self.model.relations[state.IMAGE_RELATION]:
            # There is no need to test for case with no units (95->94)
            for unit in relation.units:  # pragma: no cover
                unit_auth_data = state.CloudsAuthConfig.from_unit_relation_data(
                    data=relation.data[unit]
                )
                if (
                    not unit_auth_data
                    or (cloud_id := unit_auth_data.get_id()) not in cloud_id_to_image_id
                ):
                    logger.warning("Cloud auth data not found in relation with %s", unit.name)
                    continue
                relation.data[self.model.unit].update(
                    ImageRelationData(
                        id=cloud_id_to_image_id[cloud_id],
                        tags=",".join((arch.value, base.value)),
                    )
                )
                # the relation data update is required only once per relation since every units in
                # the relation share the same OpenStack cloud credentials.
                break
