#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration testing module."""

import dataclasses
import logging
from datetime import datetime, timezone

import pytest
from fabric.connection import Connection as SSHConnection
from fabric.runners import Result
from juju.application import Application
from juju.model import Model
from openstack.connection import Connection
from openstack.image.v2.image import Image

from builder import IMAGE_NAME_TMPL
from state import BASE_IMAGE_CONFIG_NAME, _get_supported_arch
from tests.integration.helpers import format_dockerhub_mirror_microk8s_command, wait_for
from tests.integration.types import ProxyConfig

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_build_image(app: Application, openstack_connection: Connection):
    """
    arrange: A deployed active charm.
    act: When openstack images are listed.
    assert: An image is built successfully.
    """
    dispatch_time = datetime.now(tz=timezone.utc)
    config: dict = await app.get_config()
    image_base = config[BASE_IMAGE_CONFIG_NAME]["value"]

    def image_created_from_dispatch() -> bool:
        """Return whether there is an image created after dispatch has been called.

        Returns:
            Whether there exists an image that has been created after dispatch time.
        """
        image_name = IMAGE_NAME_TMPL.format(
            IMAGE_BASE=image_base, APP_NAME=app.name, ARCH=_get_supported_arch().value
        )
        images: list[Image] = openstack_connection.search_images(image_name)
        logger.info("Image name: %s, Images: %s", image_name, images)
        # split logs, the image log is long and gets cut off.
        logger.info("Dispatch time: %s", dispatch_time)
        return any(
            datetime.strptime(image.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            >= dispatch_time
            for image in images
        )

    await wait_for(image_created_from_dispatch, check_interval=30, timeout=60 * 30)


@pytest.mark.asyncio
async def test_image_relation(app: Application, test_charm: Application):
    """
    arrange: An active charm and a test charm that becomes active when valid relation data is set.
    act: When the relation is joined.
    assert: The test charm becomes active due to proper relation data.
    """
    model: Model = app.model
    await model.integrate(app.name, test_charm.name)
    await model.wait_for_idle([app.name, test_charm.name], wait_for_active=True)


@dataclasses.dataclass
class Commands:
    """Test commands to execute.

    Attributes:
        name: The test name.
        command: The command to execute.
    """

    name: str
    command: str


# This is matched with E2E test run of github-runner-operator charm.
TEST_RUNNER_COMMANDS = (
    Commands(name="simple hello world", command="echo 'hello world'"),
    Commands(
        name="file permission to /usr/local/bin", command="ls -ld /usr/local/bin | grep drwxrwxrwx"
    ),
    Commands(
        name="file permission to /usr/local/bin (create)", command="touch /usr/local/bin/test_file"
    ),
    Commands(name="install microk8s", command="sudo snap install microk8s --classic"),
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


@pytest.mark.asyncio
async def test_image(
    ssh_connection: SSHConnection, proxy: ProxyConfig, dockerhub_mirror: str | None
):
    """
    arrange: given a latest image build, a ssh-key and a server.
    act: when commands are run through ssh.
    assert: all binaries are present and run without errors.
    """
    env = (
        {}
        if not proxy.http
        else {
            "HTTP_PROXY": proxy.http,
            "HTTPS_PROXY": proxy.https,
            "NO_PROXY": proxy.no_proxy,
            "http_proxy": proxy.http,
            "https_proxy": proxy.https,
            "no_proxy": proxy.no_proxy,
        }
    )
    if dockerhub_mirror:
        env.update(DOCKERHUB_MIRROR=dockerhub_mirror, CONTAINER_REGISTRY_URL=dockerhub_mirror)

    for command in TEST_RUNNER_COMMANDS:
        if command.command == "configure dockerhub mirror":
            if not dockerhub_mirror:
                continue
            command.command = format_dockerhub_mirror_microk8s_command(
                command=command.command, dockerhub_mirror=dockerhub_mirror
            )
        logger.info("Running test: %s", command.name)
        result: Result = ssh_connection.run(command.command, env=env if env else None)
        logger.info("Command output: %s %s %s", result.return_code, result.stdout, result.stderr)
        assert result.ok
