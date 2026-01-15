# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test that no breaking change occurs when upgrading the charm."""

import functools
import logging
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.connection import Connection

from tests.integration.helpers import wait_for, wait_for_images
from tests.integration.types import OpenstackMeta, TestConfigs


@pytest_asyncio.fixture(scope="module", name="app")
async def app_fixture(
    app_on_charmhub: Application,
    test_configs: TestConfigs,
    openstack_metadata: OpenstackMeta,
    ops_test,
) -> Application:
    """Upgrade the charm from the local charm file."""
    logging.info("Refreshing the charm from the local charm file.")
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
    unit = app.units[0]

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
        try:
            unit_name_without_slash = unit.name.replace("/", "-")
            juju_unit_log_file = f"/var/log/juju/unit-{unit_name_without_slash}.log"
            stdout = await unit.ssh(command=f"cat {juju_unit_log_file}")
            logging.info("Upgrade logs:\n%s", stdout)
            return "Emitting Juju event upgrade_charm." in stdout
        except Exception as e:
            # Unit might not be reachable yet, return False and try again
            logging.debug(f"Could not check upgrade_charm event: {e}")
            return False

    await wait_for(
        functools.partial(is_upgrade_charm_event_emitted, unit), timeout=360, check_interval=60
    )
    await app.model.wait_for_idle(
        apps=[app.name],
        raise_on_error=True,
        timeout=180 * 60,
        check_freq=30,
    )

    return app


@pytest.mark.asyncio
async def test_image_build(
    app: Application,
    test_charm: Application,
    openstack_connection: Connection,
    image_names: list[str],
):
    """
    arrange: A refreshed application.
    act: Integrate the refreshed charm with the test charm.
    assert: Image building is working.
    """
    model: Model = app.model
    dispatch_time = datetime.now(tz=timezone.utc)
    await model.integrate(app.name, test_charm.name)

    await wait_for_images(
        openstack_connection=openstack_connection,
        dispatch_time=dispatch_time,
        image_names=image_names,
    )
