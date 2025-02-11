#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import functools
import logging
from datetime import datetime

import pytest
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.connection import Connection

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


@pytest.mark.skip(reason="There is an issue with dispatch tests as of now")
@pytest.mark.asyncio
async def test_run_dispatch(app: Application):
    """
    arrange: A deployed active charm.
    act: When dispatch command is given.
    assert: An image is built successfully.
    """
    unit: Unit = next(iter(app.units))
    await unit.ssh(
        command=(
            f'sudo -E -b /usr/bin/juju-exec "{unit.name}" "JUJU_DISPATCH_PATH=run '
            'HOME=/home/ubuntu ./dispatch"'
        ),
    )

    await wait_for(lambda: unit.latest().agent_status == "executing")
