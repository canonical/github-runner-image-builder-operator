#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import logging
import typing

import ops

import builder
import charm_utils
import image
import proxy
import state

logger = logging.getLogger(__name__)


class GithubRunnerImageBuilderCharm(ops.CharmBase):
    """Charm GitHubRunner image builder application."""

    def __init__(self, *args: typing.Any):
        """Initialize the charm.

        Args:
            args: The CharmBase initialization arguments.
        """
        super().__init__(*args)
        self.image_observer = image.Observer(self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.run_action, self._on_run_action)

    @charm_utils.block_if_invalid_config(defer=True)
    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.

        """
        self.unit.status = ops.MaintenanceStatus("Setting up Builder.")
        proxy.setup(proxy=state.ProxyConfig.from_env())
        init_config = state.BuilderInitConfig.from_charm(self)
        builder.initialize(init_config=init_config)
        self.unit.status = ops.ActiveStatus("Waiting for first image.")
        self._run()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        proxy.configure_aproxy(proxy=state.ProxyConfig.from_env())
        init_config = state.BuilderInitConfig.from_charm(self)
        builder.install_clouds_yaml(cloud_config=init_config.run_config.cloud_config)
        if builder.configure_cron(unit_name=self.unit.name, interval=init_config.interval):
            self._run()
        self.unit.status = ops.ActiveStatus()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_run_action(self, _: ops.EventBase) -> None:
        """Handle the run action event."""
        self._run()

    def _run(self) -> None:
        """Trigger an image build."""
        self.unit.status = ops.ActiveStatus("Building image.")
        run_config = state.BuilderRunConfig.from_charm(self)
        image_id = builder.run(config=run_config)
        self.image_observer.update_image_data(
            image_id=image_id, arch=run_config.arch, base=run_config.base
        )
        self.unit.status = ops.ActiveStatus("Image build success. Checking and upgrading app.")
        builder.upgrade_app()
        self.unit.status = ops.ActiveStatus()

    def update_status(self, status: ops.StatusBase) -> None:
        """Update the charm status.

        Args:
            status: The desired status instance.
        """
        self.unit.status = status


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
