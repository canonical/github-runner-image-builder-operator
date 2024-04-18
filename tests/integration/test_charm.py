#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import logging
from datetime import datetime

from juju.action import Action
from juju.application import Application
from juju.unit import Unit
from openstack.connection import Connection
from openstack.image.v2.image import Image

logger = logging.getLogger(__name__)


async def test_build_image(app: Application, openstack_connection: Connection):
    """
    arrange: A deployed active charm.
    act: When openstack images are listed.
    assert: An image is built successfully.
    """
    images = openstack_connection.list_images()

    assert any(app.name in image for image in images)


async def test_image_cron(app: Application, openstack_connection: Connection):
    """
    arrange: A deployed active charm.
    act: When image cron hook is triggered.
    assert: An image is built successfully.
    """
    unit: Unit = app.units[0]

    dispatch_time = datetime.now()
    cur_env = {
        "JUJU_DISPATCH_PATH": "hooks/trigger",
        "JUJU_MODEL_NAME": app.model.name,
        "JUJU_UNIT_NAME": unit.name,
    }
    env = " ".join(f'{key}="{val}"' for (key, val) in cur_env.items())
    action: Action = await unit.run(
        f"/usr/bin/juju-exec {unit.name} {env} /var/lib/juju/agents/unit-{unit.name.replace('/','-')}/charm/dispatch",
        timeout=20 * 60,
    )
    await action.wait()

    images: list[Image] = openstack_connection.list_images()
    assert any(
        datetime.strptime(image.created_at, "YYYY-MM-DDTHH:mm:ssZ") >= dispatch_time
        for image in images
    )
