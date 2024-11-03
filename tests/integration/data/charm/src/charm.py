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
            self.on[IMAGE_RELATION].relation_joined, self._on_image_relation_joined
        )
        self.framework.observe(
            self.on[IMAGE_RELATION].relation_changed, self._on_image_relation_changed
        )

    def _on_image_relation_joined(self, event: ops.RelationJoinedEvent):
        """Handle the image relation joined event.

        Args:
            event: The event fired when relation is joined.
        """
        logger.info("Relation joined.")
        event.relation.data[self.unit].update(
            {
                "auth_url": self.config["openstack-auth-url"],
                "password": self.config["openstack-password"],
                "project_domain_name": self.config["openstack-project-domain-name"],
                "project_name": self.config["openstack-project-name"],
                "user_domain_name": self.config["openstack-user-domain-name"],
                "username": self.config["openstack-user-name"],
            }
        )
        logger.info("Relation data updated.")

    def _on_image_relation_changed(self, event: ops.RelationChangedEvent):
        """Handle the image relation changed event.

        Args:
            event: The event fired when relation has changed.
        """
        logger.info("Image relation changed.")
        if (
            not event.unit
            or not event.relation.data[event.unit].get("id", "")
            or not event.relation.data[event.unit].get("tags", "")
            or not event.relation.data[event.unit].get("images", "")
        ):
            logger.warning("Relation data not yet set.")
            return
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(RelationCharm)
