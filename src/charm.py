#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Entrypoint for GithubRunnerImageBuilder charm."""

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
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
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
        builder_config_state = state.BuilderConfig.from_charm(charm=self)
        builder.initialize(
            app_init_config=builder.ApplicationInitializationConfig(
                cloud_config=builder_config_state.cloud_config,
                cron_interval=builder_config_state.app_config.build_interval,
                image_arch=builder_config_state.image_config.arch,
                resource_prefix=builder_config_state.app_config.resource_prefix,
                unit_name=self.unit.name,
            )
        )
        self.unit.status = ops.ActiveStatus("Waiting for first image.")

    @charm_utils.block_if_invalid_config(defer=True)
    def _on_upgrade_charm(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle charm upgrade events.

        Upgrades the application.
        """
        self.unit.status = ops.MaintenanceStatus("Running builder upgrade.")
        builder.upgrade_app()
        self.unit.status = ops.ActiveStatus()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_config_changed(self, _: ops.ConfigChangedEvent) -> None:
        """Handle charm configuration change events."""
        builder_config_state = state.BuilderConfig.from_charm(charm=self)
        if not self._is_image_relation_ready_set_status(
            cloud_config=builder_config_state.cloud_config
        ):
            return
        # The following lines should be covered by integration tests.
        proxy.configure_aproxy(proxy=state.ProxyConfig.from_env())  # pragma: no cover
        builder.install_clouds_yaml(  # pragma: no cover
            cloud_config=builder_config_state.cloud_config.openstack_clouds_config
        )
        if builder.configure_cron(  # pragma: no cover
            unit_name=self.unit.name, interval=builder_config_state.app_config.build_interval
        ):
            self._run()
        self.unit.status = ops.ActiveStatus()  # pragma: no cover

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_image_relation_changed(self, _: ops.RelationChangedEvent) -> None:
        """Handle charm image relation changed event."""
        builder_config_state = state.BuilderConfig.from_charm(charm=self)
        if not self._is_image_relation_ready_set_status(
            cloud_config=builder_config_state.cloud_config
        ):
            return
        proxy.configure_aproxy(proxy=state.ProxyConfig.from_env())
        builder.install_clouds_yaml(
            cloud_config=builder_config_state.cloud_config.openstack_clouds_config
        )
        self._run()
        self.unit.status = ops.ActiveStatus()

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_run(self, _: RunEvent) -> None:
        """Handle the run event."""
        builder_config_state = state.BuilderConfig.from_charm(charm=self)
        if not self._is_image_relation_ready_set_status(
            cloud_config=builder_config_state.cloud_config
        ):
            return
        # The following line should be covered by the integration test.
        self._run()  # pragma: nocover

    @charm_utils.block_if_invalid_config(defer=False)
    def _on_run_action(self, event: ops.ActionEvent) -> None:
        """Handle the run action event.

        Args:
            event: The run action event.
        """
        builder_config_state = state.BuilderConfig.from_charm(charm=self)
        if not self._is_image_relation_ready_set_status(
            cloud_config=builder_config_state.cloud_config
        ):
            event.fail("Image relation not yet ready.")
            return
        # The following line should be covered by the integration test.
        self._run()  # pragma: nocover

    def _is_image_relation_ready_set_status(self, cloud_config: state.CloudConfig) -> bool:
        """Check if image relation is ready and set according status otherwise.

        Args:
            cloud_config: The cloud configuration state.

        Returns:
            Whether the image relation is ready.
        """
        if not cloud_config.upload_cloud_ids:
            self.unit.status = ops.BlockedStatus(f"{state.IMAGE_RELATION} integration required.")
            return False
        return True

    def _run(self) -> None:
        """Trigger an image build.

        This method requires that the clouds.yaml are properly installed with build cloud and
        upload cloud authentication parameters.
        """
        self.unit.status = ops.ActiveStatus("Building image.")
        builder_config = state.BuilderConfig.from_charm(self)
        cloud_images = builder.run(
            config_matrix=self._get_configuration_matrix(builder_config=builder_config),
            static_config=self._get_static_config(builder_config=builder_config),
        )
        self.image_observer.update_image_data(cloud_images=cloud_images)
        self.unit.status = ops.ActiveStatus()

    def _get_configuration_matrix(
        self, builder_config: state.BuilderConfig
    ) -> builder.ConfigMatrix:
        """Transform builder_config state to builder configuration matrix.

        Args:
            builder_config: The builder run configuration from state.

        Returns:
            Configurable image parameters to matricize.
        """
        return builder.ConfigMatrix(
            bases=builder_config.image_config.bases,
        )

    def _get_static_config(self, builder_config: state.BuilderConfig) -> builder.StaticConfigs:
        """Transform builder_config state to builder static configuration.

        Args:
            builder_config: The builder run configuration from state.

        Returns:
            Static configurations required to build the image.
        """
        return builder.StaticConfigs(
            cloud_config=builder.CloudConfig(
                build_cloud=builder_config.cloud_config.cloud_name,
                build_flavor=builder_config.cloud_config.external_build_config.flavor,
                build_network=builder_config.cloud_config.external_build_config.network,
                resource_prefix=builder_config.app_config.resource_prefix,
                num_revisions=builder_config.cloud_config.num_revisions,
                upload_clouds=builder_config.cloud_config.upload_cloud_ids,
            ),
            image_config=builder.StaticImageConfig(
                arch=builder_config.image_config.arch,
                script_url=builder_config.image_config.script_url,
                script_secrets=builder_config.image_config.script_secrets,
                runner_version=builder_config.image_config.runner_version,
            ),
            service_config=builder.ExternalServiceConfig(
                proxy=(builder_config.proxy.http if builder_config.proxy else None),
            ),
        )

    def update_status(self, status: ops.StatusBase) -> None:
        """Update the charm status.

        Args:
            status: The desired status instance.
        """
        self.unit.status = status


if __name__ == "__main__":  # pragma: nocover
    ops.main.main(GithubRunnerImageBuilderCharm)
