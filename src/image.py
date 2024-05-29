# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Github-runner-image-builder-operator image relation observer."""

import logging
from typing import TypedDict

import ops

import builder
from state import CharmConfigInvalidError, CharmState

logger = logging.getLogger(__name__)

IMAGE_RELATION = "image"


class ImageRelationData(TypedDict):
    """Relation data for providing image ID.

    Attributes:
        id: The latest image ID to provide.
    """

    id: str


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

    def _load_state(self) -> CharmState | None:
        """Load the charm state if valid, set charm to blocked if otherwise.

        Returns:
            Initialized charm state if valid charm state. None if invalid charm state was found.
        """
        try:
            return CharmState.from_charm(self.charm)
        except CharmConfigInvalidError as exc:
            self.charm.unit.status = ops.BlockedStatus(str(exc))
            return None

    def _on_image_relation_joined(self, _: ops.RelationJoinedEvent) -> None:
        """Handle the image relation joined event."""
        state = self._load_state()
        if not state:
            return

        image_id = builder.get_latest_image(
            base=state.image_config.base_image,
            app_name=self.charm.app.name,
            arch=state.image_config.arch,
            cloud_name=state.cloud_name,
        )
        if not image_id:
            logger.warning("Image not yet ready.")
            return
        self.update_image_id(image_id=image_id)

    def update_image_id(self, image_id: str) -> None:
        """Update the relation data if exists.

        Args:
            image_id: The latest image ID to propagate.
        """
        for relation in self.model.relations[IMAGE_RELATION]:
            relation.data[self.model.unit].update(ImageRelationData(id=image_id))
