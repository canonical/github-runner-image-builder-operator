#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

from charm_utils import remove_residual_venv_dirs

# This is a workaround for https://bugs.launchpad.net/juju/+bug/2058335
# It is important that this is run before importing any other modules.
# pylint: disable=wrong-import-position,wrong-import-order
remove_residual_venv_dirs()

import logging
import typing

import ops
from charms.grafana_agent.v0.cos_agent import COSAgentProvider

import builder
import charm_utils
import image
import proxy
import state

logger = logging.getLogger(__name__)


class RunEvent(ops.EventBase):
    """Event representing a periodic image builder run."""


class GithubRunnerImageBuilderCharm(ops.CharmBase):
    """Charm GitHubRunner image builder application."""

    def __init__(self, *args: typing.Any):
        """Initialize the charm.

        Args:
            args: The CharmBase initialization arguments.
        """
        super().__init__(*args)
        self.on.define_event("run", RunEvent)

        self.image_observer = image.Observer(self)
        self._grafana_agent = COSAgentProvider(charm=self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.run, self._on_run)
        self.framework.observe(self.on.run_action, self._on_run_action)
        self.framework.observe(
            self.on[state.IMAGE_RELATION].relation_changed, self._on_image_relation_changed
        )

    @charm_utils.block_if_invalid_config(defer=True)
    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.

        """
        self.unit.status = ops.MaintenanceStatus("Setting up Builder.")
        proxy.setup(proxy=state.ProxyConfig.from_env())
        init_config = state.BuilderInitConfig.from_charm(self)
        builder.install_clouds_yaml(
            cloud_config=init_config.run_config.cloud_config.openstack_clouds_config
        )
        builder.initialize(init_config=init_config)
        self.unit.status = ops.ActiveStatus("Waiting for first image.")

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        init_config = state.BuilderInitConfig.from_charm(self)
        if not self._is_image_relation_ready_set_status(config=init_config.run_config):
            return
        proxy.configure_aproxy(proxy=state.ProxyConfig.from_env())
        builder.install_clouds_yaml(
            cloud_config=init_config.run_config.cloud_config.openstack_clouds_config
        )
        if builder.configure_cron(unit_name=self.unit.name, interval=init_config.interval):
            self._run()
        self.unit.status = ops.ActiveStatus()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_image_relation_changed(self, _: ops.RelationChangedEvent) -> None:
        """Handle charm image relation changed event."""
        init_config = state.BuilderInitConfig.from_charm(self)
        if not self._is_image_relation_ready_set_status(config=init_config.run_config):
            return
        proxy.configure_aproxy(proxy=state.ProxyConfig.from_env())
        builder.install_clouds_yaml(
            cloud_config=init_config.run_config.cloud_config.openstack_clouds_config
        )
        self._run()
        self.unit.status = ops.ActiveStatus()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_run(self, _: RunEvent) -> None:
        """Handle the run event."""
        init_config = state.BuilderInitConfig.from_charm(self)
        if not self._is_image_relation_ready_set_status(config=init_config.run_config):
            return
        self._run()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_run_action(self, event: ops.ActionEvent) -> None:
        """Handle the run action event.

        Args:
            event: The run action event.
        """
        init_config = state.BuilderInitConfig.from_charm(self)
        if not self._is_image_relation_ready_set_status(config=init_config.run_config):
            event.fail("Image relation not yet ready.")
            return
        self._run()

    def _is_image_relation_ready_set_status(self, config: state.BuilderRunConfig) -> bool:
        """Check if image relation is ready and set according status otherwise.

        Args:
            config: The image builder run configuration.

        Returns:
            Whether the image relation is ready.
        """
        if not config.cloud_config.upload_cloud_ids:
            self.unit.status = ops.BlockedStatus(f"{state.IMAGE_RELATION} integration required.")
            return False
        return True

    def _run(self) -> None:
        """Trigger an image build.

        This method requires that the clouds.yaml are properly installed with build cloud and
        upload cloud authentication parameters.
        """
        self.unit.status = ops.ActiveStatus("Running upgrade.")
        builder.upgrade_app()
        self.unit.status = ops.ActiveStatus("Building image.")
        run_config = state.BuilderRunConfig.from_charm(self)
        cloud_images = builder.run(config=run_config)
        self.image_observer.update_image_data(cloud_images=cloud_images)
        self.unit.status = ops.ActiveStatus()

    def update_status(self, status: ops.StatusBase) -> None:
        """Update the charm status.

        Args:
            status: The desired status instance.
        """
        self.unit.status = status


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
