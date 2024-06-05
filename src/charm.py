#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import logging
import os
from typing import Any

import ops

import builder
import image
import proxy
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


BUILD_SUCCESS_EVENT_NAME = "build_success"
CALLBACK_SCRIPT_PATH = builder.UBUNTU_HOME / "propagate_image_id"
OPENSTACK_IMAGE_ID_ENV = "OPENSTACK_IMAGE_ID"


class GithubRunnerImageBuilderCharm(ops.CharmBase):
    """Charm GitHubRunner image builder application.

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
        """Load the charm state if valid, set charm to blocked otherwise.

        Returns:
            Initialized charm state if valid charm state. None if invalid charm state was found.
        """
        try:
            return CharmState.from_charm(self)
        except CharmConfigInvalidError as exc:
            self.unit.status = ops.BlockedStatus(str(exc))
            return None

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
        builder.CALLBACK_SCRIPT_PATH.touch(exist_ok=True)
        builder.CALLBACK_SCRIPT_PATH.write_text(script_contents, encoding="utf-8")
        builder.CALLBACK_SCRIPT_PATH.chmod(0o755)

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
        self._create_callback_script()
        build_config = builder.BuildConfig(
            arch=state.image_config.arch,
            base=state.image_config.base_image,
            callback_script=builder.CALLBACK_SCRIPT_PATH.relative_to(builder.UBUNTU_HOME),
            cloud_name=state.cloud_name,
            num_revisions=state.revision_history_limit,
        )
        builder.setup_builder(
            build_config=build_config,
            cloud_config=state.cloud_config,
            interval=state.build_interval,
        )
        builder.build_immediate(config=build_config)
        self.unit.status = ops.ActiveStatus("Waiting for first image.")

    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        state = self._load_state()
        if not state:
            return

        proxy.configure_aproxy(proxy=state.proxy_config)
        builder.install_clouds_yaml(cloud_config=state.cloud_config)
        build_config = builder.BuildConfig(
            arch=state.image_config.arch,
            base=state.image_config.base_image,
            callback_script=builder.CALLBACK_SCRIPT_PATH.relative_to(builder.UBUNTU_HOME),
            cloud_name=state.cloud_name,
            num_revisions=state.revision_history_limit,
        )
        if builder.configure_cron(build_config=build_config, interval=state.build_interval):
            builder.build_immediate(config=build_config)
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
