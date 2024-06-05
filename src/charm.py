#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

import functools
import logging
import os
import typing

import ops

import builder
import image
import proxy
from state import CharmConfigInvalidError, CharmState

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


class GithubRunnerImageBuilderCharmProtocol(
    typing.Protocol
):  # pylint: disable=too-few-public-methods
    """Protocol to use for the decorator to block if invalid."""

    def update_status(self, status: ops.StatusBase) -> None:
        """Update the application and unit status.

        Args:
            status: the desired unit status.
        """


C = typing.TypeVar("C", bound=GithubRunnerImageBuilderCharmProtocol)
E = typing.TypeVar("E", bound=ops.EventBase)


def block_if_invalid_config(defer: bool = False):
    """Create a decorator that puts the charm in blocked state if the config is wrong.

    Args:
        defer: whether to defer the event.

    Returns:
        the function decorator.
    """

    def decorator(method: typing.Callable[[C, E], None]) -> typing.Callable[[C, E], None]:
        """Create a decorator that puts the charm in blocked state if the config is wrong.

        Args:
            method: observer method to wrap.

        Returns:
            the function wrapper.
        """

        @functools.wraps(method)
        def wrapper(instance: C, event: E) -> None:
            """Block the charm if the config is wrong.

            Args:
                instance: the instance of the class with the hook method.
                event: the event for the observer

            Returns:
                The value returned from the original function. That is, None.
            """
            try:
                return method(instance, event)
            except CharmConfigInvalidError as exc:
                if defer:
                    event.defer()
                logger.exception("Wrong Charm Configuration")
                instance.update_status(ops.BlockedStatus(exc.msg))
                return None

        return wrapper

    return decorator


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

    def _load_state(self) -> CharmState | None:
        """Load the charm state if valid, set charm to blocked otherwise.

        Returns:
            Initialized charm state if valid charm state. None if invalid charm state was found.
        """
        return CharmState.from_charm(self)

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

    @block_if_invalid_config(defer=True)
    def _on_install(self, _: ops.InstallEvent) -> None:
        """Handle installation of the charm.

        Installs apt packages required to build the image.

        """
        self.unit.status = ops.MaintenanceStatus("Setting up Builder.")
        state = CharmState.from_charm(self)
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

    @block_if_invalid_config(defer=False)
    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        state = CharmState.from_charm(self)
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
