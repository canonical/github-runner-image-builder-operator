#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import logging
import os
from pathlib import Path
from typing import Any

import ops

import builder
import cron
import image
import proxy
from openstack_manager import OpenstackManager, UploadImageConfig
from state import CharmConfigInvalidError, CharmState

logger = logging.getLogger(__name__)


class BuildSuccessEvent(ops.EventBase):
    """Represents a successful image build event."""


class ImageEvents(ops.CharmEvents):
    """Represents events triggered by image builder callback.

    Attributes:
        build_success: Represents a successful image build event.
    """

    build_success = ops.EventSource(BuildSuccessEvent)


class GithubRunnerImageBuilderCharm(ops.CharmBase):
    """Charm the service.

    Attributes:
        on: Represents custom events managed by cron.
    """

    on = ImageEvents()

    def __init__(self, *args: Any):
        """Initialize the charm.

        Args:
            args: The CharmBase initialization arguments.
        """
        super().__init__(*args)
        self.image_observer = image.Observer(self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.build_success, self._on_build_success)

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

    def _on_install(self, event: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.

        Args:
            event: The event fired on install hook.
        """
        self.unit.status = ops.MaintenanceStatus("Setting up Builder.")
        state = self._load_state()
        if not state:
            # Defer this event since on install should be re-triggered to setup dependencies for
            # the charm. Since the charm goes into blocked state and the user reconfigures the
            # state, config_changed event should be queued after the deferred on_install.
            event.defer()
            return

        proxy.setup(proxy=state.proxy_config)
        builder.setup_builder(
            callback_config=builder.CallbackConfig(
                model_name=self.model.name,
                unit_name=self.unit.name,
                charm_dir=os.getenv("JUJU_CHARM_DIR"),
                hook_name="build_success",
            ),
            cron_config=builder.RunCronConfig(
                app_name=self.app.name,
                arch=state.image_config.arch,
                base=state.image_config.base_image,
                cloud_name=list(state.cloud_config["clouds"].keys())[0],
                interval=state.build_interval,
                model_name=self.model.name,
                num_revisions=state.revision_history_limit,
                unit_name=self.unit.name,
            ),
        )
        self.unit.status = ops.ActiveStatus("Waiting for first image build.")

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        state = self._load_state()
        if not state:
            return

        proxy.configure_aproxy(proxy=state.proxy_config)
        builder.install_cron(config=builder.RunCronConfig())
        self.unit.status = ops.ActiveStatus()

    def _on_build_success(self, _: cron.CronEvent) -> None:
        """Handle cron fired event."""
        state = self._load_state()
        if not state:
            return
        image_id = os.getenv(builder.OPENSTACK_IMAGE_ID_ENV, "")
        if not image_id:
            raise ValueError("Image ID not found.")
        self.image_observer.update_relation_data(image_id=image_id)
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
