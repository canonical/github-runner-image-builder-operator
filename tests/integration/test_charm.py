#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import functools
import logging
from datetime import datetime, timezone

import pytest
from juju.application import Application
from juju.model import Model
from juju.unit import Unit
from openstack.connection import Connection
from openstack.image.v2.image import Image

from tests.integration.helpers import test_image, wait_for
from tests.integration.types import Commands, OpenstackMeta, ProxyConfig

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
    await model.wait_for_idle([app.name], wait_for_active=True, timeout=30 * 60)


def image_created_from_dispatch(
    image_name: str, connection: Connection, dispatch_time: datetime
) -> bool:
    """Return whether there is an image created after dispatch has been called.

    Args:
        image_name: The image name to check for.
        connection: The OpenStack connection instance.
        dispatch_time: Time when the image build was dispatched.

    Returns:
        Whether there exists an image that has been created after dispatch time.
    """
    images: list[Image] = connection.search_images(image_name)
    logger.info(
        "Image name: %s, Images: %s",
        image_name,
        tuple((image.id, image.name, image.created_at) for image in images),
    )
    # split logs, the image log is long and gets cut off.
    logger.info("Dispatch time: %s", dispatch_time)
    return any(
        datetime.strptime(image.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        >= dispatch_time
        for image in images
    )


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
            timeout=60 * 30,
        )


# This is matched with E2E test run of github-runner-operator charm.
TEST_RUNNER_COMMANDS = (
    Commands(name="simple hello world", command="echo 'hello world'"),
    Commands(
        name="file permission to /usr/local/bin", command="ls -ld /usr/local/bin | grep drwxrwxrwx"
    ),
    Commands(
        name="file permission to /usr/local/bin (create)", command="touch /usr/local/bin/test_file"
    ),
    Commands(name="proxy internet access test", command="curl google.com", retry=3),
    Commands(name="install microk8s", command="sudo snap install microk8s --classic", retry=3),
    # This is a special helper command to configure dockerhub registry if available.
    Commands(
        name="configure dockerhub mirror",
        command="""echo 'server = "{registry_url}"

[host.{hostname}:{port}]
capabilities = ["pull", "resolve"]
' | sudo tee /var/snap/microk8s/current/args/certs.d/docker.io/hosts.toml && \
sudo microk8s stop && sudo microk8s start""",
    ),
    Commands(name="wait for microk8s", command="microk8s status --wait-ready"),
    Commands(
        name="deploy nginx in microk8s",
        command="microk8s kubectl create deployment nginx --image=nginx",
    ),
    Commands(
        name="wait for nginx",
        command="microk8s kubectl rollout status deployment/nginx --timeout=40m",
    ),
    Commands(name="docker version", command="docker version"),
    Commands(name="update apt in docker", command="docker run python:3.10-slim apt-get update"),
    Commands(name="check python3 alias", command="python --version"),
    Commands(name="pip version", command="python3 -m pip --version"),
    Commands(name="npm version", command="npm --version"),
    Commands(name="shellcheck version", command="shellcheck --version"),
    Commands(name="jq version", command="jq --version"),
    Commands(name="yq version", command="yq --version"),
    Commands(name="apt update", command="sudo apt-get update -y"),
    Commands(name="install pipx", command="sudo apt-get install -y pipx"),
    Commands(name="install check-jsonschema", command="pipx install check-jsonschema"),
    Commands(name="unzip version", command="unzip -v"),
    Commands(name="gh version", command="gh --version"),
    Commands(name="check jsonschema", command="~/.local/bin/check-jsonschema --version"),
    Commands(
        name="test sctp support", command="sudo apt-get install lksctp-tools -yq && checksctp"
    ),
)

JUJU_RUNNER_COMMANDS = (
    *TEST_RUNNER_COMMANDS,
    Commands(name="juju bootstrapped test", command="juju status"),
)


@pytest.mark.asyncio
async def test_bare_image(
    proxy: ProxyConfig,
    dockerhub_mirror: str | None,
    test_id: str,
    openstack_metadata: OpenstackMeta,
    bare_image_id: str,
):
    """
    arrange: given a latest bare image build, a ssh-key and a server.
    act: when commands are run through ssh.
    assert: all binaries are present and run without errors.
    """
    await test_image(
        proxy=proxy,
        dockerhub_mirror=dockerhub_mirror,
        openstack_metadata=openstack_metadata,
        image_id=bare_image_id,
        test_id=test_id,
        test_commands=TEST_RUNNER_COMMANDS,
    )


async def test_juju_image(
    proxy: ProxyConfig,
    dockerhub_mirror: str | None,
    test_id: str,
    openstack_metadata: OpenstackMeta,
    bare_image_id: str,
):
    """
    arrange: given a latest juju image build, a ssh-key and a server.
    act: when commands are run through ssh.
    assert: all binaries are present and run without errors.
    """
    await test_image(
        proxy=proxy,
        dockerhub_mirror=dockerhub_mirror,
        openstack_metadata=openstack_metadata,
        image_id=bare_image_id,
        test_id=test_id,
        test_commands=JUJU_RUNNER_COMMANDS,
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
