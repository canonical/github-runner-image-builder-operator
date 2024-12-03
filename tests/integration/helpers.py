# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper utilities for integration tests."""

import dataclasses
import inspect
import logging
import time
import urllib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Iterable, ParamSpec, TypeVar, cast

import invoke
from fabric import Connection as SSHConnection
from fabric import Result
from juju.application import Application
from juju.unit import Unit
from openstack.compute.v2.server import Server
from openstack.connection import Connection
from openstack.image.v2.image import Image
from paramiko.ssh_exception import NoValidConnectionsError, SSHException

from tests.integration.types import Commands, OpenstackMeta, ProxyConfig

logger = logging.getLogger(__name__)


def image_created_from_dispatch(
    image_name: str, connection: Connection, dispatch_time: datetime
) -> Image | None:
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
    for image in images:
        if (
            datetime.strptime(image.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            >= dispatch_time
        ):
            return image
    return None


def _install_proxy(conn: SSHConnection, proxy: ProxyConfig | None = None):
    """Run commands to install proxy.

    Args:
        conn: The SSH connection instance.
        proxy: The proxy to apply if available.
    """
    if not proxy or not proxy.http:
        return
    command = "sudo snap install aproxy --edge"
    logger.info("Running command: %s", command)
    result: Result = conn.run(command)
    assert result.ok, "Failed to install aproxy"

    proxy_str = proxy.http.replace("http://", "").replace("https://", "")
    command = f"sudo snap set aproxy proxy={proxy_str} listen=:8443"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to setup aproxy"

    # ignore line too long since it is better read without line breaks
    command = """/usr/bin/sudo nft -f - << EOF
define default-ip = $(ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \\K\\S+') | grep -oP 'src \\K\\S+')
define private-ips = { 10.0.0.0/8, 127.0.0.1/8, 172.16.0.0/12, 192.168.0.0/16 }
table ip aproxy
flush table ip aproxy
table ip aproxy {
    chain prerouting {
            type nat hook prerouting priority dstnat; policy accept;
            ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8443
    }

    chain output {
            type nat hook output priority -100; policy accept;
            ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8443
    }
}
EOF"""  # noqa: E501
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to configure iptable rules"

    command = "sudo snap services aproxy"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to check aproxy status"


def _configure_dockerhub_mirror(conn: SSHConnection, dockerhub_mirror: str | None):
    """Use dockerhub mirror if provided.

    Args:
        conn: The SSH connection instance.
        dockerhub_mirror: The DockerHub mirror URL.
    """
    if not dockerhub_mirror:
        return
    command = "sudo systemctl status docker --no-pager"
    logger.info("Running command: %s", command)
    result: Result = conn.run(command)
    assert result.ok, "Failed to show docker status"

    command = f"""sudo mkdir -p /etc/docker/ && \
echo '{{ "registry-mirrors": ["{dockerhub_mirror}"] }}' | \
sudo tee /etc/docker/daemon.json"""
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to setup DockerHub mirror"

    command = "sudo systemctl daemon-reload"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to reload daemon"

    command = "sudo systemctl restart docker"
    logger.info("Running command: %s", command)
    result = conn.run(command)
    assert result.ok, "Failed to restart docker"


@dataclasses.dataclass
class OpenStackConnectionParams:
    """Parameters for connecting to OpenStack instance.

    Attributes:
        connection: The openstack connection client to communicate with Openstack.
        server_name: Openstack server to find the valid connection from.
        network: The network to find valid connection from.
        ssh_key: The path to public ssh_key to create connection with.
    """

    connection: Connection
    server_name: str
    network: str
    ssh_key: Path


def _wait_for_valid_connection(
    connection_params: OpenStackConnectionParams,
    timeout: int = 30 * 60,
    proxy: ProxyConfig | None = None,
    dockerhub_mirror: str | None = None,
) -> SSHConnection:
    """Wait for a valid SSH connection from Openstack server.

    Args:
        connection_params: Parameters for connecting to OpenStack instance.
        timeout: Number of seconds to wait before raising a timeout error.
        proxy: The proxy to configure on host runner.
        dockerhub_mirror: The DockerHub mirror URL.

    Raises:
        TimeoutError: If no valid connections were found.

    Returns:
        SSHConnection.
    """
    start_time = time.time()
    while time.time() - start_time <= timeout:
        server: Server | None = connection_params.connection.get_server(
            name_or_id=connection_params.server_name
        )
        if not server or not server.addresses:
            time.sleep(10)
            continue
        for address in server.addresses[connection_params.network]:
            ip = address["addr"]
            logger.info(
                "Trying SSH into %s using key: %s...",
                ip,
                str(connection_params.ssh_key.absolute()),
            )
            ssh_connection = SSHConnection(
                host=ip,
                user="ubuntu",
                connect_kwargs={"key_filename": str(connection_params.ssh_key.absolute())},
                connect_timeout=60 * 10,
            )
            try:
                result: Result = ssh_connection.run("echo 'hello world'")
                if result.ok:
                    _install_proxy(conn=ssh_connection, proxy=proxy)
                    _configure_dockerhub_mirror(
                        conn=ssh_connection, dockerhub_mirror=dockerhub_mirror
                    )
                    return ssh_connection
            except (NoValidConnectionsError, TimeoutError, SSHException) as exc:
                logger.warning("Connection not yet ready, %s.", str(exc))
        time.sleep(10)
    raise TimeoutError("No valid ssh connections found.")


def format_dockerhub_mirror_microk8s_command(command: str, dockerhub_mirror: str) -> str:
    """Format dockerhub mirror for microk8s command.

    Args:
        command: The command to run.
        dockerhub_mirror: The DockerHub mirror URL.

    Returns:
        The formatted dockerhub mirror registry command for snap microk8s.
    """
    url = urllib.parse.urlparse(dockerhub_mirror)
    return command.format(registry_url=url.geturl(), hostname=url.hostname, port=url.port)


P = ParamSpec("P")
R = TypeVar("R")
S = Callable[P, R] | Callable[P, Awaitable[R]]


async def wait_for(
    func: S,
    timeout: int | float = 300,
    check_interval: int = 10,
) -> R:
    """Wait for function execution to become truthy.

    Args:
        func: A callback function to wait to return a truthy value.
        timeout: Time in seconds to wait for function result to become truthy.
        check_interval: Time in seconds to wait between ready checks.

    Raises:
        TimeoutError: if the callback function did not return a truthy value within timeout.

    Returns:
        The result of the function if any.
    """
    deadline = time.time() + timeout
    is_awaitable = inspect.iscoroutinefunction(func)
    while time.time() < deadline:
        if is_awaitable:
            if result := await cast(Awaitable, func()):
                return result
        else:
            if result := func():
                return cast(R, result)
        time.sleep(check_interval)

    # final check before raising TimeoutError.
    if is_awaitable:
        if result := await cast(Awaitable, func()):
            return result
    else:
        if result := func():
            return cast(R, result)
    raise TimeoutError()


@asynccontextmanager
async def _get_ssh_connection_for_image(
    image: str,
    test_id: str,
    openstack_metadata: OpenstackMeta,
    proxy: ProxyConfig,
    dockerhub_mirror: str | None,
) -> AsyncIterator[SSHConnection]:
    """Spawn a server with the image and create an SSH connection.

    Args:
        image: The image to use to create server.
        test_id: The unique test ID.
        openstack_metadata: The OpenStack metadata to create servers with.
        proxy: The proxy configuration to spawn the servers with.
        dockerhub_mirror: The dockerhub mirror to configure the OpenStack servers with.

    Yields:
        The SSH connection to the server.
    """
    images = openstack_metadata.connection.search_images(name_or_id=image)
    assert images, f"No image found with name/id {image}"
    server_name = f"test-image-builder-operator-server-{test_id}"
    server: Server = openstack_metadata.connection.create_server(
        name=server_name,
        image=images[0],
        key_name=openstack_metadata.ssh_key.keypair.name,
        auto_ip=False,
        # these are pre-configured values on private endpoint.
        security_groups=[openstack_metadata.security_group.name],
        flavor=openstack_metadata.flavor,
        network=openstack_metadata.network,
        # hostname setting is required for microk8s testing
        userdata="""#!/bin/bash
hostnamectl set-hostname github-runner
DEBIAN_FRONTEND=noninteractive apt-get update -y
""",
        timeout=60 * 10,
        wait=True,
    )

    logger.info("Setting up SSH connection.")
    ssh_connection = _wait_for_valid_connection(
        connection_params=OpenStackConnectionParams(
            connection=openstack_metadata.connection,
            server_name=server.name,
            network=openstack_metadata.network,
            ssh_key=openstack_metadata.ssh_key.private_key,
        ),
        proxy=proxy,
        dockerhub_mirror=dockerhub_mirror,
    )

    yield ssh_connection

    openstack_metadata.connection.delete_server(server_name, wait=True)
    for openstack_image in images:
        openstack_metadata.connection.delete_image(openstack_image.id, wait=True)


def get_image_relation_data(app: Application, key: str = "id") -> None | dict[str, str]:
    """Get default image ID from app relation data.

    Args:
        app: The image builder application.
        key: The key to wait to appear on the relation data.

    Returns:
        The image relation data dictionary if available.
    """
    app = app.latest()
    unit: Unit = app.units[0]
    unit = unit.latest()
    logger.info("Unit data for %s: %s", unit.name, unit.data)
    if not app.relations:
        return None
    image_relation = app.relations[0]
    if not image_relation or not image_relation.data:
        return None
    if key not in image_relation.data:
        return None
    return image_relation.data


@dataclasses.dataclass
class ImageTestMeta:
    """Testing configuration required for image VM testing.

    Attributes:
        proxy: The proxy to enable for testing.
        dockerhub_mirror: The DockerHub mirror URL to enable for docker tests.
        test_id: The unique testing ID.
    """

    proxy: ProxyConfig
    dockerhub_mirror: str | None
    test_id: str


async def run_image_test(
    openstack_metadata: OpenstackMeta,
    image_id: str,
    image_test_meta: ImageTestMeta,
    test_commands: Iterable[Commands],
):
    """Run test commands on an image.

    Args:
        openstack_metadata: OpenStack metadata for creating test server.
        image_id: The image to test.
        image_test_meta: The image testing metadata.
        test_commands: The test commands to run.
    """
    env = (
        {}
        if not image_test_meta.proxy.http
        else {
            "HTTP_PROXY": image_test_meta.proxy.http,
            "HTTPS_PROXY": image_test_meta.proxy.https,
            "NO_PROXY": image_test_meta.proxy.no_proxy,
            "http_proxy": image_test_meta.proxy.http,
            "https_proxy": image_test_meta.proxy.https,
            "no_proxy": image_test_meta.proxy.no_proxy,
        }
    )
    if image_test_meta.dockerhub_mirror:
        env.update(
            DOCKERHUB_MIRROR=image_test_meta.dockerhub_mirror,
            CONTAINER_REGISTRY_URL=image_test_meta.dockerhub_mirror,
        )

    async with _get_ssh_connection_for_image(
        image=image_id,
        test_id=image_test_meta.test_id,
        openstack_metadata=openstack_metadata,
        proxy=image_test_meta.proxy,
        dockerhub_mirror=image_test_meta.dockerhub_mirror,
    ) as ssh_conn:
        for command in test_commands:
            if command.command == "configure dockerhub mirror":
                if not image_test_meta.dockerhub_mirror:
                    continue
                command.command = format_dockerhub_mirror_microk8s_command(
                    command=command.command, dockerhub_mirror=image_test_meta.dockerhub_mirror
                )
            logger.info("Running test: %s", command.name)
            for attempt in range(command.retry):
                try:
                    result: Result = ssh_conn.run(command.command, env=env if env else None)
                except invoke.exceptions.UnexpectedExit as exc:
                    logger.info(
                        "Unexpected exception (retry attempt: %s): %s %s %s %s %s",
                        attempt,
                        exc.reason,
                        exc.args,
                        exc.result.stdout,
                        exc.result.stderr,
                        exc.result.return_code,
                    )
                    continue
                logger.info(
                    "Command output: %s %s %s", result.return_code, result.stdout, result.stderr
                )
                if result.ok:
                    break
            assert result.ok
