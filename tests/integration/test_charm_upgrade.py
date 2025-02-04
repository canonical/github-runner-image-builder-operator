# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test that no breaking change occurs when upgrading a charm from latest stable."""

import functools
import logging

import pytest
from juju.application import Application
from juju.client import client
from juju.unit import Unit

from tests.integration.helpers import wait_for
from tests.integration.types import TestConfigs


@pytest.mark.asyncio
#use ops_test fixture which will work for tests which do not rely on the private endpoint
# for hosting the juju model
async def test_charm_upgrade(app_on_charmhub: Application, test_configs: TestConfigs, ops_test):
    """
    arrange: An active charm deployed from charmhub using latest/stable.
    act: Refresh the charm using the local charm file.
    assert: Upgrade charm hook is emitted and the charm is active.
    """
    logging.info("Refreshing the charm from the local charm file.")
    unit = app_on_charmhub.units[0]
    await ops_test.juju("refresh", "--path", test_configs.charm_file,  app_on_charmhub.name)

    app = app_on_charmhub


    async def is_upgrade_charm_event_emitted(unit: Unit) -> bool:
        """Check if the upgrade_charm event is emitted.

        This is to ensure false positives from only waiting for ACTIVE status.

        Args:
            unit: The unit to check for upgrade charm event.

        Returns:
            bool: True if the event is emitted, False otherwise.
        """
        unit_name_without_slash = unit.name.replace("/", "-")
        juju_unit_log_file = f"/var/log/juju/unit-{unit_name_without_slash}.log"
        stdout = await unit.ssh(command=f"cat {juju_unit_log_file}")
        return "Emitting Juju event upgrade_charm." in stdout

    await wait_for(
        functools.partial(is_upgrade_charm_event_emitted, unit), timeout=360, check_interval=60
    )
    await app.model.wait_for_idle(
        apps=[app.name],
        raise_on_error=False,
        timeout=180 * 60,
        check_freq=30,
    )
