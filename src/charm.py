#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import logging
import os
import typing

import ops

import builder
import charm_utils
import image
import proxy
import state

logger = logging.getLogger(__name__)


BUILD_SUCCESS_EVENT_NAME = "build_success"
OPENSTACK_IMAGE_ID_ENV = "OPENSTACK_IMAGE_ID"


class BuildSuccessEvent(ops.EventBase):
    """Represents a successful image build event."""


class BuildEvents(ops.CharmEvents):
    """Represents events triggered by image builder callback.

    Attributes:
        build_success: Represents a successful image build event.
    """

    build_success = ops.EventSource(BuildSuccessEvent)


class GithubRunnerImageBuilderCharm(ops.CharmBase):
    """Charm GitHubRunner image builder application.

    Attributes:
        on: Represents custom events managed by cron.
    """

    on = BuildEvents()

    def __init__(self, *args: typing.Any):
        """Initialize the charm.

        Args:
            args: The CharmBase initialization arguments.
        """
        super().__init__(*args)
        self.image_observer = image.Observer(self)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.build_success, self._on_build_success)

    def _create_callback_script(self) -> None:
        """Create callback script to propagate images."""
        charm_dir = os.getenv("JUJU_CHARM_DIR")
        cur_env = {
            "JUJU_DISPATCH_PATH": f"hooks/{BUILD_SUCCESS_EVENT_NAME}",
            "JUJU_MODEL_NAME": self.model.name,
            "JUJU_UNIT_NAME": self.unit.name,
            OPENSTACK_IMAGE_ID_ENV: "$OPENSTACK_IMAGE_ID",
        }
        env = " ".join(f'{key}="{val}"' for (key, val) in cur_env.items())
        script_contents = f"""#! /bin/bash
OPENSTACK_IMAGE_ID="$1"

/usr/bin/juju-exec {self.unit.name} {env} {charm_dir}/dispatch
"""
        builder.CALLBACK_SCRIPT_PATH.write_text(script_contents, encoding="utf-8")
        builder.CALLBACK_SCRIPT_PATH.chmod(0o755)

    @charm_utils.block_if_invalid_config(defer=True)
    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.

        """
        self.unit.status = ops.MaintenanceStatus("Setting up Builder.")
        proxy.setup(proxy=state.ProxyConfig.from_env())
        self._create_callback_script()
        init_config = state.BuilderInitConfig.from_charm(self)
        builder.initialize(init_config=init_config)
        self.unit.status = ops.ActiveStatus("Waiting for first image.")
        builder.run(config=init_config.run_config)

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        proxy.configure_aproxy(proxy=state.ProxyConfig.from_env())
        init_config = state.BuilderInitConfig.from_charm(self)
        builder.install_clouds_yaml(cloud_config=init_config.run_config.cloud_config)
        if builder.configure_cron(
            run_config=init_config.run_config, interval=init_config.interval
        ):
            builder.run(config=init_config.run_config)
        self.unit.status = ops.ActiveStatus()

    def _on_build_success(self, _: BuildSuccessEvent) -> None:
        """Handle cron fired event."""
        image_id = os.getenv(OPENSTACK_IMAGE_ID_ENV, "")
        if not image_id:
            self.unit.status = ops.ActiveStatus(
                f"Failed to build image. Check {builder.OUTPUT_LOG_PATH}."
            )
            return
        self.image_observer.update_image_id(image_id=image_id)
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
