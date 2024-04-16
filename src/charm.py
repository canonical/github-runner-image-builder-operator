#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import logging
from typing import Any

import ops

import builder
import cron
import image
import openstack_manager
from state import CharmConfigInvalidError, CharmState

logger = logging.getLogger(__name__)


class GithubRunnerImageBuilderCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: Any):
        """Initialize the charm.

        Args:
            args: The CharmBase initialization arguments.
        """
        super().__init__(*args)
        self.image_observer = image.Observer(self)
        print(self.image_observer)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.build_image_action, self._on_build_image_action)

    def _load_state(self) -> CharmState | None:
        """Load the charm state if valid, set charm to blocked if otherwise.

        Returns:
            Initialized charm state if valid charm state. None if invalid charm state was found.
        """
        try:
            return CharmState.from_charm(self)
        except CharmConfigInvalidError as exc:
            self.unit.status = ops.BlockedStatus(str(exc))
            return None

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.
        """
        builder.setup_builder()

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        state = self._load_state()
        if not state:
            return

        build_config = builder.BuildImageConfig(
            arch=state.image_config.arch, base_image=state.image_config.base_image
        )
        image_path = builder.build_image(config=build_config)
        upload_config = openstack_manager.UploadImageConfig(
            arch=state.image_config.arch,
            base=state.image_config.base_image,
            num_revisions=state.revision_history_limit,
            src_path=image_path,
        )
        with openstack_manager.OpenstackManager(cloud_config=state.cloud_config) as openstack:
            image_id = openstack.upload_image(config=upload_config)

        self.image_observer.update_relation_data(image_id=image_id)
        cron.setup(
            interval=state.build_interval, unit_name=self.unit.name, action_name="build-image"
        )

    def _on_build_image_action(self, event: ops.ActionEvent) -> None:
        """Handle build image action.

        Args:
            event: The build image action event.
        """
        state = self._load_state()
        if not state:
            return

        build_config = builder.BuildImageConfig(
            arch=state.image_config.arch, base_image=state.image_config.base_image
        )
        image_path = builder.build_image(config=build_config)
        upload_config = openstack_manager.UploadImageConfig(
            arch=state.image_config.arch,
            base=state.image_config.base_image,
            num_revisions=state.revision_history_limit,
            src_path=image_path,
        )
        with openstack_manager.OpenstackManager(cloud_config=state.cloud_config) as openstack:
            image_id = openstack.upload_image(config=upload_config)

        self.image_observer.update_relation_data(image_id=image_id)
        event.set_results({"id": image_id})


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
