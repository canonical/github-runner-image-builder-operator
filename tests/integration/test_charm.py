#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import functools
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.connection import Connection

from builder import CRON_BUILD_SCHEDULE_PATH
from state import BUILD_INTERVAL_CONFIG_NAME
from tests.integration.helpers import image_created_from_dispatch, wait_for

logger = logging.getLogger(__name__)


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
        channel="latest/edge",
    )
    await model.relate(f"{app.name}:cos-agent", f"{grafana_agent.name}:cos-agent")
    await model.wait_for_idle(apps=[app.name], status="active", timeout=30 * 60)


@pytest.mark.asyncio
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
    await _wait_for_images(openstack_connection, dispatch_time, image_names)


@pytest.mark.asyncio
async def test_periodic_rebuilt(
    app: Application, app_config: dict, openstack_connection: Connection, image_names: list[str]
):
    """
    arrange: A deployed active charm.
    act: Modify the crontab to run every minute.
    assert: An image is built successfully.
    """
    unit: Unit = next(iter(app.units))

    await app.model.wait_for_idle(apps=[app.name], status="active", timeout=30 * 60)

    async with _change_crontab_to_minutes(
        unit, current_hour_interval=app_config[BUILD_INTERVAL_CONFIG_NAME]
    ):
        def is_agent_status_executing(unit: Unit):
            status_str = unit.latest().agent_status
            logger.info("Agent status: %s", status_str)
            return status_str == "executing"
        await wait_for(functools.partial(is_agent_status_executing, unit), timeout=60 * 10)

    await _wait_for_images(
        openstack_connection=openstack_connection,
        dispatch_time=datetime.now(tz=timezone.utc),
        image_names=image_names,
    )


@asynccontextmanager
async def _change_crontab_to_minutes(unit: Unit, current_hour_interval: int):
    """Context manager to change the crontab to run every minute."""
    minute_interval = 1
    await unit.ssh(
        command=rf"sudo sed -i 's/0 \*\/{current_hour_interval}/\*\/{minute_interval} \*/g'  "
        f"{CRON_BUILD_SCHEDULE_PATH}"
    )
    await unit.ssh(command="sudo systemctl restart cron")

    yield

    await unit.ssh(
        command=rf"sudo sed -i 's/\*\/{minute_interval} \*/0 \*\/{current_hour_interval}/g'  "
        f"{CRON_BUILD_SCHEDULE_PATH}"
    )
    await unit.ssh(command="sudo systemctl restart cron")


async def _wait_for_images(
    openstack_connection: Connection, dispatch_time: datetime, image_names: list[str]
):
    """Wait for images to be created.

    Args:
        openstack_connection: The openstack connection instance.
        dispatch_time: Time when the image build was dispatched.
        image_names: The image names to check for.
    """
    for image_name in image_names:
        await wait_for(
            functools.partial(
                image_created_from_dispatch,
                connection=openstack_connection,
                dispatch_time=dispatch_time,
                image_name=image_name,
            ),
            check_interval=30,
            timeout=60 * 50,
        )
