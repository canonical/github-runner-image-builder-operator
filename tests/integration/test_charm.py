#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import json
import logging
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.connection import Connection
from pytest_operator.plugin import OpsTest

from builder import CRON_BUILD_SCHEDULE_PATH
from state import BUILD_INTERVAL_CONFIG_NAME, ProxyConfig
from tests.integration.helpers import image_created_from_dispatch, wait_for_images

logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_charmcraft_pack(model: Model, proxy: ProxyConfig):
    subprocess.check_call(  # nosec: B603
        ["/snap/bin/charmcraft", "pack", "-p", "tests/integration/data/charm"]
    )
    logging.info("Charmcraft pack completed successfully.")
    if proxy.http:
        logger.info("Setting model proxy: %s", proxy.http)
        await model.set_config(
            {
                "juju-no-proxy": "",
            }
        )


@pytest.mark.asyncio
async def test_image_relation(app: Application, test_charm: Application):
    """
    arrange: An active charm and a test charm that becomes active when valid relation data is set.
    act: When the relation is joined.
    assert: The test charm becomes active due to proper relation data.
    """
    model: Model = app.model
    await model.integrate(app.name, test_charm.name)
    await model.wait_for_idle([app.name], wait_for_active=True, timeout=60 * 60)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_cos_agent_relation(app: Application):
    """
    arrange: An active charm.
    act: When the cos-agent relation is joined.
    assert: The test charm becomes active.
    """
    model: Model = app.model
    grafana_agent = await model.deploy(
        "grafana-agent",
        application_name=f"grafana-agent-{app.name}",
        channel="1/edge",
        series="jammy",
    )
    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], status="active", timeout=30 * 60)


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_build_image(
    openstack_connection: Connection,
    dispatch_time: datetime,
    image_names: list[str],
):
    """
    arrange: A deployed active charm.
    act: When openstack images are listed.
    assert: An image is built successfully.
    """
    await wait_for_images(openstack_connection, dispatch_time, image_names)


# Ignore the "too many arguments" warning, as this is not significant for a test function where
# the arguments are fixtures and the function is not expected to be called directly.
@pytest.mark.abort_on_fail
async def test_charm_another_app_does_not_rebuild_image(  # pylint: disable=R0913,R0917
    app: Application,
    test_charm: Application,
    test_charm_2: Application,
    openstack_connection: Connection,
    image_names: list[str],
    ops_test: OpsTest,
):
    """
    arrange: A test_charm that has already been integrated.
        And another test_charm_2 (with creds on the same cloud) that is not yet integrated.
    act: Integrate the test_charm_2 with the app.
    assert: No additional image is created but instead the already created ones are reused.
    """
    model: Model = app.model
    time_before_relation = datetime.now(tz=timezone.utc)

    await model.integrate(app.name, test_charm_2.name)
    await model.wait_for_idle(apps=(test_charm_2.name,), status="active", timeout=30 * 60)

    # Check that no new image is created
    for image_name in image_names:
        assert (
            image_created_from_dispatch(
                image_name=image_name,
                connection=openstack_connection,
                dispatch_time=time_before_relation,
            )
            is None
        )

    # Check that images in relation data is same for both test charms
    image_builder_unit_name = app.units[0].name
    test_charm_unit_name = test_charm.units[0].name
    _, test_charm_unit_data, _ = await ops_test.juju(
        "show-unit", test_charm_unit_name, "--format", "json"
    )
    logger.info("Test charm unit data: %s", test_charm_unit_data)
    test_charm_unit_data = json.loads(test_charm_unit_data)

    test_charm_2_unit_name = test_charm_2.units[0].name
    _, test_charm_2_unit_data, _ = await ops_test.juju(
        "show-unit", test_charm_2_unit_name, "--format", "json"
    )
    logger.info("Test charm 2 unit data: %s", test_charm_2_unit_data)
    test_charm_2_unit_data = json.loads(test_charm_2_unit_data)

    assert (
        test_charm_unit_data[test_charm_unit_name]["relation-info"][0]["related-units"][
            image_builder_unit_name
        ]["data"]["images"]
        == test_charm_2_unit_data[test_charm_2_unit_name]["relation-info"][0]["related-units"][
            image_builder_unit_name
        ]["data"]["images"]
    )


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_periodic_rebuilt(
    app: Application,
    app_config: dict,
    openstack_connection: Connection,
    image_names: list[str],
):
    """
    arrange: A deployed active charm.
    act: Modify the crontab to run every minute.
    assert: An image is built successfully.
    """
    unit: Unit = next(iter(app.units))

    await app.model.wait_for_idle(apps=(app.name,), status="active", timeout=30 * 60)

    dispatch_time = datetime.now(tz=timezone.utc)
    async with _change_cronjob_to_minutes(
        unit, current_hour_interval=app_config[BUILD_INTERVAL_CONFIG_NAME]
    ):

        await wait_for_images(
            openstack_connection=openstack_connection,
            dispatch_time=dispatch_time,
            image_names=image_names,
        )


@asynccontextmanager
async def _change_cronjob_to_minutes(unit: Unit, current_hour_interval: int):
    """Context manager to change the crontab to run every minute."""
    minute_interval = 1
    await unit.ssh(
        command=rf"sudo sed -i 's/0 \*\/{current_hour_interval}/\*\/{minute_interval} \*/g'  "
        f"{CRON_BUILD_SCHEDULE_PATH}"
    )
    cron_content = await unit.ssh(command=f"cat {CRON_BUILD_SCHEDULE_PATH}")
    logger.info("Cron file content: %s", cron_content)
    await unit.ssh(command="sudo systemctl restart cron")

    yield

    await unit.ssh(
        command=rf"sudo sed -i 's/\*\/{minute_interval} \*/0 \*\/{current_hour_interval}/g'  "
        f"{CRON_BUILD_SCHEDULE_PATH}"
    )
    cron_content = await unit.ssh(command=f"cat {CRON_BUILD_SCHEDULE_PATH}")
    logger.info("Cronfile content: %s", cron_content)
    await unit.ssh(command="sudo systemctl restart cron")


@pytest.mark.asyncio
@pytest.mark.abort_on_fail
async def test_log_rotated(app: Application):
    """
    arrange: A deployed active charm and manually write something to the log file.
    act: trigger logrotate manually
    assert: The log is rotated successfully.
    """
    unit: Unit = next(iter(app.units))
    await app.model.wait_for_idle(apps=(app.name,), timeout=30 * 60)
    test_log = "this log should be rotated"
    await unit.ssh(
        command=f"echo '{test_log}' | " "sudo tee -a /var/log/github-runner-image-builder/info.log"
    )

    # Test that the configuration is loaded successfully using --debug flag
    logrotate_debug_output = await unit.ssh(
        command="sudo /usr/sbin/logrotate /etc/logrotate.conf --debug 2>&1"
    )
    assert (
        "rotating pattern: /var/log/github-runner-image-builder/info.log" in logrotate_debug_output
    )
    # Manually trigger logrotate using --force flag
    await unit.ssh(command="sudo /usr/sbin/logrotate /etc/logrotate.conf --force")
    log_output = await unit.ssh(command="sudo cat /var/log/github-runner-image-builder/info.log")
    assert test_log not in log_output
