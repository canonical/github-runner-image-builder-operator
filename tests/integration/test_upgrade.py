# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test that no breaking change occurs when upgrading the charm."""

import functools
import logging

import pytest
from juju.application import Application
from juju.unit import Unit

from tests.integration.helpers import wait_for
from tests.integration.types import OpenstackMeta, TestConfigs


@pytest.mark.asyncio
async def test_upgrade(
    app_on_charmhub: Application,
    test_configs: TestConfigs,
    ops_test,
    openstack_metadata: OpenstackMeta,
):
    """
    arrange: An active charm deployed from charmhub.
    act: Refresh the charm using the local charm file.
    assert: Upgrade charm hook is emitted ran successfully.
    """
    logging.info("Refreshing the charm from the local charm file.")
    unit = app_on_charmhub.units[0]
    await ops_test.juju(
        "refresh",
        "--path",
        test_configs.charm_file,
        "--config",
        f"build-flavor={openstack_metadata.flavor}",
        "--config",
        f"build-network={openstack_metadata.network}",
        app_on_charmhub.name,
    )

    app = app_on_charmhub

    async def is_upgrade_charm_event_emitted(unit: Unit) -> bool:
        """Check if the upgrade_charm event is emitted.

        This is to ensure false positives from only waiting for ACTIVE status or
        relying on the juju status.
        We cannot rely on the juju status containing revision zero, because it changes instantly,
        and the hook upgrade-charm can run with a significant delay.

        Args:
            unit: The unit to check for upgrade charm event.

        Returns:
            bool: True if the event is emitted, False otherwise.
        """
        unit_name_without_slash = unit.name.replace("/", "-")
        juju_unit_log_file = f"/var/log/juju/unit-{unit_name_without_slash}.log"
        stdout = await unit.ssh(command=f"cat {juju_unit_log_file} | grep 'Emitting Juju event upgrade_charm.'")
        return "Emitting Juju event upgrade_charm." in stdout

    await wait_for(
        functools.partial(is_upgrade_charm_event_emitted, unit), timeout=360, check_interval=60
    )
    await app.model.wait_for_idle(
        apps=[app.name],
        raise_on_error=True,
        timeout=180 * 60,
        check_freq=30,
    )
