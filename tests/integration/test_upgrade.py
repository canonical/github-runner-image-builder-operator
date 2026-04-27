# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test that no breaking change occurs when upgrading the charm."""

import logging
from datetime import datetime, timezone

import jubilant
import pytest

from state import OPENSTACK_PASSWORD_SECRET_CONFIG_NAME
from tests.integration.conftest import _Secret
from tests.integration.helpers import wait_for, wait_for_images
from tests.integration.types import OpenstackMeta, TestConfigs


@pytest.fixture(scope="module", name="app")
def app_fixture(
    juju: jubilant.Juju,
    app_on_charmhub: str,
    test_configs: TestConfigs,
    openstack_metadata: OpenstackMeta,
    openstack_password_secret: _Secret,
) -> str:
    """Upgrade the charm from the local charm file."""
    logging.info("Refreshing the charm from the local charm file.")
    juju.refresh(
        app_on_charmhub,
        path=test_configs.charm_file,
        config={
            "build-flavor": openstack_metadata.flavor,
            "build-network": openstack_metadata.network,
        },
    )
    # The new charm requires openstack-password-secret; grant and set it now
    # in case the charmhub version did not support this config option yet.
    juju.grant_secret(openstack_password_secret.name, app_on_charmhub)
    juju.config(
        app_on_charmhub, {OPENSTACK_PASSWORD_SECRET_CONFIG_NAME: openstack_password_secret.id}
    )
    status = juju.status()
    unit_name = next(iter(status.apps[app_on_charmhub].units))

    def is_upgrade_charm_event_emitted() -> bool:
        """Check if the upgrade_charm event is emitted.

        This is to ensure false positives from only waiting for ACTIVE status or
        relying on the juju status.
        We cannot rely on the juju status containing revision zero, because it changes instantly,
        and the hook upgrade-charm can run with a significant delay.

        Returns:
            bool: True if the event is emitted, False otherwise.
        """
        unit_name_without_slash = unit_name.replace("/", "-")
        juju_unit_log_file = f"/var/log/juju/unit-{unit_name_without_slash}.log"
        stdout = juju.ssh(unit_name, f"sudo cat {juju_unit_log_file}")
        return "Emitting Juju event upgrade_charm." in stdout

    wait_for(is_upgrade_charm_event_emitted, timeout=360, check_interval=60)
    juju.wait(
        lambda s: jubilant.all_agents_idle(s, app_on_charmhub),
        error=jubilant.any_error,
        timeout=180 * 60,
        delay=30,
    )

    return app_on_charmhub


def test_image_build(
    juju: jubilant.Juju,
    app: str,
    test_charm: str,
    openstack_connection,
    image_names: list[str],
):
    """
    arrange: A refreshed application.
    act: Integrate the refreshed charm with the test charm.
    assert: Image building is working.
    """
    dispatch_time = datetime.now(tz=timezone.utc)
    juju.integrate(app, test_charm)

    wait_for_images(
        openstack_connection=openstack_connection,
        dispatch_time=dispatch_time,
        image_names=image_names,
    )
