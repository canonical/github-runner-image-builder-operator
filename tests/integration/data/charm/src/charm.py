#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import logging
from typing import Any

import ops

logger = logging.getLogger(__name__)

IMAGE_RELATION = "image"


class RelationCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: Any):
        """Initialize the charm.

        Args:
            args: The CharmBase initialization arguments.
        """
        super().__init__(*args)
        self.framework.observe(
            self.on[IMAGE_RELATION].relation_changed, self._on_image_relation_changed
        )

    def _on_image_relation_changed(self, event: ops.RelationChangedEvent):
        """Handle the image relation changed event.

        Args:
            event: The event fired when relation has changed.
        """
        logger.info("Image relation changed.")
        if not event.unit or event.relation.data[event.unit].get("id", None):
            logger.warning("Relation data not yet set.")
            return
        logger.info("Image relation changed.")
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(RelationCharm)
