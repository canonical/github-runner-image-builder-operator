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

IMAGE_RELATION = "image"


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
            charm.on[IMAGE_RELATION].relation_joined, self._on_image_relation_joined
        )

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_image_relation_joined(self, _: ops.RelationJoinedEvent) -> None:
        """Handle the image relation joined event."""
        build_config = state.BuilderRunConfig.from_charm(charm=self.charm)
        image_id = builder.get_latest_image(
            arch=build_config.arch,
            base=build_config.base,
            cloud_name=build_config.cloud_name,
        )
        if not image_id:
            logger.warning("Image not yet ready.")
            return
        self.update_image_data(image_id=image_id, arch=build_config.arch, base=build_config.base)

    def update_image_data(
        self,
        image_id: str,
        arch: state.Arch,
        base: state.BaseImage,
    ) -> None:
        """Update the relation data if exists.

        Args:
            image_id: The latest image ID to propagate.
            arch: The architecture in which the image was built for.
            base: The OS base image.
        """
        for relation in self.model.relations[IMAGE_RELATION]:
            relation.data[self.model.unit].update(
                ImageRelationData(id=image_id, tags=",".join((arch.value, base.value)))
            )
