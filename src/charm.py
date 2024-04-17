#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import logging
from datetime import timedelta
from typing import Any

import ops
from charms.resurrect.v0.resurrect import Resurrect, ResurrectEvent

import builder
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
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.build_image_action, self._on_build_image_action)

        state = self._load_state()
        if not state:
            return
        # only register resurrect if state is valid.
        # this line cannot be tested due to framework's singleton registration that does not
        # allow multiple charm to be instantiated during testing.
        self.resurrect: Resurrect | None = Resurrect(  # pragma: nocover
            self, every=timedelta(hours=state.build_interval)
        )

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

    def _on_start(self, _: ops.StartEvent) -> None:
        """Handle the start event."""
        if not self.resurrect:
            return
        self.resurrect.start()

    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.
        """
        self.unit.status = ops.MaintenanceStatus("Setting up Builder.")
        builder.setup_builder()
        self.unit.status = ops.ActiveStatus()

    def _build_image(self, state: CharmState) -> str:
        """Build image and propagate the new image.

        Args:
            state: The charm state.

        Returns:
            The built image ID.
        """
        self.unit.status = ops.MaintenanceStatus("Building image.")
        build_config = builder.BuildImageConfig(
            arch=state.image_config.arch, base_image=state.image_config.base_image
        )
        image_path = builder.build_image(config=build_config)
        upload_config = openstack_manager.UploadImageConfig(
            arch=state.image_config.arch,
            app_name=self.app.name,
            base=state.image_config.base_image,
            num_revisions=state.revision_history_limit,
            src_path=image_path,
        )
        self.unit.status = ops.MaintenanceStatus("Updating image.")
        with openstack_manager.OpenstackManager(cloud_config=state.cloud_config) as openstack:
            image_id = openstack.upload_image(config=upload_config)

        self.image_observer.update_relation_data(image_id=image_id)
        return image_id

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        state = self._load_state()
        if not state:
            return

        self._build_image(state=state)
        self.unit.status = ops.ActiveStatus()

    def _on_build_image_action(self, event: ops.ActionEvent) -> None:
        """Handle build image action.

        Args:
            event: The build image action event.
        """
        state = self._load_state()
        if not state:
            return

        image_id = self._build_image(state=state)
        event.set_results({"id": image_id})

    def _on_resurrect_timeout(self, _: ResurrectEvent) -> None:
        """Handle the resurrect event."""
        state = self._load_state()
        if not state:
            return

        self._build_image(state=state)


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
