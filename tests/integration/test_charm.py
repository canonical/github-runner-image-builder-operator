#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import logging
from datetime import datetime
from typing import NamedTuple

from fabric.connection import Connection as SSHConnection
from fabric.runners import Result
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.connection import Connection
from openstack.image.v2.image import Image

from tests.integration.helpers import wait_for

logger = logging.getLogger(__name__)


async def test_build_image(app: Application, openstack_connection: Connection):
    """
    arrange: A deployed active charm.
    act: When openstack images are listed.
    assert: An image is built successfully.
    """
    images: list[Image] = openstack_connection.list_images()

    assert any(app.name in image.name for image in images)


async def test_image_cron(model: Model, app: Application, openstack_connection: Connection):
    """
    arrange: A deployed active charm.
    act: When image cron hook is triggered.
    assert: An image is built successfully.
    """
    await model.wait_for_idle(apps=[app.name], wait_for_active=True, timeout=30 * 60)
    unit: Unit = app.units[0]

    dispatch_time = datetime.now()
    cur_env = {
        "JUJU_DISPATCH_PATH": "hooks/trigger",
        "JUJU_MODEL_NAME": app.model.name,
        "JUJU_UNIT_NAME": unit.name,
    }
    env = " ".join(f'{key}="{val}"' for (key, val) in cur_env.items())
    await unit.ssh(
        (
            f"sudo /usr/bin/juju-exec {unit.name} {env} /var/lib/juju/agents/unit-"
            f"{unit.name.replace('/','-')}/charm/dispatch"
        )
    )
    await model.wait_for_idle(apps=[app.name], wait_for_active=True, timeout=30 * 60)

    def image_created_from_dispatch() -> bool:
        """Return whether there is an image created after dispatch has been called.

        Returns:
            Whether there exists an image that has been created after dispatch time.
        """
        images: list[Image] = openstack_connection.list_images()
        logger.info("Images: %s, dispatch time: %s", images, dispatch_time)
        return any(
            # .now() is required for timezone aware date comparison.
            datetime.strptime(image.created_at, "%Y-%m-%dT%H:%M:%SZ").now() >= dispatch_time.now()
            for image in images
        )

    await wait_for(image_created_from_dispatch, check_interval=30)


class TestCommand(NamedTuple):
    """Test commands to execute.

    Attributes:
        name: The test name.
        command: The command to execute.
        expected: The expected stdout result.
    """

    name: str
    command: str
    expected: str


# This is matched with E2E test run of github-runner-operator charm.
TEST_RUNNER_COMMANDS = (
    TestCommand(name="simple hello world", command="echo 'hello world'", expected="hello world"),
    TestCommand(
        name="file permission to /usr/local/bin",
        command="ls -ld /usr/local/bin | grep drwxrwxrwx",
        expected="drwxrwxrwx",
    ),
    TestCommand(
        name="file permission to /usr/local/bin (create)",
        command="touch /usr/local/bin/test_file",
        expected="",
    ),
    TestCommand(
        name="install microk8s", command="sudo snap install microk8s --classic", expected=""
    ),
    TestCommand(name="wait for microk8s", command="microk8s status --wait-ready", expected=""),
    TestCommand(
        name="deploy nginx in microk8s",
        command="microk8s kubectl create deployment nginx --image=nginx",
        expected="",
    ),
    TestCommand(
        name="wait for nginx",
        command="microk8s kubectl rollout status deployment/nginx --timeout=30m",
        expected="",
    ),
    TestCommand(
        name="update apt in docker",
        command="docker run python:3.10-slim apt-get update",
        expected="",
    ),
    TestCommand(name="docker version", command="docker version", expected=""),
    TestCommand(name="check python3 alias", command="python --version", expected=""),
    TestCommand(name="pip version", command="python3 -m pip --version", expected=""),
    TestCommand(name="npm version", command="npm --version", expected=""),
    TestCommand(name="shellcheck version", command="shellcheck --version", expected=""),
    TestCommand(name="jq version", command="jq --version", expected=""),
    TestCommand(name="yq version", command="yq --version", expected=""),
    TestCommand(name="apt update", command="sudo apt-get update -y", expected=""),
    TestCommand(name="install pipx", command="sudo apt-get install -y pipx", expected=""),
    TestCommand(
        name="install check-jsonschema", command="pipx install check-jsonschema", expected=""
    ),
    TestCommand(name="unzip version", command="unzip -v", expected=""),
    TestCommand(name="gh version", command="gh --version", expected=""),
    TestCommand(name="check jsonschema", command="check-jsonschema --version", expected=""),
    TestCommand(
        name="test sctp support",
        command="sudo apt-get install lksctp-tools -yq && checksctp",
        expected="",
    ),
)


async def test_image(ssh_connection: SSHConnection):
    """
    arrange: given a latest image build, a ssh-key and a server.
    act: when commands are run through ssh.
    assert: all binaries are present and run without errors.
    """
    for command in TEST_RUNNER_COMMANDS:
        logger.info("Running test: %s", command.name)
        result: Result = ssh_connection.run(command.command)
        assert result.ok
        if command.expected:
            assert command.expected == result.stdout
